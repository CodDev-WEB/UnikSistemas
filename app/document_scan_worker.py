from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.antivirus import scan_bytes
from app.config import Settings, get_settings
from app.db import SessionLocal
from app.document_storage import (
    load_document_for_scan,
    promote_document,
    quarantine_document,
)
from app.models import AuditLog, ClientDocument, utcnow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("unik.document_scan_worker")

POLL_SECONDS = 15
RETRY_DELAY_SECONDS = 60
STALE_SCAN_SECONDS = 300
MAX_SCAN_ATTEMPTS = 5
BATCH_SIZE = 20
Scanner = Callable[[bytes, str, int, int], str]


def _audit_scan(db: Session, document: ClientDocument, action: str, details: dict) -> None:
    db.add(
        AuditLog(
            tenant_id=document.tenant_id,
            actor_user_id=None,
            action=action,
            entity_type="client_document",
            entity_id=document.id,
            details=details,
        )
    )


def process_pending_scans(
    db: Session,
    settings: Settings,
    scanner: Scanner = scan_bytes,
    limit: int = BATCH_SIZE,
    now=None,
) -> dict[str, int]:
    """Scan queued documents; only a clean verdict moves the file to clean storage."""
    current_time = now or utcnow()
    stale_before = current_time - timedelta(seconds=STALE_SCAN_SECONDS)
    stale_documents = db.scalars(
        select(ClientDocument).where(
            ClientDocument.scan_status == "scanning",
            ClientDocument.scan_last_attempt_at.is_not(None),
            ClientDocument.scan_last_attempt_at < stale_before,
        )
    ).all()
    for stale in stale_documents:
        stale.scan_status = "pending"
        stale.scan_error = "Análise interrompida; documento reenfileirado com segurança."
    if stale_documents:
        db.commit()

    retry_before = current_time - timedelta(seconds=RETRY_DELAY_SECONDS)
    document_ids = db.scalars(
        select(ClientDocument.id)
        .where(
            ClientDocument.scan_status == "pending",
            ClientDocument.scan_attempts < MAX_SCAN_ATTEMPTS,
            or_(
                ClientDocument.scan_last_attempt_at.is_(None),
                ClientDocument.scan_last_attempt_at <= retry_before,
            ),
        )
        .order_by(ClientDocument.created_at.asc(), ClientDocument.id.asc())
        .limit(max(1, min(limit, 100)))
    ).all()

    result = {"scanned": 0, "clean": 0, "infected": 0, "failed": 0}
    for document_id in document_ids:
        document = db.scalar(
            select(ClientDocument)
            .where(
                ClientDocument.id == document_id,
                ClientDocument.scan_status == "pending",
            )
            .with_for_update(skip_locked=True)
        )
        if document is None:
            continue
        document.scan_status = "scanning"
        document.scan_attempts += 1
        document.scan_last_attempt_at = utcnow()
        attempt = document.scan_attempts
        storage_key = document.storage_key
        db.commit()

        source_area: str | None = None
        try:
            content, source_area = load_document_for_scan(settings.document_storage_path, storage_key)
            verdict = scanner(
                content,
                settings.antivirus_host,
                settings.antivirus_port,
                settings.antivirus_timeout_seconds,
            )
            if verdict not in {"clean", "infected"}:
                raise RuntimeError("O scanner retornou um resultado desconhecido.")
            if verdict == "clean":
                promote_document(settings.document_storage_path, storage_key, source_area)
            elif source_area == "clean":
                quarantine_document(settings.document_storage_path, storage_key, source_area)
        except Exception as exc:
            db.rollback()
            if source_area == "clean":
                try:
                    quarantine_document(settings.document_storage_path, storage_key, source_area)
                except OSError:
                    logger.exception("Não foi possível devolver documento %s à quarentena", document_id)
            document = db.get(ClientDocument, document_id)
            if document is None:
                continue
            document.scan_status = "error" if attempt >= MAX_SCAN_ATTEMPTS else "pending"
            document.scan_error = (str(exc) or exc.__class__.__name__)[:500]
            _audit_scan(
                db,
                document,
                "document.scan_failed",
                {"attempt": attempt, "terminal": document.scan_status == "error"},
            )
            db.commit()
            result["failed"] += 1
            logger.warning(
                "Análise falhou para documento %s (tentativa %s/%s); estado=%s",
                document_id,
                attempt,
                MAX_SCAN_ATTEMPTS,
                document.scan_status,
            )
            continue

        document = db.get(ClientDocument, document_id)
        if document is None:
            continue
        document.scan_status = verdict
        document.scan_completed_at = utcnow()
        document.scan_error = None
        _audit_scan(
            db,
            document,
            "document.scan_clean" if verdict == "clean" else "document.scan_infected",
            {"attempt": attempt},
        )
        db.commit()
        result["scanned"] += 1
        result[verdict] += 1

    return result


def main() -> None:
    logger.info("Worker antimalware iniciado; host ClamAV=%s:%s", get_settings().antivirus_host, get_settings().antivirus_port)
    while True:
        try:
            settings = get_settings()
            with SessionLocal() as db:
                stats = process_pending_scans(db, settings)
            if any(stats.values()):
                logger.info("Ciclo de análise documental: %s", stats)
        except Exception:
            logger.exception("Falha no ciclo de análise documental; nova tentativa no próximo ciclo")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
