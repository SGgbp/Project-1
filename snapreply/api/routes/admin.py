"""Admin routes — protected by ADMIN_SECRET_TOKEN."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from config import settings
from database.connection import get_db
from database.models import Business, Subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin")


def _require_admin(x_admin_token: str = Header(...)):
    if x_admin_token != settings.ADMIN_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/stats", dependencies=[Depends(_require_admin)])
async def admin_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count(Business.id)))
    active = await db.execute(select(func.count(Business.id)).where(Business.active == True))
    return {
        "total_businesses": total.scalar(),
        "active_businesses": active.scalar(),
    }


@router.post("/digest/trigger", dependencies=[Depends(_require_admin)])
async def trigger_digest():
    from workers.daily_digest import send_all_daily_digests
    await send_all_daily_digests()
    return {"status": "digest triggered"}


@router.post("/monday/trigger", dependencies=[Depends(_require_admin)])
async def trigger_monday():
    from workers.monday_report import send_all_monday_reports
    await send_all_monday_reports()
    return {"status": "monday report triggered"}


@router.post("/health/trigger", dependencies=[Depends(_require_admin)])
async def trigger_health():
    from workers.health_check import check_platform_health
    result = await check_platform_health()
    return result
