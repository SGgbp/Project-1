"""
Daily digest worker — runs at 7pm UK time.
Sends each active business owner a summary of the day's activity.
"""
import logging
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)


async def send_all_daily_digests() -> None:
    from database.connection import AsyncSessionLocal
    from database.models import Business, Subscription, Enquiry, Booking, DailyAnalytics
    from services.whatsapp_service import send_whatsapp_message
    from sqlalchemy import select, func, and_

    logger.info("Running daily digest...")
    today = date.today().isoformat()
    today_start = f"{today}T00:00:00"
    today_end = f"{today}T23:59:59"

    async with AsyncSessionLocal() as db:
        # Get all active businesses with active or trial subscriptions
        result = await db.execute(
            select(Business)
            .join(Subscription, Subscription.business_id == Business.id)
            .where(
                Business.active == True,
                Subscription.status.in_(["active", "trial"]),
            )
        )
        businesses = result.scalars().all()

        for business in businesses:
            try:
                await _send_digest_for_business(business, today, today_start, today_end, db)
            except Exception as e:
                logger.error(f"Digest failed for business {str(business.id)[-8:]}: {e}")

    logger.info(f"Daily digest complete — processed {len(businesses)} businesses")


async def _send_digest_for_business(business, today: str, today_start: str, today_end: str, db) -> None:
    from database.models import Enquiry, Booking, DailyAnalytics
    from services.whatsapp_service import send_whatsapp_message
    from sqlalchemy import select, func

    # Count today's enquiries
    e_result = await db.execute(
        select(func.count(Enquiry.id)).where(
            Enquiry.business_id == business.id,
            Enquiry.created_at >= today_start,
            Enquiry.created_at <= today_end,
        )
    )
    enquiries = e_result.scalar() or 0

    # Count today's bookings
    b_result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.business_id == business.id,
            Booking.preferred_date == today,
        )
    )
    bookings = b_result.scalar() or 0

    # Skip if nothing happened
    if enquiries == 0 and bookings == 0:
        return

    # Average reply time
    avg_result = await db.execute(
        select(func.avg(Enquiry.seconds_to_reply)).where(
            Enquiry.business_id == business.id,
            Enquiry.created_at >= today_start,
            Enquiry.reply_sent == True,
        )
    )
    avg_seconds = int(avg_result.scalar() or 0)

    # Build message
    if bookings > 0:
        est_revenue = bookings * 60  # Rough average job value
        msg = (
            f"📈 *SnapReply daily summary*\n\n"
            f"📩 Enquiries caught: {enquiries}\n"
            f"📅 Bookings made: {bookings} 🎉\n"
            f"💰 Est. revenue: £{est_revenue}\n"
            f"⚡ Avg reply time: {avg_seconds}s\n\n"
            f"Text *BOOKINGS* to see full list."
        )
    else:
        msg = (
            f"📈 *SnapReply daily summary*\n\n"
            f"📩 Enquiries caught today: {enquiries}\n"
            f"💬 Conversations started: {enquiries}\n"
            f"⚡ Avg reply time: {avg_seconds}s\n\n"
            f"Text *BOOKINGS* to see conversations."
        )

    await send_whatsapp_message(business.owner_whatsapp, msg)

    # Upsert daily analytics
    existing = await db.execute(
        select(DailyAnalytics).where(
            DailyAnalytics.business_id == business.id,
            DailyAnalytics.date == today,
        )
    )
    analytics = existing.scalar_one_or_none()
    if analytics:
        analytics.enquiries_count = enquiries
        analytics.bookings_count = bookings
        analytics.avg_reply_seconds = avg_seconds
    else:
        db.add(DailyAnalytics(
            business_id=business.id,
            date=today,
            enquiries_count=enquiries,
            bookings_count=bookings,
            avg_reply_seconds=avg_seconds,
        ))
    await db.commit()
