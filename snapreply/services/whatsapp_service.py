import httpx
import logging
from config import settings

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v18.0/{phone_number_id}/messages"


def _normalize_number(phone: str) -> str:
    """Strip +, spaces, and dashes from a phone number."""
    return phone.replace("+", "").replace(" ", "").replace("-", "")


async def send_whatsapp_message(to: str, body: str) -> bool:
    """Send a WhatsApp message via Meta Cloud API. Returns True on success."""
    to_normalized = _normalize_number(to)
    url = WHATSAPP_API_URL.format(phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID)
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_normalized,
        "type": "text",
        "text": {"body": body},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            logger.info(f"WhatsApp sent successfully to ...{to_normalized[-4:]}")
            return True
        else:
            logger.error(f"WhatsApp send failed: {response.status_code} — {response.text[:200]}")
            return False

    except httpx.TimeoutException:
        logger.error("WhatsApp send timed out after 10 seconds")
        return False
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return False


async def send_whatsapp_with_sms_fallback(to: str, body: str, twilio_from: str = None) -> bool:
    """Try WhatsApp first; fall back to SMS via Twilio on failure."""
    success = await send_whatsapp_message(to, body)
    if success:
        logger.info(f"Delivered via WhatsApp to ...{_normalize_number(to)[-4:]}")
        return True

    logger.warning(f"WhatsApp failed for ...{_normalize_number(to)[-4:]}, attempting SMS fallback")
    try:
        from services.sms_service import send_sms
        sms_from = twilio_from or settings.TWILIO_NUMBER_POOL
        sms_success = await send_sms(to=to, body=body, from_=sms_from)
        if sms_success:
            logger.info(f"Delivered via SMS fallback to ...{_normalize_number(to)[-4:]}")
        else:
            logger.error(f"Both WhatsApp and SMS failed for ...{_normalize_number(to)[-4:]}")
        return sms_success
    except Exception as e:
        logger.error(f"SMS fallback error: {e}")
        return False
