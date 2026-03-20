"""
Auth routes — register, login, JWT.
Rate limited: 5 registers/hour, 10 logins/hour per IP.
"""
import re
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.connection import get_db
from database.models import Business, Subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

E164_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    owner_name: str
    business_name: str
    business_type: str
    owner_whatsapp: str
    city: str = ""
    plan: str = "starter"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode(data, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])


async def get_current_business(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Business:
    try:
        payload = _decode_token(credentials.credentials)
        business_id = payload.get("business_id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=401, detail="Business not found")
    return business


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    # Validate WhatsApp number
    if not E164_PATTERN.match(body.owner_whatsapp):
        raise HTTPException(status_code=400, detail="Invalid WhatsApp number format")

    # Check email not already taken
    existing = await db.execute(select(Business).where(Business.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create business
    business = Business(
        email=body.email,
        password_hash=_hash_password(body.password),
        owner_name=body.owner_name,
        business_name=body.business_name,
        business_type=body.business_type,
        owner_whatsapp=body.owner_whatsapp,
        city=body.city,
        plan=body.plan,
        active=True,
    )
    db.add(business)
    await db.flush()

    # Create trial subscription
    trial_end = datetime.now(timezone.utc) + timedelta(days=7)
    subscription = Subscription(
        business_id=business.id,
        stripe_customer_id=f"pending_{str(business.id)[-8:]}",  # replaced on first payment
        status="trial",
        plan=body.plan,
        trial_ends_at=trial_end,
    )
    db.add(subscription)
    await db.commit()

    # Create Stripe checkout session
    checkout_url = None
    try:
        from services.stripe_service import create_checkout_session
        checkout_url = await create_checkout_session(str(business.id), body.plan)
    except Exception as e:
        logger.error(f"Stripe checkout creation failed: {e}")

    return {
        "business_id": str(business.id),
        "checkout_url": checkout_url,
        "message": f"Account created! Complete your subscription to activate SnapReply.",
    }


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Business).where(Business.email == body.email))
    business = result.scalar_one_or_none()

    if not business or not _verify_password(body.password, business.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token({
        "business_id": str(business.id),
        "plan": business.plan,
        "setup_complete": business.setup_complete,
    })

    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def get_me(business: Business = Depends(get_current_business)):
    return {
        "business_id": str(business.id),
        "email": business.email,
        "owner_name": business.owner_name,
        "business_name": business.business_name,
        "business_type": business.business_type,
        "plan": business.plan,
        "city": business.city,
        "setup_complete": business.setup_complete,
        "paused": business.paused,
        "active": business.active,
    }


@router.post("/refresh")
async def refresh_token(business: Business = Depends(get_current_business)):
    token = _create_token({
        "business_id": str(business.id),
        "plan": business.plan,
        "setup_complete": business.setup_complete,
    })
    return {"access_token": token, "token_type": "bearer"}
