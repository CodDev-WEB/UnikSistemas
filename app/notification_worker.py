from __future__ import annotations

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import get_settings
from app.db import SessionLocal
from app.notifications import enqueue_due_reminders, process_email_queue
from app.models import utcnow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("unik.notification_worker")
POLL_SECONDS = 60


def run_once() -> dict[str, int]:
    settings = get_settings()
    try:
        tz = ZoneInfo(settings.notification_timezone)
    except ZoneInfoNotFoundError:
        logger.exception("Fuso horário inválido em NOTIFICATION_TIMEZONE")
        raise

    with SessionLocal() as db:
        local_today = datetime.now(tz).date()
        due = enqueue_due_reminders(db, local_today, days_ahead=1)
        db.commit()
        email_result = process_email_queue(db, settings, limit=50)
        result = {
            "reminders_created": due["created"],
            "tasks_checked": due["checked"],
            "emails_sent": email_result["sent"],
            "emails_failed": email_result["failed"],
        }
        logger.info("Ciclo de notificações: %s", result)
        return result


def main() -> None:
    logger.info("Worker de notificações iniciado; SMTP habilitado=%s", get_settings().email_notifications_enabled)
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("Falha no ciclo de notificações; nova tentativa no próximo ciclo")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
