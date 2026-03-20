"""Dashboard API routes — stats, bookings, conversations."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from datetime import date, timedelta, datetime, timezone

from database.connection import get_db
from database.models import Business, Booking, Enquiry, DailyAnalytics, Subscription
from api.routes.auth import get_current_business

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard")


@router.get("/overview")
async def get_overview(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    e_result = await db.execute(
        select(func.count(Enquiry.id)).where(
            Enquiry.business_id == business.id,
            Enquiry.created_at >= week_ago,
        )
    )
    b_result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.business_id == business.id,
            Booking.created_at >= week_ago,
        )
    )
    b_today = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.business_id == business.id,
            Booking.created_at >= date.today().isoformat(),
        )
    )

    sub_result = await db.execute(
        select(Subscription).where(Subscription.business_id == business.id)
    )
    sub = sub_result.scalar_one_or_none()

    return {
        "enquiries_7d": e_result.scalar() or 0,
        "bookings_7d": b_result.scalar() or 0,
        "bookings_today": b_today.scalar() or 0,
        "plan": business.plan,
        "setup_complete": business.setup_complete,
        "paused": business.paused,
        "subscription_status": sub.status if sub else "none",
        "trial_ends_at": sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
    }


@router.get("/bookings")
async def get_bookings(
    status: str = None,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    q = select(Booking).where(Booking.business_id == business.id)
    if status:
        q = q.where(Booking.status == status)
    q = q.order_by(Booking.created_at.desc()).limit(100)

    result = await db.execute(q)
    bookings = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "customer_name": b.customer_name,
            "customer_phone": b.customer_phone[-4:].rjust(len(b.customer_phone), "*") if b.customer_phone else None,
            "service_type": b.service_type,
            "preferred_date": b.preferred_date,
            "preferred_time": b.preferred_time,
            "location": b.location,
            "notes": b.notes,
            "status": b.status,
            "reminder_sent": b.reminder_sent,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bookings
    ]


@router.patch("/bookings/{booking_id}")
async def update_booking_status(
    booking_id: str,
    status: str,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    valid_statuses = {"pending", "confirmed", "completed", "no_show", "cancelled"}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.business_id == business.id,
        )
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.status = status
    await db.commit()

    if status == "completed" and business.is_pro:
        from services.review_service import schedule_review_request
        schedule_review_request(str(booking.id))

    return {"id": str(booking.id), "status": booking.status}


@router.get("/analytics")
async def get_analytics(
    days: int = 30,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    start_date = (date.today() - timedelta(days=days)).isoformat()
    result = await db.execute(
        select(DailyAnalytics)
        .where(
            DailyAnalytics.business_id == business.id,
            DailyAnalytics.date >= start_date,
        )
        .order_by(DailyAnalytics.date.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "date": r.date,
            "enquiries": r.enquiries_count,
            "conversations": r.conversations_count,
            "bookings": r.bookings_count,
            "avg_reply_seconds": r.avg_reply_seconds,
        }
        for r in rows
    ]
