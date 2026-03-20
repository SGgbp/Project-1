"""
SnapReply v2.0 — FastAPI application entry point.
WhatsApp-first AI assistant for UK micro-businesses.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from config import settings
from database.connection import init_db
from workers.scheduler import start_scheduler, stop_scheduler
from workers.health_check import get_latest_health, check_platform_health
from api.middleware import RequestLoggingMiddleware, add_cors, limiter

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if settings.PRODUCTION else logging.DEBUG,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SnapReply v2.0 starting...")
    await init_db()
    start_scheduler()
    logger.info("SnapReply v2.0 is running 🚀")
    yield
    stop_scheduler()
    logger.info("SnapReply v2.0 shut down.")


# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SnapReply",
    description="WhatsApp-first AI assistant for UK micro-businesses",
    version="2.0.0",
    docs_url="/docs" if not settings.PRODUCTION else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

# Middlewares
add_cors(app)
app.add_middleware(RequestLoggingMiddleware)

# ─── Routers ─────────────────────────────────────────────────────────────────

# Webhooks (no auth)
from api.webhooks.whatsapp import router as whatsapp_router
from api.webhooks.twilio_voice import router as twilio_voice_router
from api.webhooks.twilio_sms import router as twilio_sms_router
from api.webhooks.stripe_webhook import router as stripe_router

app.include_router(whatsapp_router)
app.include_router(twilio_voice_router)
app.include_router(twilio_sms_router)
app.include_router(stripe_router)

# API routes (JWT auth)
from api.routes.auth import router as auth_router
from api.routes.dashboard import router as dashboard_router
from api.routes.onboarding import router as onboarding_router
from api.routes.admin import router as admin_router
from api.routes.calendar import router as calendar_router

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(onboarding_router)
app.include_router(admin_router)
app.include_router(calendar_router)

# ─── Health endpoint ─────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    cached = get_latest_health()
    if cached:
        return cached
    return await check_platform_health()

# ─── Viral footer referral landing ───────────────────────────────────────────
@app.get("/referred")
async def referred_landing(from_: str = None):
    """Redirect viral footer links to the main landing page."""
    from fastapi.responses import RedirectResponse
    url = f"{settings.BASE_URL}/?ref={from_}" if from_ else f"{settings.BASE_URL}/"
    return RedirectResponse(url=url)

# ─── Static files (landing page) ─────────────────────────────────────────────
import os
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
