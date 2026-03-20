"""
Google Calendar sync — Growth and Pro tier only.
Owners connect via OAuth2; bookings are auto-added as events.
"""
import json
import logging
from datetime import datetime, timedelta

from config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
REDIRECT_URI = f"{settings.BASE_URL}/api/calendar/callback"


def get_oauth_url(business_id: str) -> str:
    """Generate Google OAuth2 URL. State = business_id for callback routing."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=str(business_id),
        prompt="consent",
    )
    return auth_url


async def handle_oauth_callback(code: str, state: str) -> bool:
    """Exchange auth code for tokens and store on business record."""
    from google_auth_oauthlib.flow import Flow
    from database.connection import AsyncSessionLocal
    from database.models import Business
    from sqlalchemy import select

    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes or SCOPES),
        }

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Business).where(Business.id == state))
            business = result.scalar_one_or_none()
            if not business:
                return False
            business.google_calendar_token = token_data
            await db.commit()

        logger.info(f"Google Calendar connected for business {state[-8:]}")
        return True

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return False


async def create_booking_event(business, booking) -> bool:
    """
    Create a Google Calendar event for a booking.
    Only runs for Growth and Pro tier businesses with Calendar connected.
    Never raises — returns False on failure.
    """
    if not business.is_growth_or_pro:
        return False
    if not business.google_calendar_token:
        return False

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import google.auth.transport.requests

        token_data = business.google_calendar_token
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes", SCOPES),
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
            # Update stored token
            from database.connection import AsyncSessionLocal
            from database.models import Business
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Business).where(Business.id == business.id))
                biz = result.scalar_one_or_none()
                if biz:
                    updated_token = dict(token_data)
                    updated_token["token"] = creds.token
                    biz.google_calendar_token = updated_token
                    await db.commit()

        service = build("calendar", "v3", credentials=creds)

        # Parse start time
        start_dt = _parse_booking_datetime(booking.preferred_date, booking.preferred_time)
        end_dt = start_dt + timedelta(hours=1)

        event = {
            "summary": f"{booking.service_type} — {booking.customer_name or 'Customer'}",
            "description": (
                f"Booked via SnapReply\n"
                f"Phone: {booking.customer_phone}\n"
                f"Notes: {booking.notes or 'None'}"
            ),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/London"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/London"},
        }

        calendar_id = business.google_calendar_id or "primary"
        service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"Calendar event created for booking {str(booking.id)[-8:]}")
        return True

    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        return False


def _parse_booking_datetime(date_str: str, time_str: str) -> datetime:
    """Best-effort parse of booking date/time strings."""
    now = datetime.now()
    base_date = now.replace(hour=9, minute=0, second=0, microsecond=0)

    try:
        if date_str and "-" in date_str:
            base_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass

    # Parse time hints
    if time_str:
        t = time_str.lower()
        if "morning" in t:
            base_date = base_date.replace(hour=9)
        elif "afternoon" in t:
            base_date = base_date.replace(hour=14)
        elif "evening" in t:
            base_date = base_date.replace(hour=18)
        else:
            try:
                parsed = datetime.strptime(time_str.strip(), "%H:%M")
                base_date = base_date.replace(hour=parsed.hour, minute=parsed.minute)
            except ValueError:
                pass

    return base_date
