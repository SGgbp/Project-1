"""
Monday morning ROI report — runs 8am UK time every Monday.
The single most important retention feature: owners who see their ROI never cancel.
"""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

AVG_JOB_VALUE = {
    "driving_instructor": 35,
    "beautician": 45,
    "personal_trainer": 50,
    "tattoo_artist": 150,
    "dog_groomer": 55,
    "tutor": 40,
    "cleaner": 120,
    "photographer": 300,
    "hairdresser": 60,
    "other": 60,
}

PLAN_MONTHLY_PRICE = {
    "starter": 39,
    "growth": 69,
    "pro": 119,
}



async def send_all_monday_reports() -> None:
    from database.connection import AsyncSessionLocal
    from database.models import Business, Subscription
    from sqlalchemy import select

    logger.info("Running Monday ROI reports...")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business)
            .join(Subscription, Subscription.business_id == Business.id)
            .where(
                Business.active == True,
                Business.plan.in_(["growth", "pro"]),
                Subscription.status.in_(["active", "trial"]),
            )
        )
        businesses = result.scalars().all()

        for business in businesses:
            try:
                await _send_monday_report(business, db)
            except Exception as e:
                logger.error(f"Monday report failed for {str(business.id)[-8:]}: {e}")

    logger.info(f"Monday reports complete — {len(businesses)} sent")


async def _send_monday_report(business, db) -> None:
    from database.models import Enquiry, Booking
    from services.whatsapp_service import send_whatsapp_message
    from sqlalchemy import select, func

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    enquiries_result = await db.execute(
        select(func.count(Enquiry.id)).where(
            Enquiry.business_id == business.id,
            Enquiry.created_at >= week_ago,
        )
    )
    total_enquiries = enquiries_result.scalar() or 0

    bookings_result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.business_id == business.id,
            Booking.created_at >= week_ago,
        )
    )
    total_bookings = bookings_result.scalar() or 0

    # Track consecutive quiet weeks in DB
    if total_bookings == 0:
        business.consecutive_quiet_weeks = (business.consecutive_quiet_weeks or 0) + 1
    else:
        business.consecutive_quiet_weeks = 0
    await db.commit()

    # Two or more consecutive quiet weeks — send proactive help message
    if (business.consecutive_quiet_weeks or 0) >= 2:
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"Hey {business.first_name}, quiet week — are you getting many calls? 📞\n\n"
            f"Reply *TIPS* for ideas to drive more enquiries to your SnapReply number."
        )
        return

    avg_job_value = AVG_JOB_VALUE.get(business.business_type, 60)
    estimated_revenue = total_bookings * avg_job_value
    monthly_price = PLAN_MONTHLY_PRICE.get(business.plan, 69)
    weekly_cost = monthly_price / 4.3
    roi_multiple = round(estimated_revenue / weekly_cost, 1) if weekly_cost > 0 else 0

    msg = (
        f"📊 *Your SnapReply week in numbers:*\n\n"
        f"📩 Enquiries caught: {total_enquiries}\n"
        f"💬 Conversations started: {total_enquiries}\n"
        f"📅 Bookings made: {total_bookings}\n"
        f"💰 Est. revenue recovered: £{estimated_revenue}\n"
        f"🚀 SnapReply paid for itself *{roi_multiple}x* this week.\n\n"
        f"Have a great week, {business.first_name}!"
    )
    await send_whatsapp_message(business.owner_whatsapp, msg)
