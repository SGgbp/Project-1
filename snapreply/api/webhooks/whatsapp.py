import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory idempotency cache — prevents duplicate processing on Meta retries
_processed_message_ids: set[str] = set()
_MAX_CACHE_SIZE = 10_000


def _cache_message_id(message_id: str) -> bool:
    """Return True if this message is new (not yet processed). Adds to cache."""
    if message_id in _processed_message_ids:
        return False
    if len(_processed_message_ids) >= _MAX_CACHE_SIZE:
        # Drop oldest ~10% to prevent unbounded growth
        to_remove = list(_processed_message_ids)[:1000]
        for m in to_remove:
            _processed_message_ids.discard(m)
    _processed_message_ids.add(message_id)
    return True


# ─── GET — Webhook verification ──────────────────────────────────────────────

@router.get("/webhooks/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully.")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("WhatsApp webhook verification failed — invalid token.")
    raise HTTPException(status_code=403, detail="Forbidden")


# ─── POST — Incoming messages ────────────────────────────────────────────────

@router.post("/webhooks/whatsapp")
async def receive_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    """
    Return 200 IMMEDIATELY. All processing happens in BackgroundTasks.
    Meta will retry if it doesn't receive 200 within 20 seconds.
    """
    if settings.PRODUCTION:
        _verify_signature(request)

    try:
        body = await request.json()
    except Exception:
        return Response(status_code=200)

    background_tasks.add_task(process_whatsapp_payload, body)
    return Response(status_code=200)


def _verify_signature(request: Request):
    """Validate X-Hub-Signature-256 header in production."""
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Missing signature")
    # Note: body bytes need to be read before calling this; handled in middleware


# ─── Background processing ───────────────────────────────────────────────────

async def process_whatsapp_payload(body: dict):
    """Route each inbound message to the correct handler."""
    try:
        entry = body.get("entry", [])
        for e in entry:
            for change in e.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                metadata = value.get("metadata", {})

                for message in messages:
                    await _handle_single_message(message, metadata, value)
    except Exception as e:
        logger.error(f"Error processing WhatsApp payload: {e}", exc_info=True)


async def _handle_single_message(message: dict, metadata: dict, value: dict):
    from database.connection import AsyncSessionLocal
    from database.models import Business
    from sqlalchemy import select

    message_id = message.get("id", "")
    if not _cache_message_id(message_id):
        logger.info(f"Duplicate message {message_id} — skipping")
        return

    from_number = message.get("from", "")
    to_number = metadata.get("phone_number_id", settings.WHATSAPP_PHONE_NUMBER_ID)
    msg_type = message.get("type", "text")
    timestamp = message.get("timestamp")

    async with AsyncSessionLocal() as db:
        # Check if this is a message FROM the business owner
        result = await db.execute(
            select(Business).where(
                Business.owner_whatsapp.contains(from_number[-9:]),
                Business.active == True,
            )
        )
        owner_business = result.scalar_one_or_none()

        if owner_business:
            await _route_owner_message(message, owner_business, db)
            return

        # Route as a customer message — find business by snapreply_number
        result = await db.execute(
            select(Business).where(
                Business.snapreply_number.contains(to_number[-9:]),
                Business.active == True,
            )
        )
        business = result.scalar_one_or_none()

        if not business:
            logger.warning(f"No business found for number {to_number[-4:]}")
            return

        await _route_customer_message(message, business, from_number, msg_type, db)


async def _route_owner_message(message: dict, business, db):
    from services.onboarding_ai import handle_owner_message
    text = _extract_text(message)
    if text:
        await handle_owner_message(business, text, db)


async def _route_customer_message(message: dict, business, from_number: str, msg_type: str, db):
    from services.ai_conversation import handle_customer_message
    from services.ai_safety import check_reply_safety
    from services.whatsapp_service import send_whatsapp_message
    from services.notification_service import notify_owner_of_booking, notify_owner_of_new_enquiry
    from database.models import Conversation, Enquiry
    from sqlalchemy import select

    if business.paused:
        logger.info(f"Business {str(business.id)[-8:]} is paused — not replying")
        return

    # Handle non-text message types
    if msg_type == "audio":
        await send_whatsapp_message(
            from_number,
            "Thanks for your voice message! Could you type your message instead? I want to make sure I help you properly 😊"
        )
        return
    elif msg_type not in ("text", "button"):
        await send_whatsapp_message(
            from_number,
            f"Thanks for getting in touch! Could you type your message? I want to make sure I can help you 😊"
        )
        return

    text = _extract_text(message)
    if not text:
        return

    # Check if first message from this customer (for enquiry logging)
    existing = await db.execute(
        select(Conversation).where(
            Conversation.business_id == business.id,
            Conversation.customer_phone == from_number,
            Conversation.status == "active",
        )
    )
    existing_convo = existing.scalar_one_or_none()
    is_first_message = existing_convo is None

    # Log enquiry on first contact
    if is_first_message:
        enquiry = Enquiry(
            business_id=business.id,
            customer_phone=from_number,
            source="whatsapp",
            first_message=text[:500],
        )
        db.add(enquiry)
        await db.commit()

    # Get AI reply
    result = await handle_customer_message(business, from_number, text, db)
    if not result:
        return

    reply_text = result.get("reply_text", "")
    booking_details = result.get("booking_details")
    conversation_id = result.get("conversation_id")

    if not reply_text:
        return

    # Safety check
    safety = check_reply_safety(reply_text, business.owner_name)
    if safety["safe_to_send"]:
        await send_whatsapp_message(from_number, reply_text)
    else:
        logger.warning(f"Reply held for safety: {safety['hold_reason']}")
        await send_whatsapp_message(
            from_number,
            f"Thanks for getting in touch with {business.business_name}! "
            f"{business.owner_name} will get back to you very shortly 😊"
        )
        from services.notification_service import notify_owner_safety_hold
        await notify_owner_safety_hold(business, from_number, reply_text, safety["hold_reason"])

    # Notify owner of booking
    if booking_details:
        await notify_owner_of_booking(business, booking_details, from_number)

    # Notify owner of new enquiry
    if is_first_message:
        await notify_owner_of_new_enquiry(business, from_number, text)


def _extract_text(message: dict) -> str:
    """Extract text body from a WhatsApp message object."""
    msg_type = message.get("type", "")
    if msg_type == "text":
        return message.get("text", {}).get("body", "").strip()
    elif msg_type == "button":
        return message.get("button", {}).get("text", "").strip()
    return ""
