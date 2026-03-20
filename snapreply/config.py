from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # ─── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://user:password@host:5432/snapreply"

    # ─── Meta WhatsApp Cloud API ─────────────────────────────────────────────
    WHATSAPP_PHONE_NUMBER_ID: str = "your_phone_number_id"
    WHATSAPP_ACCESS_TOKEN: str = "your_permanent_access_token"
    WHATSAPP_VERIFY_TOKEN: str = "snapreply_verify_token"
    WHATSAPP_APP_SECRET: str = "your_whatsapp_app_secret"
    WHATSAPP_BUSINESS_NUMBER: str = "+447700000000"

    # ─── Twilio (SMS fallback + missed call detection) ───────────────────────
    TWILIO_ACCOUNT_SID: str = "ACxxxxxxxxxxxxx"
    TWILIO_AUTH_TOKEN: str = "your_twilio_auth_token"
    TWILIO_NUMBER_POOL: str = "+447700000001"

    # ─── Anthropic ───────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = "sk-ant-xxxxxxxxxxxxx"

    # ─── Stripe ──────────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = "sk_test_xxxxxxxxxxxxx"
    STRIPE_WEBHOOK_SECRET: str = "whsec_xxxxxxxxxxxxx"
    # Monthly price IDs
    STRIPE_PRICE_ID_STARTER: str = "price_starter_monthly"
    STRIPE_PRICE_ID_GROWTH: str = "price_growth_monthly"
    STRIPE_PRICE_ID_PRO: str = "price_pro_monthly"
    # Annual price IDs
    STRIPE_PRICE_ID_STARTER_ANNUAL: str = "price_starter_annual"
    STRIPE_PRICE_ID_GROWTH_ANNUAL: str = "price_growth_annual"
    STRIPE_PRICE_ID_PRO_ANNUAL: str = "price_pro_annual"

    # ─── Resend (email) ──────────────────────────────────────────────────────
    RESEND_API_KEY: str = "re_xxxxxxxxxxxxx"
    FROM_EMAIL: str = "hello@snapreply.co.uk"

    # ─── Google Calendar (Growth+ tier) ──────────────────────────────────────
    GOOGLE_CLIENT_ID: str = "xxxxxxxxxxxxx.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "GOCSPX-xxxxxxxxxxxxx"

    # ─── App ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-to-a-64-character-random-string-before-deploying"
    PRODUCTION: bool = False
    BASE_URL: str = "http://localhost:8000"

    # ─── Admin ───────────────────────────────────────────────────────────────
    ADMIN_PHONE: str = "+447700000000"
    ADMIN_EMAIL: str = "admin@snapreply.co.uk"
    ADMIN_SECRET_TOKEN: str = "change-this-admin-token-before-deploying"

    def get_stripe_price_id(self, plan: str, annual: bool = False) -> str:
        """Return the correct Stripe price ID for a given plan and billing cycle."""
        key = f"STRIPE_PRICE_ID_{plan.upper()}{'_ANNUAL' if annual else ''}"
        return getattr(self, key, self.STRIPE_PRICE_ID_STARTER)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
