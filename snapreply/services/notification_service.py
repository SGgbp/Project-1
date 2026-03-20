"""
Owner notification service.
All functions are idempotent — safe to call multiple times.
"""
import logging
from config import settings

logger = logging.getLogger(__name__)


async def notify_owner_of_booking(business, booking_details: dict, customer_number: str) -> None:
    from services.whatsapp_service import send_whatsapp_message

    name = booking_details.get("customer_name", "Unknown")
    service = booking_details.get("service_type", "Not specified")
    date = booking_details.get("preferred_date", "TBC")
    time = booking_details.get("preferred_time", "TBC")
    location = booking_details.get("location") or "Not provided"
    notes = booking_details.get("notes") or "None"
    # Mask all but last 4 digits
    masked = f"...{customer_number[-4:]}" if len(customer_number) >= 4 else customer_number

    msg = (
        f"✨ *New booking via SnapReply!*\n\n"
        f"👤 Customer: {name}\n"
        f"📱 Phone: {masked}\n"
        f"🔧 Service: {service}\n"
        f"📅 Date: {date}\n"
        f"⏰ Time: {time}\n"
        f"📍 Location: {location}\n"
        f"📝 Notes: {notes}\n\n"
        f"Text *BOOKINGS* to see all today's bookings."
    )
    await send_whatsapp_message(business.owner_whatsapp, msg)


async def notify_owner_of_new_enquiry(business, customer_number: str, first_message: str) -> None:
    from services.whatsapp_service import send_whatsapp_message

    preview = (first_message[:80] + "...") if len(first_message) > 80 else first_message
    masked = f"...{customer_number[-4:]}" if len(customer_number) >= 4 else customer_number

    msg = (
        f"📩 *New enquiry from {masked}*\n\n"
        f'"{preview}"\n\n'
        f"Your AI assistant is handling it. 🤖\n"
        f"Text *TAKEOVER* to join the conversation."
    )
    await send_whatsapp_message(business.owner_whatsapp, msg)


async def notify_owner_payment_failed(business) -> None:
    from services.whatsapp_service import send_whatsapp_message

    msg = (
        f"⚠️ *Payment failed for SnapReply*\n\n"
        f"Hi {business.first_name}, we couldn't process your subscription payment.\n\n"
        f"Please update your billing details within 3 days to keep your AI assistant running:\n"
        f"{settings.BASE_URL}/billing\n\n"
        f"Need help? Reply to this message."
    )
    await send_whatsapp_message(business.owner_whatsapp, msg)


async def notify_owner_safety_hold(business, customer_number: str, held_reply: str, reason: str) -> None:
    from services.whatsapp_service import send_whatsapp_message

    masked = f"...{customer_number[-4:]}" if len(customer_number) >= 4 else customer_number
    msg = (
        f"🚨 *Reply held for review*\n\n"
        f"A reply to {masked} was held because:\n_{reason}_\n\n"
        f"A holding message was sent to the customer. "
        f"Please follow up with them directly."
    )
    await send_whatsapp_message(business.owner_whatsapp, msg)


async def notify_admin(message: str) -> None:
    """Send an alert to the SnapReply admin phone."""
    from services.whatsapp_service import send_whatsapp_message
    await send_whatsapp_message(settings.ADMIN_PHONE, f"🔔 *SnapReply Admin Alert*\n\n{message}")
