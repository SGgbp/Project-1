"""
Trial expiry worker — runs at 9am UK time daily.
Sends timed nudges as trial approaches/passes expiry.
Never sends the same threshold message twice (tracked in sent_notifications JSONB).
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def run_trial_expiry_checks() -> None:
    from database.connection import AsyncSessionLocal
    from database.models import Business, Subscription
    from sqlalchemy import select

    logger.info("Running trial expiry checks...")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Subscription).where(Subscription.status == "trial")
        )
        subscriptions = result.scalars().all()

        for sub in subscriptions:
            try:
                await _process_trial(sub, db)
            except Exception as e:
                logger.error(f"Trial check failed for sub {str(sub.id)[-8:]}: {e}")

    logger.info("Trial expiry checks complete")


async def _process_trial(sub, db) -> None:
    from database.models import Business
    from services.whatsapp_service import send_whatsapp_message
    from sqlalchemy import select

    if not sub.trial_ends_at:
        return

    now = datetime.now(timezone.utc)
    trial_end = sub.trial_ends_at
    if trial_end.tzinfo is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)

    days_left = (trial_end - now).days
    sent = sub.sent_notifications or {}

    biz_result = await db.execute(select(Business).where(Business.id == sub.business_id))
    business = biz_result.scalar_one_or_none()
    if not business:
        return

    async def _send_once(key: str, message: str):
        if sent.get(key):
            return
        await send_whatsapp_message(business.owner_whatsapp, message)
        sent[key] = now.isoformat()
        sub.sent_notifications = sent
        await db.commit()

    from config import settings as cfg

    if days_left == 2:
        await _send_once("2_days", (
            f"⏰ Your SnapReply trial ends in 2 days, {business.first_name}.\n\n"
            f"To keep your AI assistant running: {cfg.BASE_URL}/billing\n\n"
            f"Just £39/month (Starter) or £69/month (Growth) — cancel anytime.\n"
            f"Reply *UPGRADE* to see all options."
        ))

    elif days_left == 0:
        await _send_once("expired", (
            f"😔 Your SnapReply trial has ended, {business.first_name}.\n\n"
            f"Your AI assistant is now paused. Restart it here: {cfg.BASE_URL}/billing\n\n"
            f"We'd love to keep helping your business grow! 🚀"
        ))
        business.paused = True
        await db.commit()

    elif days_left == -3:
        await _send_once("3_days_past", (
            f"Hi {business.first_name}! Your SnapReply trial ended 3 days ago.\n\n"
            f"Ready to reactivate? {cfg.BASE_URL}/billing — takes 2 minutes."
        ))

    elif days_left == -7:
        await _send_once("7_days_past", (
            f"Last message from us, {business.first_name}! SnapReply trial expired 7 days ago.\n\n"
            f"Your account data is safe for 90 days. Reactivate anytime: {cfg.BASE_URL}/billing"
        ))
