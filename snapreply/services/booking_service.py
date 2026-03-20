"""Booking creation and management."""
import logging
from database.models import Booking

logger = logging.getLogger(__name__)


async def create_booking(business, booking_details: dict, customer_phone: str, conversation_id: str, db) -> Booking:
    """Create a booking record and optionally sync to Google Calendar."""
    booking = Booking(
        business_id=business.id,
        conversation_id=conversation_id,
        customer_name=booking_details.get("customer_name"),
        customer_phone=customer_phone,
        service_type=booking_details.get("service_type"),
        preferred_date=booking_details.get("preferred_date"),
        preferred_time=booking_details.get("preferred_time"),
        location=booking_details.get("location"),
        notes=booking_details.get("notes"),
        status="pending",
    )
    db.add(booking)
    await db.flush()

    # Calendar sync for Growth+ tier
    if business.is_growth_or_pro:
        try:
            from services.calendar_service import create_booking_event
            await create_booking_event(business, booking)
        except Exception as e:
            logger.error(f"Calendar sync failed (non-fatal): {e}")

    # Schedule review request for Pro tier
    if business.is_pro:
        try:
            from services.review_service import schedule_review_request
            schedule_review_request(str(booking.id))
        except Exception as e:
            logger.error(f"Review schedule failed (non-fatal): {e}")

    await db.commit()
    logger.info(f"Booking created: {str(booking.id)[-8:]} for business {str(business.id)[-8:]}")
    return booking
