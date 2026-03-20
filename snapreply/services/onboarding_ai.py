"""
WhatsApp-native owner onboarding and command handling.
Owners set up their entire account by texting — no dashboard required.
"""
import logging
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

BUSINESS_TYPE_MENU = """What type of business do you run?

1. Driving Instructor
2. Mobile Beautician
3. Personal Trainer
4. Tattoo Artist
5. Dog Groomer
6. Tutor / Music Teacher
7. Cleaner / Window Cleaner
8. Photographer
9. Hairdresser
10. Other

Reply with the number."""

BUSINESS_TYPE_MAP = {
    "1": "driving_instructor",
    "2": "beautician",
    "3": "personal_trainer",
    "4": "tattoo_artist",
    "5": "dog_groomer",
    "6": "tutor",
    "7": "cleaner",
    "8": "photographer",
    "9": "hairdresser",
    "10": "other",
}

OWNER_COMMANDS = {
    "PAUSE", "UNPAUSE", "BOOKINGS", "STATS", "GREETING",
    "TEST", "HELP", "STOP", "UPGRADE", "TIPS",
}


async def handle_owner_message(business, text: str, db) -> None:
    """Route owner message to setup flow or command handler."""
    from services.whatsapp_service import send_whatsapp_message

    text_upper = text.strip().upper()

    # Always handle commands regardless of setup state
    if text_upper in OWNER_COMMANDS:
        await _handle_command(business, text_upper, db)
        return

    # Setup flow
    if not business.setup_complete:
        await _handle_setup_step(business, text.strip(), db)
        return

    # Post-setup freeform — offer help
    await send_whatsapp_message(
        business.owner_whatsapp,
        f"Hi {business.first_name}! Text HELP to see all available commands 😊"
    )


# ─── Setup Flow ──────────────────────────────────────────────────────────────

async def _handle_setup_step(business, text: str, db) -> None:
    from services.whatsapp_service import send_whatsapp_message

    step = business.setup_step

    if step == 0:
        # Welcome — ask for name
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"👋 Welcome to SnapReply! I'm going to set up your AI assistant in under 5 minutes.\n\n"
            f"First — what's your full name?"
        )
        business.setup_step = 1
        await db.commit()

    elif step == 1:
        # Save name — ask for business name
        business.owner_name = text
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"Great, {text.split()[0]}! 🎉\n\nWhat's your business name?"
        )
        business.setup_step = 2
        await db.commit()

    elif step == 2:
        # Save business name — ask for type
        business.business_name = text
        await send_whatsapp_message(
            business.owner_whatsapp,
            BUSINESS_TYPE_MENU
        )
        business.setup_step = 3
        await db.commit()

    elif step == 3:
        # Save business type — ask for city
        business_type = BUSINESS_TYPE_MAP.get(text.strip(), "other")
        business.business_type = business_type
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"Perfect! What city or area do you cover? (e.g. Manchester, North London)"
        )
        business.setup_step = 4
        await db.commit()

    elif step == 4:
        # Save city — show default greeting
        business.city = text
        default_greeting = (
            f"Hi! Thanks for getting in touch with {business.business_name}. "
            f"I'm {business.owner_name}'s assistant — how can I help you today? 😊"
        )
        business.custom_greeting = default_greeting
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"Here's your default greeting:\n\n"
            f"_{default_greeting}_\n\n"
            f"Reply *KEEP* to use this, or type your own custom greeting."
        )
        business.setup_step = 5
        await db.commit()

    elif step == 5:
        # Save greeting — mark setup complete
        if text.upper() != "KEEP":
            business.custom_greeting = text
        business.setup_complete = True
        business.setup_step = 6
        await db.commit()

        await send_whatsapp_message(
            business.owner_whatsapp,
            f"🎉 You're all set, {business.first_name}!\n\n"
            f"Your SnapReply AI assistant is now *LIVE*. "
            f"Any missed calls or WhatsApp enquiries will be replied to automatically within 60 seconds.\n\n"
            f"Text *HELP* anytime to see what I can do for you."
        )


# ─── Owner Commands ───────────────────────────────────────────────────────────

async def _handle_command(business, command: str, db) -> None:
    from services.whatsapp_service import send_whatsapp_message
    from database.models import Booking, OwnerCommand
    from sqlalchemy import select, func as sqlfunc
    from datetime import date

    if command == "PAUSE":
        business.paused = True
        await db.commit()
        await send_whatsapp_message(
            business.owner_whatsapp,
            "⏸ SnapReply is now *paused*. Your AI won't reply to new messages until you text UNPAUSE."
        )

    elif command == "UNPAUSE":
        business.paused = False
        await db.commit()
        await send_whatsapp_message(
            business.owner_whatsapp,
            "▶️ SnapReply is now *active* again. Your AI assistant is back on duty! 🚀"
        )

    elif command == "BOOKINGS":
        today = date.today().isoformat()
        result = await db.execute(
            select(Booking).where(
                Booking.business_id == business.id,
                Booking.preferred_date == today,
                Booking.status.in_(["pending", "confirmed"]),
            )
        )
        bookings = result.scalars().all()
        if not bookings:
            msg = f"📅 No bookings for today ({today})."
        else:
            lines = [f"📅 Today's bookings ({today}):"]
            for i, b in enumerate(bookings, 1):
                lines.append(
                    f"\n{i}. {b.customer_name or 'Unknown'} — {b.service_type}\n"
                    f"   ⏰ {b.preferred_time or 'TBC'} | 📱 {b.customer_phone}"
                )
            msg = "\n".join(lines)
        await send_whatsapp_message(business.owner_whatsapp, msg)

    elif command == "STATS":
        from database.models import Enquiry, Conversation
        from datetime import timedelta
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        e_result = await db.execute(
            select(sqlfunc.count(Enquiry.id)).where(
                Enquiry.business_id == business.id,
                Enquiry.created_at >= week_ago,
            )
        )
        b_result = await db.execute(
            select(sqlfunc.count(Booking.id)).where(
                Booking.business_id == business.id,
                Booking.created_at >= week_ago,
            )
        )
        enquiries = e_result.scalar() or 0
        bookings = b_result.scalar() or 0
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"📊 Last 7 days:\n"
            f"📩 Enquiries: {enquiries}\n"
            f"📅 Bookings: {bookings}\n"
            f"Plan: {business.plan.title()}"
        )

    elif command == "GREETING":
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"Your current greeting:\n\n_{business.custom_greeting}_\n\n"
            f"To change it, text: GREETING followed by your new greeting message."
        )

    elif command == "TEST":
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"✅ SnapReply is working! Your AI assistant is active and ready to reply to customers.\n"
            f"Business: {business.business_name}\n"
            f"Plan: {business.plan.title()}\n"
            f"Status: {'⏸ Paused' if business.paused else '▶️ Active'}"
        )

    elif command == "UPGRADE":
        await handle_upgrade_command(business)

    elif command == "TIPS":
        await send_whatsapp_message(
            business.owner_whatsapp,
            "💡 Tips to get more enquiries:\n\n"
            "1. Add your SnapReply number to your Facebook/Instagram bio\n"
            "2. Put it on your Google Business profile\n"
            "3. Add it to any flyers or business cards\n"
            "4. Ask happy customers to WhatsApp you for repeat bookings\n\n"
            "Need help? Reply HELP 😊"
        )

    elif command == "HELP":
        await send_whatsapp_message(
            business.owner_whatsapp,
            "📱 *SnapReply Commands:*\n\n"
            "*PAUSE* — Stop AI replies temporarily\n"
            "*UNPAUSE* — Resume AI replies\n"
            "*BOOKINGS* — See today's bookings\n"
            "*STATS* — Last 7 days summary\n"
            "*GREETING* — View/update your greeting\n"
            "*TEST* — Check everything's working\n"
            "*UPGRADE* — See Growth & Pro plans\n"
            "*TIPS* — Ideas to drive more enquiries\n"
            "*STOP* — Cancel your subscription\n"
        )

    elif command == "STOP":
        await send_whatsapp_message(
            business.owner_whatsapp,
            f"😢 Sorry to see you go, {business.first_name}.\n\n"
            f"To cancel your subscription, visit: {settings.BASE_URL}/billing\n\n"
            f"Your data will be retained for 90 days. Text HELP if you change your mind!"
        )

    # Log the command
    cmd_log = OwnerCommand(
        business_id=business.id,
        command=command,
    )
    db.add(cmd_log)
    await db.commit()


async def handle_upgrade_command(business) -> None:
    """Send plan comparison and Stripe checkout links."""
    from services.whatsapp_service import send_whatsapp_message

    msg = (
        f"⬆️ *Upgrade SnapReply*\n\n"
        f"*Growth — £69/mo*\n"
        f"✅ Unlimited conversations\n"
        f"✅ Google Calendar sync\n"
        f"✅ No-show reminders\n"
        f"✅ Monday ROI report\n"
        f"👉 {settings.BASE_URL}/upgrade?plan=growth\n\n"
        f"*Pro — £119/mo*\n"
        f"✅ Everything in Growth\n"
        f"✅ Review request automation\n"
        f"✅ Custom AI persona name\n"
        f"✅ Dedicated Twilio number\n"
        f"✅ Monthly strategy call\n"
        f"👉 {settings.BASE_URL}/upgrade?plan=pro\n\n"
        f"Annual plans save 2 months! 💰"
    )
    await send_whatsapp_message(business.owner_whatsapp, msg)
