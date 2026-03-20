"""Settings & billing routes — authenticated owner profile management."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from config import settings
from database.connection import get_db
from database.models import Business, Subscription
from api.routes.auth import get_current_business

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings")


class UpdateSettingsRequest(BaseModel):
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    city: Optional[str] = None
    custom_greeting: Optional[str] = None
    ai_persona_name: Optional[str] = None
    google_place_id: Optional[str] = None


@router.get("")
async def get_settings(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    sub_result = await db.execute(
        select(Subscription).where(Subscription.business_id == business.id)
    )
    sub = sub_result.scalar_one_or_none()

    return {
        "business_id": str(business.id),
        "email": business.email,
        "owner_name": business.owner_name,
        "business_name": business.business_name,
        "business_type": business.business_type,
        "plan": business.plan,
        "city": business.city,
        "custom_greeting": business.custom_greeting,
        "ai_persona_name": business.ai_persona_name,
        "google_place_id": business.google_place_id,
        "setup_complete": business.setup_complete,
        "paused": business.paused,
        "owner_whatsapp": business.owner_whatsapp,
        "subscription": {
            "status": sub.status if sub else "none",
            "plan": sub.plan if sub else business.plan,
            "annual": sub.annual if sub else False,
            "trial_ends_at": sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
            "current_period_end": sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        } if sub else None,
    }


@router.put("")
async def update_settings(
    body: UpdateSettingsRequest,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    if body.business_name is not None:
        business.business_name = body.business_name
    if body.owner_name is not None:
        business.owner_name = body.owner_name
    if body.city is not None:
        business.city = body.city
    if body.custom_greeting is not None:
        business.custom_greeting = body.custom_greeting
    if body.ai_persona_name is not None:
        if not business.is_pro:
            raise HTTPException(status_code=403, detail="Custom AI persona name is a Pro feature")
        business.ai_persona_name = body.ai_persona_name
    if body.google_place_id is not None:
        business.google_place_id = body.google_place_id

    await db.commit()
    return {"status": "updated"}


@router.post("/pause")
async def toggle_pause(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    business.paused = not business.paused
    await db.commit()
    state = "paused" if business.paused else "active"
    return {"status": state, "paused": business.paused}


@router.post("/billing-portal")
async def billing_portal(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    sub_result = await db.execute(
        select(Subscription).where(Subscription.business_id == business.id)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub or sub.stripe_customer_id.startswith("pending_"):
        raise HTTPException(status_code=400, detail="No active subscription found")

    try:
        from services.stripe_service import create_billing_portal_session
        url = await create_billing_portal_session(sub.stripe_customer_id)
        return {"url": url}
    except Exception as e:
        logger.error(f"Billing portal error: {e}")
        raise HTTPException(status_code=502, detail="Could not create billing portal session")


@router.post("/checkout")
async def create_checkout(
    plan: str = "starter",
    annual: bool = False,
    business: Business = Depends(get_current_business),
):
    try:
        from services.stripe_service import create_checkout_session
        url = await create_checkout_session(str(business.id), plan, annual)
        return {"url": url}
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=502, detail="Could not create checkout session")
