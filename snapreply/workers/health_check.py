"""
Platform health check — runs every 5 minutes.
Checks DB, WhatsApp API, and Claude API. Alerts admin on failure.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

_health_log: list[dict] = []  # Max 100 entries
_start_time = time.time()


async def check_platform_health() -> dict:
    db_ok = await _check_database()
    whatsapp_ok = await _check_whatsapp()
    claude_ok = await _check_claude()

    status = "ok" if all([db_ok, whatsapp_ok, claude_ok]) else "degraded"
    uptime = int(time.time() - _start_time)

    result = {
        "status": status,
        "db_ok": db_ok,
        "whatsapp_ok": whatsapp_ok,
        "claude_ok": claude_ok,
        "last_check": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime,
    }

    # Store in log (cap at 100)
    _health_log.append(result)
    if len(_health_log) > 100:
        _health_log.pop(0)

    if status == "degraded":
        failed = [k for k, v in result.items() if k.endswith("_ok") and not v]
        await _alert_admin(f"Health check FAILED: {', '.join(failed)}")

    return result


def get_latest_health() -> Optional[dict]:
    return _health_log[-1] if _health_log else None


async def _check_database() -> bool:
    try:
        from database.connection import engine
        from sqlalchemy import text
        start = time.perf_counter()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        ms = (time.perf_counter() - start) * 1000
        if ms > 100:
            logger.warning(f"DB health check slow: {ms:.0f}ms")
        return True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return False


async def _check_whatsapp() -> bool:
    try:
        url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}"
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"WhatsApp health check failed: {e}")
        return False


async def _check_claude() -> bool:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        return bool(response.content)
    except Exception as e:
        logger.error(f"Claude health check failed: {e}")
        return False


async def _alert_admin(message: str) -> None:
    try:
        from services.notification_service import notify_admin
        await notify_admin(message)
    except Exception as e:
        logger.error(f"Failed to send admin health alert: {e}")
