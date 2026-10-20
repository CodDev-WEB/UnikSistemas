import secrets

from io import BytesIO
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.client_imports import canonical_tax_id, parse_client_import, validate_import_rows
from app.models import AuditLog, Client, ClientImportBatch, Tenant, User, utcnow
from app.schemas import (
    ClientCreate,
    ClientRead,
    ClientImportBatchRead,
    ClientImportHistoryRead,
    LoginRequest,
    MeResponse,
    TenantBootstrapRequest,
    TenantBootstrapResponse,
    TokenResponse,
    UserCreate,
    UserUpdate,
    UserRead,
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
    if current_user.role not in {"owner", "admin", "accountant", "assistant"}:
        raise HTTPException(status_code=403, detail="Seu perfil não permite cadastrar clientes.")

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




MANAGE_USER_ROLES = {"owner", "admin"}
VALID_STAFF_ROLES = {"admin", "accountant", "assistant", "viewer"}


def _require_user_manager(user: User) -> None:
    if user.role not in MANAGE_USER_ROLES:
        raise HTTPException(status_code=403, detail="Seu perfil não permite administrar usuários.")


def _record_user_audit(
    db: Session,
    actor: User,
    action: str,
    subject: User,
    changed_fields: list[str],
) -> None:
    db.add(
        AuditLog(
            tenant_id=actor.tenant_id,
            actor_user_id=actor.id,
            action=action,
            entity_type="user",
            entity_id=subject.id,
            details={"fields": sorted(changed_fields)},
        )
    )


@router.get("/users", response_model=list[UserRead], tags=["Users"])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_user_manager(current_user)
    return list(
        db.scalars(
            select(User)
            .where(User.tenant_id == current_user.tenant_id)
            .order_by(User.role, User.full_name, User.id)
        ).all()
    )


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_user_manager(current_user)
    if current_user.role == "admin" and payload.role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Somente o responsável do escritório pode criar administradores.",
        )

    user = User(
        tenant_id=current_user.tenant_id,
        email=str(payload.email).lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    try:
        db.add(user)
        db.flush()
        _record_user_audit(db, current_user, "user.created", user, ["email", "full_name", "role"])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe um usuário com esse e-mail neste escritório.",
        ) from None

    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead, tags=["Users"])
def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_user_manager(current_user)
    user = db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == current_user.tenant_id)
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo para atualizar.")
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Os campos enviados não podem ser nulos.")

    if user.id == current_user.id and ({"role", "is_active"} & changes.keys()):
        raise HTTPException(
            status_code=403,
            detail="Você não pode alterar o próprio perfil nem desativar o próprio acesso.",
        )
    if user.role == "owner" and user.id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="O usuário responsável não pode ser alterado por outro usuário.",
        )
    if current_user.role == "admin":
        if user.role == "admin" and user.id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Administradores não podem alterar outros administradores.",
            )
        if changes.get("role") == "admin":
            raise HTTPException(
                status_code=403,
                detail="Somente o responsável do escritório pode atribuir o perfil administrador.",
            )

    old_active = user.is_active
    for field, value in changes.items():
        setattr(user, field, value)

    if "is_active" in changes and changes["is_active"] != old_active:
        action = "user.activated" if changes["is_active"] else "user.deactivated"
    else:
        action = "user.updated"

    try:
        _record_user_audit(db, current_user, action, user, list(changes.keys()))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível atualizar o usuário.") from None

    db.refresh(user)
    return user


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



CLIENT_EDITOR_ROLES = {"owner", "admin", "accountant", "assistant"}
MAX_IMPORT_FILE_BYTES = 5 * 1024 * 1024


def _require_client_editor(user: User) -> None:
    if user.role not in CLIENT_EDITOR_ROLES:
        raise HTTPException(status_code=403, detail="Seu perfil não permite importar clientes.")


def _serialize_import_batch(batch: ClientImportBatch) -> dict:
    return {
        "id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "total_rows": batch.total_rows,
        "imported_count": batch.imported_count,
        "rows": batch.preview_rows,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "confirmed_at": batch.confirmed_at.isoformat() if batch.confirmed_at else None,
    }


@router.post(
    "/imports/clients/preview",
    response_model=ClientImportBatchRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Imports"],
)
async def preview_client_import(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse and validate a CSV/XLSX without creating any clients."""
    _require_client_editor(current_user)
    if not file.filename:
        raise HTTPException(status_code=422, detail="Selecione um arquivo para importar.")

    filename = PurePosixPath(file.filename.replace("\\", "/")).name[:255]
    try:
        content = await file.read(MAX_IMPORT_FILE_BYTES + 1)
        if len(content) > MAX_IMPORT_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="O arquivo ultrapassa o limite de 5 MiB.",
            )
        try:
            source_rows = parse_client_import(filename, content)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    finally:
        await file.close()

    existing_ids = {
        key
        for value in db.scalars(
            select(Client.tax_id).where(
                Client.tenant_id == current_user.tenant_id,
                Client.tax_id.is_not(None),
            )
        ).all()
        if (key := canonical_tax_id(value))
    }
    preview_rows = validate_import_rows(source_rows, existing_ids)
    batch = ClientImportBatch(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        filename=filename,
        status="ready" if all(not row["errors"] for row in preview_rows) else "invalid",
        preview_rows=preview_rows,
        total_rows=len(preview_rows),
        imported_count=0,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return _serialize_import_batch(batch)





@router.get(
    "/imports/clients",
    response_model=list[ClientImportHistoryRead],
    tags=["Imports"],
)
def list_client_import_history(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return import batches for the currently authenticated office only."""
    _require_client_editor(current_user)
    records = db.execute(
        select(ClientImportBatch, User.full_name)
        .outerjoin(User, User.id == ClientImportBatch.created_by_user_id)
        .where(ClientImportBatch.tenant_id == current_user.tenant_id)
        .order_by(ClientImportBatch.created_at.desc(), ClientImportBatch.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        {
            "id": batch.id,
            "filename": batch.filename,
            "status": batch.status,
            "total_rows": batch.total_rows,
            "imported_count": batch.imported_count,
            "created_by_name": creator_name,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "confirmed_at": batch.confirmed_at.isoformat() if batch.confirmed_at else None,
        }
        for batch, creator_name in records
    ]


@router.get("/imports/client-template.csv", tags=["Imports"])
def download_client_import_csv_template(
    current_user: User = Depends(get_current_user),
):
    """Download a minimal CSV template for client imports."""
    _require_client_editor(current_user)
    content = (
        "\ufeffRazão Social;Nome Fantasia;CNPJ/CPF;E-mail;Telefone;Status\r\n"
    )
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="unik-modelo-clientes.csv"'},
    )


@router.get("/imports/client-template.xlsx", tags=["Imports"])
def download_client_import_xlsx_template(
    current_user: User = Depends(get_current_user),
):
    """Download an Excel template with a clients tab and usage instructions."""
    _require_client_editor(current_user)
    workbook = Workbook()
    clients_sheet = workbook.active
    clients_sheet.title = "Clientes"
    headers = ["Razão Social", "Nome Fantasia", "CNPJ/CPF", "E-mail", "Telefone", "Status"]
    clients_sheet.append(headers)
    clients_sheet.freeze_panes = "A2"
    clients_sheet.auto_filter.ref = "A1:F1"
    widths = {"A": 34, "B": 28, "C": 20, "D": 32, "E": 20, "F": 16}
    for column, width in widths.items():
        clients_sheet.column_dimensions[column].width = width
    for cell in clients_sheet[1]:
        cell.font = __import__("openpyxl").styles.Font(bold=True, color="FFFFFF")
        cell.fill = __import__("openpyxl").styles.PatternFill("solid", fgColor="5C55B7")
    clients_sheet.column_dimensions["C"].number_format = "@"

    instructions = workbook.create_sheet("Instruções")
    instructions.append(["Como usar o modelo de clientes"])
    instructions.append(["1. Preencha uma linha para cada cliente na aba Clientes."])
    instructions.append(["2. Razão Social é obrigatória; mantenha a primeira linha de títulos."])
    instructions.append(["3. CNPJ/CPF deve ser formatado como texto para preservar zeros à esquerda."])
    instructions.append(["4. Status aceita Ativo ou Arquivado; se vazio, será considerado Ativo."])
    instructions.append(["5. Salve como .xlsx e envie pelo menu Importações para revisar a prévia."])
    instructions.column_dimensions["A"].width = 105
    instructions["A1"].font = __import__("openpyxl").styles.Font(bold=True, size=14)
    workbook_buffer = BytesIO()
    workbook.save(workbook_buffer)
    workbook.close()
    return Response(
        content=workbook_buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="unik-modelo-clientes.xlsx"'},
    )


@router.get("/imports/clients/{batch_id}", response_model=ClientImportBatchRead, tags=["Imports"])
def read_client_import_preview(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_client_editor(current_user)
    batch = db.scalar(
        select(ClientImportBatch).where(
            ClientImportBatch.id == batch_id,
            ClientImportBatch.tenant_id == current_user.tenant_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    return _serialize_import_batch(batch)


@router.delete(
    "/imports/clients/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Imports"],
)
def discard_client_import(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a pending import preview without touching client records."""
    _require_client_editor(current_user)
    batch = db.scalar(
        select(ClientImportBatch).where(
            ClientImportBatch.id == batch_id,
            ClientImportBatch.tenant_id == current_user.tenant_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    if batch.status == "confirmed":
        raise HTTPException(status_code=409, detail="A importação confirmada não pode ser descartada.")
    batch.status = "discarded"
    batch.preview_rows = []
    db.add(
        AuditLog(
            tenant_id=current_user.tenant_id,
            actor_user_id=current_user.id,
            action="clients.import.discarded",
            entity_type="client_import",
            entity_id=batch.id,
            details={"filename": batch.filename},
        )
    )
    db.commit()


@router.post(
    "/imports/clients/{batch_id}/confirm",
    response_model=ClientImportBatchRead,
    tags=["Imports"],
)
def confirm_client_import(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist all rows atomically after a valid preview and explicit confirmation."""
    _require_client_editor(current_user)
    batch = db.scalar(
        select(ClientImportBatch)
        .where(
            ClientImportBatch.id == batch_id,
            ClientImportBatch.tenant_id == current_user.tenant_id,
        )
        .with_for_update()
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    if batch.status == "confirmed":
        raise HTTPException(status_code=409, detail="Esta importação já foi confirmada.")
    if batch.status != "ready" or any(row.get("errors") for row in batch.preview_rows):
        raise HTTPException(
            status_code=409,
            detail="A prévia possui pendências. Corrija o arquivo e envie novamente antes de confirmar.",
        )

    existing_ids = {
        key
        for value in db.scalars(
            select(Client.tax_id).where(
                Client.tenant_id == current_user.tenant_id,
                Client.tax_id.is_not(None),
            )
        ).all()
        if (key := canonical_tax_id(value))
    }
    conflicts = [
        row for row in batch.preview_rows
        if (key := canonical_tax_id(row.get("tax_id"))) and key in existing_ids
    ]
    if conflicts:
        updated_rows = [dict(row) for row in batch.preview_rows]
        for row in updated_rows:
            key = canonical_tax_id(row.get("tax_id"))
            if key and key in existing_ids:
                row["errors"] = sorted(set([*row.get("errors", []), "CNPJ/CPF já cadastrado neste escritório."]))
        batch.preview_rows = updated_rows
        batch.status = "invalid"
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="A base mudou após a prévia. Há CNPJ/CPF que já foi cadastrado; revise as linhas sinalizadas.",
        )

    try:
        clients = [
            Client(
                tenant_id=current_user.tenant_id,
                legal_name=row["legal_name"],
                trade_name=row.get("trade_name"),
                tax_id=row.get("tax_id"),
                email=row.get("email"),
                phone=row.get("phone"),
                status=row.get("status") or "active",
            )
            for row in batch.preview_rows
        ]
        db.add_all(clients)
        db.flush()
        batch.status = "confirmed"
        batch.imported_count = len(clients)
        batch.confirmed_at = utcnow()
        # Client data now lives in the clients table; remove the copy stored for preview.
        batch.preview_rows = []
        db.add(
            AuditLog(
                tenant_id=current_user.tenant_id,
                actor_user_id=current_user.id,
                action="clients.imported",
                entity_type="client_import",
                entity_id=batch.id,
                details={"imported_count": len(clients), "filename": batch.filename},
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Um ou mais identificadores fiscais já existem. Nenhum cliente foi importado; envie a base atualizada.",
        ) from None
    db.refresh(batch)
    return _serialize_import_batch(batch)
