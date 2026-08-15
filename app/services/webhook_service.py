from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.db.models import WebhookEvent, DuplicateLog
from app.workers.tasks import process_webhook_event_task
from app.core.logging import logger

async def record_and_enqueue_webhook(session: AsyncSession, payload_dict: dict) -> tuple[bool, WebhookEvent | None]:
    event_id = payload_dict.get("event_id")
    event_type = payload_dict.get("event_type", "unknown")

    if not event_id:
        return False, None

    event = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        payload=payload_dict,
        processed=False
    )
    session.add(event)

    try:
        await session.commit()
        await session.refresh(event)
    except IntegrityError:
        await session.rollback()
        # Duplicate event_id received!
        logger.info("Duplicate webhook event_id received: %s", event_id)
        dup_log = DuplicateLog(
            reason="EVENT_DUPLICATE",
            event_id=event_id
        )
        session.add(dup_log)
        await session.commit()
        return True, None

    # Enqueue Celery task for background processing
    process_webhook_event_task.delay(event_id)
    return False, event
