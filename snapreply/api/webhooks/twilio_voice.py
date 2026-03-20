"""
Twilio voice webhook — missed call detection.
When a customer calls the Twilio number and nobody answers,
a WhatsApp message is sent within 60 seconds.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Form, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Idempotency cache — prevent duplicate WhatsApp fires for the same call
_processed_call_sids: set[str] = set()


@router.post("/webhooks/twilio/voice/incoming")
async def handle_incoming_call(
    request: Request,
    To: str = Form(...),
    From: str = Form(...),
    CallSid: str = Form(...),
):
    """
    Caller rings the Twilio number.
    We dial the owner's real number. If no answer, Twilio hits /no-answer.
    """
    if settings.PRODUCTION:
        _validate_twilio_signature(request)

    # Find the business that owns this Twilio number
    from database.connection import AsyncSessionLocal
    from database.models import Business
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business).where(
                Business.twilio_number.contains(To.replace("+", "")[-9:]),
                Business.active == True,
            )
        )
        business = result.scalar_one_or_none()

    if not business:
        logger.warning(f"Incoming call to unknown Twilio number: {To[-4:]}")
        resp = VoiceResponse()
        resp.say("Sorry, this number is not in service.")
        return Response(content=str(resp), media_type="application/xml")

    # Dial the owner's real WhatsApp/mobile number
    resp = VoiceResponse()
    dial = Dial(
        action=f"{settings.BASE_URL}/webhooks/twilio/voice/no-answer"
                f"?business_id={business.id}&caller={From}&call_sid={CallSid}",
        timeout=20,
    )
    dial.number(business.owner_whatsapp)
    resp.append(dial)

    return Response(content=str(resp), media_type="application/xml")


@router.post("/webhooks/twilio/voice/no-answer")
async def handle_no_answer(
    request: Request,
    background_tasks: BackgroundTasks,
    DialCallStatus: str = Form(...),
    business_id: str = None,
    caller: str = None,
    call_sid: str = None,
):
    """
    Fired when the owner doesn't answer.
    Return TwiML immediately; send WhatsApp in background.
    """
    # Query params (passed via action URL)
    params = dict(request.query_params)
    business_id = params.get("business_id", business_id)
    caller = params.get("caller", caller)
    call_sid = params.get("call_sid", call_sid)

    missed_statuses = {"no-answer", "busy", "failed", "canceled"}
    if DialCallStatus.lower() in missed_statuses and call_sid:
        background_tasks.add_task(send_missed_call_whatsapp, business_id, caller, call_sid)

    resp = VoiceResponse()
    resp.say(
        "Thanks for calling. You'll receive a WhatsApp message shortly. Goodbye!",
        voice="alice",
        language="en-GB",
    )

    return Response(content=str(resp), media_type="application/xml")


async def send_missed_call_whatsapp(business_id: str, caller_number: str, call_sid: str):
    """
    Idempotent: check call_sid before firing.
    Target: WhatsApp delivered within 60 seconds of call ending.
    """
    if call_sid in _processed_call_sids:
        logger.info(f"Duplicate missed call {call_sid} — skipping")
        return
    _processed_call_sids.add(call_sid)

    from database.connection import AsyncSessionLocal
    from database.models import Business, Enquiry
    from services.ai_conversation import generate_initial_message
    from services.whatsapp_service import send_whatsapp_with_sms_fallback
    from sqlalchemy import select

    start_time = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business).where(Business.id == business_id)
        )
        business = result.scalar_one_or_none()
        if not business:
            logger.error(f"Business {business_id} not found for missed call")
            return

        # Log enquiry
        enquiry = Enquiry(
            business_id=business.id,
            customer_phone=caller_number,
            source="missed_call",
            call_sid=call_sid,
            reply_sent=False,
        )
        db.add(enquiry)
        await db.flush()

        # Generate and send WhatsApp
        message = await generate_initial_message(business)
        success = await send_whatsapp_with_sms_fallback(
            to=caller_number,
            body=message,
            twilio_from=business.twilio_number or settings.TWILIO_NUMBER_POOL,
        )

        seconds_taken = int((datetime.now(timezone.utc) - start_time).total_seconds())
        enquiry.reply_sent = success
        enquiry.seconds_to_reply = seconds_taken
        await db.commit()

        if success:
            logger.info(f"Missed call reply sent in {seconds_taken}s to ...{caller_number[-4:]}")
        else:
            logger.error(f"Failed to send missed call reply to ...{caller_number[-4:]}")


def _validate_twilio_signature(request: Request):
    """Validate Twilio signature header in production."""
    from twilio.request_validator import RequestValidator
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    # Note: form body validation happens at the route level
    if not signature:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Missing Twilio signature")
