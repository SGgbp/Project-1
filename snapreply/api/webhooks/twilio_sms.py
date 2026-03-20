"""Twilio SMS fallback webhook — handles inbound SMS replies."""
import logging
from fastapi import APIRouter, BackgroundTasks, Form, Request, Response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhooks/twilio/sms")
async def handle_inbound_sms(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
):
    """Route inbound SMS to the same conversation handler as WhatsApp."""
    background_tasks.add_task(_process_sms, From, To, Body, MessageSid)
    # Twilio expects empty TwiML response
    return Response(content="<Response/>", media_type="application/xml")


async def _process_sms(from_number: str, to_number: str, body: str, message_sid: str):
    from database.connection import AsyncSessionLocal
    from database.models import Business
    from services.ai_conversation import handle_customer_message
    from services.ai_safety import check_reply_safety
    from services.sms_service import send_sms
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business).where(
                Business.twilio_number.contains(to_number.replace("+", "")[-9:]),
                Business.active == True,
            )
        )
        business = result.scalar_one_or_none()
        if not business or business.paused:
            return

        result = await handle_customer_message(business, from_number, body, db)
        if not result:
            return

        reply_text = result.get("reply_text", "")
        safety = check_reply_safety(reply_text, business.owner_name)

        if safety["safe_to_send"] and reply_text:
            await send_sms(to=from_number, body=reply_text, from_=to_number)
        else:
            await send_sms(
                to=from_number,
                body=f"Thanks for your message! {business.owner_name} will be in touch shortly.",
                from_=to_number,
            )
