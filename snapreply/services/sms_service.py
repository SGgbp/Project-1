import logging
from config import settings

logger = logging.getLogger(__name__)


async def send_sms(to: str, body: str, from_: str = None) -> bool:
    """Send an SMS via Twilio. Returns True on success."""
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        from_number = from_ or settings.TWILIO_NUMBER_POOL
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to,
        )
        logger.info(f"SMS sent: SID={message.sid}, status={message.status}")
        return True
    except Exception as e:
        logger.error(f"SMS send failed: {e}")
        return False
