"""Google Calendar OAuth routes — Growth+ tier."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from database.models import Business
from api.routes.auth import get_current_business

router = APIRouter(prefix="/api/calendar")


@router.get("/connect")
async def connect_calendar(business: Business = Depends(get_current_business)):
    if not business.is_growth_or_pro:
        raise HTTPException(status_code=403, detail="Calendar sync requires Growth or Pro plan")
    from services.calendar_service import get_oauth_url
    url = get_oauth_url(str(business.id))
    return RedirectResponse(url=url)


@router.get("/callback")
async def calendar_callback(code: str, state: str):
    from services.calendar_service import handle_oauth_callback
    from config import settings
    success = await handle_oauth_callback(code, state)
    if success:
        return RedirectResponse(url=f"{settings.BASE_URL}/dashboard?calendar=connected")
    raise HTTPException(status_code=400, detail="Calendar connection failed")
