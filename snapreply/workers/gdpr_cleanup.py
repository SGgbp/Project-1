"""
GDPR data retention cleanup — runs daily at 3am UK time.
Deletes conversations and enquiries older than 90 days.
ICO-compliant: data minimisation principle.
"""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

RETENTION_DAYS = 90


async def run_gdpr_cleanup() -> None:
    from database.connection import AsyncSessionLocal
    from database.models import Conversation, Enquiry
    from sqlalchemy import delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    logger.info(f"Running GDPR cleanup — deleting records older than {cutoff.date().isoformat()}")

    async with AsyncSessionLocal() as db:
        conv_result = await db.execute(
            delete(Conversation).where(Conversation.updated_at < cutoff)
        )
        enq_result = await db.execute(
            delete(Enquiry).where(Enquiry.created_at < cutoff)
        )
        await db.commit()

        conv_deleted = conv_result.rowcount
        enq_deleted = enq_result.rowcount

    logger.info(
        f"GDPR cleanup complete — deleted {conv_deleted} conversation(s), "
        f"{enq_deleted} enquiry record(s)"
    )
