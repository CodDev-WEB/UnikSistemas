from __future__ import annotations

import smtplib
import ssl
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Client, ClientTask, Notification, User, utcnow


def queue_notification(
    db: Session,
    *,
    tenant_id: str,
    recipient_user_id: str,
    event_key: str,
    event_type: str,
    title: str,
    message: str,
    entity_type: str,
    entity_id: str,
    action_url: str | None = None,
) -> Notification | None:
    """Add an idempotent in-app notification and email-outbox record."""
    existing_id = db.scalar(
        select(Notification.id).where(
            Notification.tenant_id == tenant_id,
            Notification.recipient_user_id == recipient_user_id,
            Notification.event_key == event_key,
        )
    )
    if existing_id:
        return None

    notification = Notification(
        tenant_id=tenant_id,
        recipient_user_id=recipient_user_id,
        event_key=event_key,
        event_type=event_type,
        title=title,
        message=message[:1500],
        entity_type=entity_type,
        entity_id=entity_id,
        action_url=action_url,
        is_read=False,
        email_status="pending",
        email_attempts=0,
        email_queued_at=utcnow(),
    )
    db.add(notification)
    return notification


def notification_email_is_ready(settings: Settings) -> bool:
    return bool(
        settings.email_notifications_enabled
        and settings.smtp_host
        and settings.smtp_from_email
    )


def _send_email(notification: Notification, recipient: User, settings: Settings) -> None:
    if not notification_email_is_ready(settings):
        raise RuntimeError("O envio de e-mail está desabilitado ou sem configuração SMTP completa.")

    message = EmailMessage()
    message["Subject"] = f"[UnikSistemas] {notification.title}"
    message["From"] = str(settings.smtp_from_email)
    message["To"] = recipient.email
    body = (
        f"Olá, {recipient.full_name}.\n\n"
        f"{notification.message}\n\n"
        "Acesse o UnikSistemas para consultar os detalhes."
    )
    if settings.app_base_url and notification.action_url:
        base_url = settings.app_base_url.rstrip("/")
        body += f"\n\nAcessar: {base_url}{notification.action_url}"
    message.set_content(body)

    timeout = 10
    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=timeout,
            context=ssl.create_default_context(),
        ) as smtp:
            smtp.ehlo()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
        smtp.ehlo()
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


def process_email_queue(
    db: Session,
    settings: Settings,
    limit: int = 50,
    now: datetime | None = None,
) -> dict[str, int]:
    """Send only fresh messages; old backlog is expired and requires explicit operator retry."""
    if not notification_email_is_ready(settings):
        return {"sent": 0, "failed": 0, "skipped": 0, "expired": 0}

    current_time = now or utcnow()
    cutoff = current_time - timedelta(hours=settings.email_queue_max_age_hours)
    batch_limit = max(1, min(limit, 200))

    # A notification created while SMTP was disabled must not be sent weeks later merely
    # because SMTP is switched on. Mark stale records for explicit admin approval first.
    expired_items = db.scalars(
        select(Notification)
        .where(
            Notification.email_status == "pending",
            Notification.email_queued_at < cutoff,
        )
        .order_by(Notification.email_queued_at.asc(), Notification.id.asc())
        .limit(batch_limit)
    ).all()
    for item in expired_items:
        item.email_status = "failed"
        item.email_last_error = "fila_expirada_requer_reenvio_manual"
    if expired_items:
        db.commit()

    notifications = db.scalars(
        select(Notification)
        .where(
            Notification.email_status == "pending",
            Notification.email_queued_at >= cutoff,
        )
        .order_by(Notification.email_queued_at.asc(), Notification.id.asc())
        .limit(batch_limit)
    ).all()

    sent = 0
    failed = 0
    skipped = 0
    for item in notifications:
        recipient = db.scalar(
            select(User).where(
                User.id == item.recipient_user_id,
                User.tenant_id == item.tenant_id,
                User.is_active.is_(True),
            )
        )
        item.email_attempts += 1
        if recipient is None:
            item.email_status = "failed"
            item.email_last_error = "destinatario_indisponivel"
            failed += 1
            db.commit()
            continue
        try:
            _send_email(item, recipient, settings)
        except Exception as exc:
            item.email_status = "failed"
            item.email_last_error = type(exc).__name__[:500]
            failed += 1
        else:
            item.email_status = "sent"
            item.email_sent_at = utcnow()
            item.email_last_error = None
            sent += 1
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {"sent": sent, "failed": failed, "skipped": skipped, "expired": len(expired_items)}


def enqueue_due_reminders(
    db: Session, today: date, days_ahead: int = 1, tenant_id: str | None = None
) -> dict[str, int]:
    """Create at most one reminder per user/task/day for open or received work."""
    from datetime import timedelta

    cutoff = today + timedelta(days=max(0, min(days_ahead, 7)))
    statement = (
        select(ClientTask, Client.legal_name, User)
        .join(
            Client,
            (Client.id == ClientTask.client_id) & (Client.tenant_id == ClientTask.tenant_id),
        )
        .join(
            User,
            (User.id == ClientTask.assigned_to_user_id) & (User.tenant_id == ClientTask.tenant_id),
        )
        .where(
            ClientTask.status.in_(("open", "received")),
            ClientTask.due_date.is_not(None),
            ClientTask.due_date <= cutoff,
            User.is_active.is_(True),
        )
    )
    if tenant_id is not None:
        statement = statement.where(ClientTask.tenant_id == tenant_id)
    rows = db.execute(
        statement.order_by(ClientTask.due_date.asc(), ClientTask.id.asc())
    ).all()

    created = 0
    for task, client_name, user in rows:
        due_date = task.due_date
        if due_date < today:
            title = "Pendência vencida"
            due_phrase = "está vencida"
        elif due_date == today:
            title = "Pendência vence hoje"
            due_phrase = "vence hoje"
        else:
            title = "Pendência vence amanhã"
            due_phrase = "vence amanhã"
        message = (
            f"A pendência “{task.title}” de {client_name} {due_phrase} "
            f"({due_date.strftime('%d/%m/%Y')})."
        )
        notification = queue_notification(
            db,
            tenant_id=task.tenant_id,
            recipient_user_id=user.id,
            event_key=f"task_due:{task.id}:{today.isoformat()}",
            event_type="task_due",
            title=title,
            message=message,
            entity_type="client_task",
            entity_id=task.id,
            action_url="/tasks",
        )
        if notification:
            created += 1
    return {"created": created, "checked": len(rows)}


def notification_queue_counts(db: Session, tenant_id: str) -> dict[str, int]:
    pending = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.email_status == "pending",
        )
    ) or 0
    failed = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.email_status == "failed",
        )
    ) or 0
    expired = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.email_status == "failed",
            Notification.email_last_error == "fila_expirada_requer_reenvio_manual",
        )
    ) or 0
    return {"pending": int(pending), "failed": int(failed), "expired": int(expired)}
