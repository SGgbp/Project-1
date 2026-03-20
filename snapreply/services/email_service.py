"""Transactional email via Resend."""
import logging
import resend
from config import settings

logger = logging.getLogger(__name__)
resend.api_key = settings.RESEND_API_KEY


async def send_welcome_email(to_email: str, owner_name: str, plan: str) -> bool:
    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": to_email,
            "subject": f"Welcome to SnapReply {plan.title()} 🎉",
            "html": f"""
            <h2>Welcome to SnapReply, {owner_name.split()[0]}!</h2>
            <p>Your <strong>{plan.title()}</strong> subscription is now active.</p>
            <p>Your AI assistant is live and will reply to every WhatsApp enquiry within 60 seconds.</p>
            <p><strong>Quick start:</strong> Text <code>HELP</code> to your SnapReply number to see all commands.</p>
            <br>
            <p>Questions? Reply to this email — we're here to help.</p>
            <p>— The SnapReply Team</p>
            <hr>
            <small><a href="{settings.BASE_URL}/privacy">Privacy</a> ·
            <a href="{settings.BASE_URL}/terms">Terms</a></small>
            """,
        })
        logger.info(f"Welcome email sent to {to_email[:4]}***")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
        return False


async def send_trial_reminder_email(to_email: str, owner_name: str, days_left: int) -> bool:
    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": to_email,
            "subject": f"Your SnapReply trial ends in {days_left} day{'s' if days_left != 1 else ''}",
            "html": f"""
            <h2>Hi {owner_name.split()[0]},</h2>
            <p>Your SnapReply free trial ends in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong>.</p>
            <p>To keep your AI assistant running,
            <a href="{settings.BASE_URL}/billing">update your billing details</a>.</p>
            <p>Plans from just £39/month — cancel anytime.</p>
            <p>— The SnapReply Team</p>
            """,
        })
        return True
    except Exception as e:
        logger.error(f"Failed to send trial reminder email: {e}")
        return False
