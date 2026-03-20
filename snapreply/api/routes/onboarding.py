"""Onboarding API routes (web-based setup complement to WhatsApp flow)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database.connection import get_db
from database.models import Business
from api.routes.auth import get_current_business

router = APIRouter(prefix="/api/onboarding")


class UpdateGreetingRequest(BaseModel):
    greeting: str


@router.get("/status")
async def onboarding_status(business: Business = Depends(get_current_business)):
    return {
        "setup_complete": business.setup_complete,
        "setup_step": business.setup_step,
        "business_name": business.business_name,
        "plan": business.plan,
    }


@router.post("/greeting")
async def update_greeting(
    body: UpdateGreetingRequest,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    business.custom_greeting = body.greeting
    await db.commit()
    return {"status": "updated", "greeting": business.custom_greeting}
