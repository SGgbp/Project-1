"""
Automated Google Review requests — Pro tier only.
Sends a WhatsApp to the customer 2 hours after a booking is marked complete.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List

logger = logging.getLogger(__name__)

# In-process queue: list of {booking_id, scheduled_time}
_review_queue: List[dict] = []


def schedule_review_request(booking_id: str) -> None:
    """Add a booking to the review request queue, scheduled for 2 hours from now."""
    scheduled_time = datetime.now(timezone.utc) + timedelta(hours=2)
    _review_queue.append({
        "booking_id": booking_id,
        "scheduled_time": scheduled_time,
    })
    logger.info(f"Review request scheduled for booking {booking_id[-8:]} at {scheduled_time.isoformat()}")


async def process_review_queue() -> None:
    """
    Called by APScheduler every 15 minutes.
    Sends pending review requests that are due.
    """
    now = datetime.now(timezone.utc)
    pending = [item for item in _review_queue if item["scheduled_time"] <= now]

    for item in pending:
        success = await send_review_request(item["booking_id"])
        if success or True:  # Remove from queue regardless (avoid infinite retry spam)
            _review_queue.remove(item)


async def send_review_request(booking_id: str) -> bool:
    """
    Send a Google Review WhatsApp to the customer.
    Only fires if: business.plan == "pro" AND booking.status == "completed".
    Returns True on success.
    """
    from database.connection import AsyncSessionLocal
    from database.models import Booking, Business, OwnerCommand
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Booking).where(Booking.id == booking_id))
        booking = result.scalar_one_or_none()
        if not booking:
            logger.warning(f"Review: booking {booking_id} not found")
            return False

        if booking.status != "completed":
            logger.info(f"Review: booking {booking_id[-8:]} not completed — skipping")
            return False

        biz_result = await db.execute(select(Business).where(Business.id == booking.business_id))
        business = biz_result.scalar_one_or_none()
        if not business or not business.is_pro:
            return False

        # Build review URL
        if business.google_place_id:
            review_url = f"https://maps.google.com/?cid={business.google_place_id}"
        else:
            review_url = f"https://www.google.com/search?q={business.business_name.replace(' ', '+')}"

        customer_name = booking.customer_name or "there"
        first_name = customer_name.split()[0]

        msg = (
            f"Hi {first_name}! Hope your session with {business.owner_name} went well 😊\n\n"
            f"If you have 30 seconds, a quick Google review would mean the world:\n"
            f"{review_url}\n\n"
            f"Thank you! 💙"
        )

        from services.whatsapp_service import send_whatsapp_message
        success = await send_whatsapp_message(booking.customer_phone, msg)

        # Log it
        log = OwnerCommand(
            business_id=business.id,
            command="REVIEW_REQUEST",
            metadata={"booking_id": str(booking.id), "sent": success},
        )
        db.add(log)
        await db.commit()

        if success:
            logger.info(f"Review request sent for booking {booking_id[-8:]}")
        return success
