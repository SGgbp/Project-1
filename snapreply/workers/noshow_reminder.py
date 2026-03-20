"""
No-show reminder worker — runs every hour.
Sends a WhatsApp reminder to customers with bookings tomorrow.
Growth and Pro tier only.
"""
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


async def send_noshow_reminders() -> None:
    from database.connection import AsyncSessionLocal
    from database.models import Business, Booking
    from services.whatsapp_service import send_whatsapp_message
    from sqlalchemy import select

    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Booking)
            .join(Business, Business.id == Booking.business_id)
            .where(
                Booking.preferred_date == tomorrow,
                Booking.status == "confirmed",
                Booking.reminder_sent == False,
                Business.plan.in_(["growth", "pro"]),
                Business.active == True,
            )
        )
        bookings = result.scalars().all()

        for booking in bookings:
            try:
                biz_result = await db.execute(
                    select(Business).where(Business.id == booking.business_id)
                )
                business = biz_result.scalar_one_or_none()
                if not business:
                    continue

                customer_name = booking.customer_name or "there"
                first_name = customer_name.split()[0]

                msg = (
                    f"Hi {first_name}! Just a reminder you've got a "
                    f"*{booking.service_type}* with *{business.owner_name}* tomorrow"
                    f"{' at ' + booking.preferred_time if booking.preferred_time else ''}. 📅\n\n"
                    f"Reply *YES* to confirm or call {business.owner_whatsapp} to reschedule."
                )
                await send_whatsapp_message(booking.customer_phone, msg)
                booking.reminder_sent = True

                from database.models import OwnerCommand
                db.add(OwnerCommand(
                    business_id=business.id,
                    command="NOSHOW_REMINDER",
                    metadata={"booking_id": str(booking.id), "customer": booking.customer_phone[-4:]},
                ))

            except Exception as e:
                logger.error(f"Reminder failed for booking {str(booking.id)[-8:]}: {e}")

        await db.commit()
        if bookings:
            logger.info(f"No-show reminders sent: {len(bookings)}")
