from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.antivirus import ClamAVInfo, get_clamav_info, signature_status
from app.config import Settings
from app.document_storage import purge_quarantined_document
from app.models import AntivirusHealth, AuditLog, ClientDocument, User, utcnow
from app.notifications import queue_notification

logger = logging.getLogger("unik.antivirus_operations")
SCANNER_ID = "clamav"
ScannerProbe = Callable[[str, int, int], ClamAVInfo]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _manager_users(db: Session) -> list[User]:
    return db.scalars(
        select(User).where(
            User.is_active.is_(True),
            User.role.in_(("owner", "admin")),
        )
    ).all()


def _queue_health_notifications(
    db: Session,
    users: list[User],
    *,
    event_type: str,
    event_key: str,
    title: str,
    message: str,
) -> int:
    queued = 0
    for user in users:
        item = queue_notification(
            db,
            tenant_id=user.tenant_id,
            recipient_user_id=user.id,
            event_key=event_key,
            event_type=event_type,
            title=title,
            message=message,
            entity_type="antivirus_service",
            entity_id=SCANNER_ID,
            action_url="/notifications",
        )
        queued += int(item is not None)
    return queued


def refresh_antivirus_health(
    db: Session,
    settings: Settings,
    probe: ScannerProbe = get_clamav_info,
    now: datetime | None = None,
) -> dict:
    """Persist scanner availability/freshness and alert owners/admins on state transitions."""
    current = _utc(now or utcnow())
    health = db.get(AntivirusHealth, SCANNER_ID)
    if health is None:
        health = AntivirusHealth(id=SCANNER_ID, status="unknown")
        db.add(health)
        db.flush()

    previous_status = health.status
    previous_incident_key = (
        health.incident_started_at.isoformat()
        if health.incident_started_at is not None
        else current.isoformat()
    )
    database_version = None
    database_date = None
    try:
        info = probe(settings.antivirus_host, settings.antivirus_port, settings.antivirus_timeout_seconds)
        database_version = info.database_version
        database_date = _utc(info.database_date)
        new_status, status_error = signature_status(
            database_date,
            current,
            settings.antivirus_signature_max_age_hours,
        )
    except Exception:
        new_status = "unavailable"
        status_error = "Não foi possível confirmar a disponibilidade e a versão do ClamAV."
        logger.warning("Não foi possível consultar o ClamAV; a fila documental ficará bloqueada.")

    health.status = new_status
    health.checked_at = current
    health.signature_database_version = database_version
    health.signature_database_date = database_date
    health.last_error = status_error
    if new_status == "healthy":
        health.last_success_at = current
        health.incident_started_at = None
    elif previous_status == "healthy" or health.incident_started_at is None:
        health.incident_started_at = current

    users = _manager_users(db) if new_status != previous_status else []
    incident_key = (
        health.incident_started_at.isoformat()
        if health.incident_started_at is not None
        else current.isoformat()
    )
    if new_status != "healthy" and new_status != previous_status:
        if new_status == "signatures_stale":
            title = "Assinaturas antimalware desatualizadas"
            message = (
                "O ClamAV está respondendo, mas a atualidade das assinaturas não foi aprovada. "
                "Novos documentos permanecerão em quarentena até que as assinaturas sejam atualizadas."
            )
        else:
            title = "Scanner antimalware indisponível"
            message = (
                "Não foi possível confirmar o estado do ClamAV. A análise de documentos foi pausada "
                "e novos arquivos permanecerão em quarentena."
            )
        _queue_health_notifications(
            db,
            users,
            event_type="antivirus_alert",
            event_key=f"antivirus_alert:{incident_key}:{new_status}",
            title=title,
            message=message,
        )
    elif new_status == "healthy" and previous_status not in {"healthy", "unknown"}:
        _queue_health_notifications(
            db,
            users,
            event_type="antivirus_recovered",
            event_key=f"antivirus_recovered:{previous_incident_key}",
            title="Scanner antimalware recuperado",
            message=(
                "O ClamAV voltou a responder com assinaturas dentro do limite configurado. "
                "A fila de documentos em quarentena voltou a ser processada."
            ),
        )

    db.commit()
    return {
        "status": health.status,
        "checked_at": health.checked_at.isoformat() if health.checked_at else None,
        "signature_database_version": health.signature_database_version,
        "signature_database_date": (
            health.signature_database_date.isoformat() if health.signature_database_date else None
        ),
        "last_error": health.last_error,
        "last_success_at": health.last_success_at.isoformat() if health.last_success_at else None,
    }


def cleanup_expired_infected_documents(
    db: Session,
    settings: Settings,
    now: datetime | None = None,
    limit: int = 200,
    force: bool = False,
) -> dict[str, int | bool]:
    """Delete infected payloads after the retention period; keep metadata and audit history."""
    current = _utc(now or utcnow())
    health = db.get(AntivirusHealth, SCANNER_ID)
    if health is None:
        return {"purged": 0, "failed": 0, "remaining": 0, "skipped": True}

    interval = timedelta(hours=settings.antivirus_cleanup_interval_hours)
    if not force and health.last_cleanup_at is not None:
        if current - _utc(health.last_cleanup_at) < interval:
            return {"purged": 0, "failed": 0, "remaining": 0, "skipped": True}

    retention = timedelta(days=settings.antivirus_infected_retention_days)
    cutoff = current - retention
    criteria = (
        ClientDocument.scan_status == "infected",
        ClientDocument.quarantine_purged_at.is_(None),
        ClientDocument.scan_completed_at.is_not(None),
        ClientDocument.scan_completed_at <= cutoff,
    )
    candidates = db.scalars(
        select(ClientDocument)
        .where(*criteria)
        .order_by(ClientDocument.scan_completed_at.asc(), ClientDocument.id.asc())
        .limit(max(1, min(limit, 1000)))
    ).all()
    purged = 0
    failed = 0
    for document in candidates:
        try:
            purge_quarantined_document(settings.document_storage_path, document.storage_key)
        except OSError:
            failed += 1
            logger.warning("Falha ao remover arquivo infectado da quarentena; documento=%s", document.id)
            continue
        document.quarantine_purged_at = current
        db.add(
            AuditLog(
                tenant_id=document.tenant_id,
                actor_user_id=None,
                action="document.quarantine_purged",
                entity_type="client_document",
                entity_id=document.id,
                details={"retention_days": settings.antivirus_infected_retention_days},
            )
        )
        purged += 1

    db.flush()
    remaining = int(db.scalar(select(func.count(ClientDocument.id)).where(*criteria)) or 0)
    if remaining and failed == 0 and len(candidates) >= limit:
        health.last_cleanup_at = current - interval - timedelta(seconds=1)
    elif failed:
        health.last_cleanup_at = current - interval + timedelta(minutes=5)
    else:
        health.last_cleanup_at = current
    db.commit()
    return {"purged": purged, "failed": failed, "remaining": remaining, "skipped": False}
