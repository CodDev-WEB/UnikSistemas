from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AntivirusHealth, ClientDocument, Notification

ANTIVIRUS_STATUSES = ("unknown", "healthy", "unavailable", "signatures_stale")
SCAN_STATUSES = ("pending", "scanning", "clean", "infected", "error")
EMAIL_STATUSES = ("pending", "sent", "failed")


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _timestamp(value: datetime | None) -> int:
    normalized = _utc(value)
    return int(normalized.timestamp()) if normalized is not None else 0


def _count(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def _sample(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    if labels:
        rendered_labels = ",".join(f'{key}="{label}"' for key, label in labels.items())
        return f"{name}{{{rendered_labels}}} {value}"
    return f"{name} {value}"


def render_prometheus_metrics(db: Session, now: datetime | None = None) -> str:
    """Render low-cardinality operational metrics without tenant or customer identifiers."""
    current = _utc(now or datetime.now(UTC))
    assert current is not None

    health = db.get(AntivirusHealth, "clamav")
    health_status = health.status if health and health.status in ANTIVIRUS_STATUSES else "unknown"
    signature_date = _utc(health.signature_database_date) if health else None
    signature_age_known = int(signature_date is not None)
    signature_age = max(0, int((current - signature_date).total_seconds())) if signature_date else 0

    lines = [
        "# HELP unik_antivirus_health_status Current ClamAV health state; exactly one status is 1.",
        "# TYPE unik_antivirus_health_status gauge",
    ]
    for status in ANTIVIRUS_STATUSES:
        lines.append(
            _sample("unik_antivirus_health_status", int(status == health_status), {"status": status})
        )

    lines.extend(
        [
            "# HELP unik_antivirus_signature_database_age_seconds Age of the loaded ClamAV signature database.",
            "# TYPE unik_antivirus_signature_database_age_seconds gauge",
            _sample("unik_antivirus_signature_database_age_seconds", signature_age),
            "# HELP unik_antivirus_signature_database_known Whether a signature database date is available.",
            "# TYPE unik_antivirus_signature_database_known gauge",
            _sample("unik_antivirus_signature_database_known", signature_age_known),
            "# HELP unik_antivirus_last_success_timestamp_seconds Unix timestamp of the last successful ClamAV check; 0 means unknown.",
            "# TYPE unik_antivirus_last_success_timestamp_seconds gauge",
            _sample(
                "unik_antivirus_last_success_timestamp_seconds",
                _timestamp(health.last_success_at) if health else 0,
            ),
            "# HELP unik_antivirus_last_check_timestamp_seconds Unix timestamp of the last ClamAV health check; 0 means unknown.",
            "# TYPE unik_antivirus_last_check_timestamp_seconds gauge",
            _sample("unik_antivirus_last_check_timestamp_seconds", _timestamp(health.checked_at) if health else 0),
            "# HELP unik_antivirus_last_cleanup_timestamp_seconds Unix timestamp of the last quarantine cleanup cycle; 0 means unknown.",
            "# TYPE unik_antivirus_last_cleanup_timestamp_seconds gauge",
            _sample("unik_antivirus_last_cleanup_timestamp_seconds", _timestamp(health.last_cleanup_at) if health else 0),
        ]
    )

    scan_counts = dict(
        db.execute(
            select(ClientDocument.scan_status, func.count(ClientDocument.id)).group_by(
                ClientDocument.scan_status
            )
        ).all()
    )
    lines.extend(
        [
            "# HELP unik_documents_scan_status_total Number of documents in each antimalware scan state.",
            "# TYPE unik_documents_scan_status_total gauge",
        ]
    )
    for status in SCAN_STATUSES:
        lines.append(
            _sample("unik_documents_scan_status_total", int(scan_counts.get(status, 0)), {"status": status})
        )

    infected_waiting = _count(
        db,
        select(func.count(ClientDocument.id)).where(
            ClientDocument.scan_status == "infected",
            ClientDocument.quarantine_purged_at.is_(None),
        ),
    )
    lines.extend(
        [
            "# HELP unik_documents_infected_payloads_waiting_retention_total Infected file payloads still awaiting retention cleanup.",
            "# TYPE unik_documents_infected_payloads_waiting_retention_total gauge",
            _sample("unik_documents_infected_payloads_waiting_retention_total", infected_waiting),
        ]
    )

    stale_cutoff = current - timedelta(minutes=5)
    stale_scans = _count(
        db,
        select(func.count(ClientDocument.id)).where(
            ClientDocument.scan_status == "scanning",
            ClientDocument.scan_last_attempt_at.is_not(None),
            ClientDocument.scan_last_attempt_at <= stale_cutoff,
        ),
    )
    lines.extend(
        [
            "# HELP unik_documents_stale_scans_total Documents marked scanning without a recent attempt.",
            "# TYPE unik_documents_stale_scans_total gauge",
            _sample("unik_documents_stale_scans_total", stale_scans),
        ]
    )

    email_counts = dict(
        db.execute(
            select(Notification.email_status, func.count(Notification.id)).group_by(
                Notification.email_status
            )
        ).all()
    )
    lines.extend(
        [
            "# HELP unik_notification_email_status_total Notifications in each SMTP queue state.",
            "# TYPE unik_notification_email_status_total gauge",
        ]
    )
    for status in EMAIL_STATUSES:
        lines.append(
            _sample("unik_notification_email_status_total", int(email_counts.get(status, 0)), {"status": status})
        )

    return "\n".join(lines) + "\n"
