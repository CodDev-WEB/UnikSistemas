import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import AuditLog, Client, Tenant, User
from app.schemas import (
    ClientCreate,
    ClientRead,
    LoginRequest,
    MeResponse,
    TenantBootstrapRequest,
    TenantBootstrapResponse,
    TokenResponse,
)
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/v1")


@router.post(
    "/setup/tenants",
    response_model=TenantBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Setup"],
)
def bootstrap_tenant(
    payload: TenantBootstrapRequest,
    x_bootstrap_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Provision a tenant and its owner using an operator-held secret."""
    if not settings.bootstrap_token:
        raise HTTPException(status_code=503, detail="Provisionamento inicial está desabilitado.")
    if not x_bootstrap_token or not secrets.compare_digest(
        x_bootstrap_token, settings.bootstrap_token
    ):
        raise HTTPException(status_code=403, detail="Token de provisionamento inválido.")
    if db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug)):
        raise HTTPException(status_code=409, detail="Já existe um escritório com esse identificador.")

    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
    try:
        db.add(tenant)
        db.flush()
        owner = User(
            tenant_id=tenant.id,
            email=str(payload.owner_email).lower(),
            full_name=payload.owner_full_name,
            password_hash=hash_password(payload.owner_password),
            role="owner",
        )
        db.add(owner)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível criar o escritório.") from None

    db.refresh(tenant)
    db.refresh(owner)
    return TenantBootstrapResponse(tenant=tenant, owner=owner)


@router.post("/auth/token", response_model=TokenResponse, tags=["Authentication"])
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    tenant = db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug))
    user = None
    if tenant and tenant.status == "active":
        user = db.scalar(
            select(User).where(
                User.tenant_id == tenant.id,
                User.email == str(payload.email).lower(),
                User.is_active.is_(True),
            )
        )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Escritório, e-mail ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user, settings),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=MeResponse, tags=["Authentication"])
def read_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Escritório não encontrado.")
    return MeResponse(user=current_user, tenant=tenant)


@router.get("/clients", response_model=list[ClientRead], tags=["Clients"])
def list_clients(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Client)
            .where(Client.tenant_id == current_user.tenant_id)
            .order_by(Client.created_at.desc(), Client.id)
            .offset(offset)
            .limit(limit)
        ).all()
    )


@router.post(
    "/clients",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Clients"],
)
def create_client(
    payload: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_client = Client(
        tenant_id=current_user.tenant_id,
        legal_name=payload.legal_name,
        trade_name=payload.trade_name,
        tax_id=payload.tax_id,
        email=str(payload.email).lower() if payload.email else None,
        phone=payload.phone,
        status=payload.status,
    )
    try:
        db.add(new_client)
        db.flush()
        db.add(
            AuditLog(
                tenant_id=current_user.tenant_id,
                actor_user_id=current_user.id,
                action="client.created",
                entity_type="client",
                entity_id=new_client.id,
                details={"client_id": new_client.id},
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe um cliente com esse identificador fiscal neste escritório.",
        ) from None
    db.refresh(new_client)
    return new_client


@router.get("/clients/{client_id}", response_model=ClientRead, tags=["Clients"])
def get_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.tenant_id == current_user.tenant_id,
        )
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return client
