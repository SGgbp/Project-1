"""Optional web dashboard API routes."""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, timedelta

from database.connection import get_db
from database.models import Business, Booking, Enquiry, DailyAnalytics
from api.routes.auth import get_current_business

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard")


@router.get("/overview")
async def get_overview(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    e_result = await db.execute(
        select(func.count(Enquiry.id)).where(
            Enquiry.business_id == business.id,
            Enquiry.created_at >= f"{week_ago}T00:00:00",
        )
    )
    b_result = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.business_id == business.id,
            Booking.created_at >= f"{week_ago}T00:00:00",
        )
    )

    return {
        "enquiries_7d": e_result.scalar() or 0,
        "bookings_7d": b_result.scalar() or 0,
        "plan": business.plan,
        "setup_complete": business.setup_complete,
        "paused": business.paused,
    }


@router.get("/bookings")
async def get_bookings(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking)
        .where(Booking.business_id == business.id)
        .order_by(Booking.created_at.desc())
        .limit(50)
    )
    bookings = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "customer_name": b.customer_name,
            "service_type": b.service_type,
            "preferred_date": b.preferred_date,
            "preferred_time": b.preferred_time,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bookings
    ]
