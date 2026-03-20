import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import anthropic

from config import settings

logger = logging.getLogger(__name__)

# Haiku ONLY for all customer conversations — never Sonnet
CONVERSATION_MODEL = "claude-haiku-4-5-20251001"
SUMMARY_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 200
MAX_RETRIES = 2

FALLBACK_MESSAGE = (
    "Thanks so much for getting in touch! We're just sorting a quick technical thing — "
    "someone will be with you very shortly 😊"
)

BUSINESS_TYPES = {
    "driving_instructor": "Driving Instructor",
    "beautician": "Mobile Beautician",
    "personal_trainer": "Personal Trainer",
    "tattoo_artist": "Tattoo Artist",
    "dog_groomer": "Dog Groomer",
    "tutor": "Tutor",
    "cleaner": "Cleaner / Window Cleaner",
    "photographer": "Photographer",
    "hairdresser": "Hairdresser",
    "other": "Business Owner",
}


def _build_system_prompt(business) -> str:
    persona = business.ai_persona_name or "Your assistant"
    business_type_label = BUSINESS_TYPES.get(business.business_type, business.business_type)

    return f"""You are {persona}, the friendly assistant for {business.business_name} — \
a {business_type_label} based in {business.city or "the UK"}.
You are replying via WhatsApp to someone who just tried to contact {business.owner_name}.

YOUR PERSONALITY:
- Warm, natural, and human — never robotic or corporate
- Very brief — WhatsApp messages should be 1-3 sentences MAX
- Occasional emojis are fine if the conversation feels casual
- Get straight to the point — people hate long WhatsApp messages

YOUR MISSION (in order):
1. Acknowledge why they got in touch warmly
2. Find out what service they need
3. Get their preferred date and time
4. Confirm the booking with all details
5. Let them know {business.owner_name} will personally confirm soon

STRICT RULES:
- Maximum 3 sentences per message — this is WhatsApp, not email
- NEVER quote specific prices
- NEVER promise specific dates without owner confirmation
- When you have name + service + preferred date/time → output BOOKING_CONFIRMED JSON
- If someone seems upset, apologise sincerely and promise fast callback

BOOKING CONFIRMATION (add after your message on new line when you have all required info):
<BOOKING_CONFIRMED>
{{
  "customer_name": "...",
  "service_type": "...",
  "preferred_date": "YYYY-MM-DD or descriptive",
  "preferred_time": "morning/afternoon/evening or specific time",
  "location": "their address or area if provided",
  "notes": "any other details mentioned"
}}
</BOOKING_CONFIRMED>

CONVERSATION END (add when conversation is naturally complete):
<CONVERSATION_END>true</CONVERSATION_END>

VIRAL FOOTER — FIRST MESSAGE ONLY (new line at end):
_Powered by SnapReply — snapreply.co.uk_"""


async def handle_customer_message(
    business,
    customer_phone: str,
    incoming_text: str,
    db,
) -> Optional[dict]:
    """
    Core conversation handler. Returns:
    {reply_text, conversation_id, booking_details, ended}
    """
    if business.paused:
        logger.info(f"Business paused — skipping AI reply")
        return None

    from database.models import Conversation
    from sqlalchemy import select

    # Load or create conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.business_id == business.id,
            Conversation.customer_phone == customer_phone,
            Conversation.status == "active",
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            business_id=business.id,
            customer_phone=customer_phone,
            messages=[],
            status="active",
        )
        db.add(conversation)
        await db.flush()

    is_first_message = len(conversation.messages or []) == 0

    # Append customer message
    messages = list(conversation.messages or [])
    messages.append({
        "role": "user",
        "content": incoming_text,
    })

    # Build Claude message list (no timestamps — keep it clean)
    claude_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

    # Get AI reply
    system_prompt = _build_system_prompt(business)
    raw_reply = await _get_ai_reply(system_prompt, claude_messages)

    # Parse structured blocks out of the reply
    reply_text, booking_details, ended = _parse_reply(raw_reply)

    # Add viral footer on first message only
    if is_first_message and "_Powered by SnapReply_" not in reply_text:
        reply_text = reply_text.rstrip() + "\n\n_Powered by SnapReply — snapreply.co.uk_"

    # Append assistant reply to history
    messages.append({
        "role": "assistant",
        "content": reply_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Persist
    conversation.messages = messages
    if ended or booking_details:
        conversation.status = "booked" if booking_details else "ended"

    await db.commit()

    return {
        "reply_text": reply_text,
        "conversation_id": str(conversation.id),
        "booking_details": booking_details,
        "ended": ended,
    }


async def _get_ai_reply(system_prompt: str, messages: list) -> str:
    """Call Claude with retries. NEVER returns empty string."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.messages.create(
                model=CONVERSATION_MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            )
            text = response.content[0].text.strip()
            if text:
                return text
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error (attempt {attempt + 1}): {e}")
        except Exception as e:
            logger.error(f"Unexpected AI error (attempt {attempt + 1}): {e}")

        if attempt < MAX_RETRIES - 1:
            await asyncio.sleep(1)

    logger.error("All AI retry attempts failed — using fallback message")
    return FALLBACK_MESSAGE


def _parse_reply(raw: str) -> tuple[str, Optional[dict], bool]:
    """
    Extract BOOKING_CONFIRMED JSON and CONVERSATION_END flag from AI reply.
    Returns (clean_reply_text, booking_details_or_None, ended_bool)
    """
    booking_details = None
    ended = False

    # Extract BOOKING_CONFIRMED block
    booking_match = re.search(
        r"<BOOKING_CONFIRMED>(.*?)</BOOKING_CONFIRMED>",
        raw,
        re.DOTALL,
    )
    if booking_match:
        try:
            booking_details = json.loads(booking_match.group(1).strip())
        except json.JSONDecodeError:
            logger.warning("Could not parse BOOKING_CONFIRMED JSON")
        raw = raw[:booking_match.start()] + raw[booking_match.end():]

    # Extract CONVERSATION_END block
    end_match = re.search(r"<CONVERSATION_END>.*?</CONVERSATION_END>", raw, re.DOTALL)
    if end_match:
        ended = True
        raw = raw[:end_match.start()] + raw[end_match.end():]

    reply_text = raw.strip()
    return reply_text, booking_details, ended


async def generate_initial_message(business) -> str:
    """Generate an opening WhatsApp message for a missed call — uses Haiku."""
    persona = business.ai_persona_name or "Your assistant"
    prompt = (
        f"You are {persona} for {business.business_name}. "
        f"Someone just tried to call {business.owner_name} but couldn't get through. "
        f"Write a warm, brief WhatsApp message (2 sentences max) to follow up and ask how you can help. "
        f"Do NOT mention prices. Sign off with the business name. "
        f"End with: _Powered by SnapReply — snapreply.co.uk_"
    )
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = await client.messages.create(
            model=CONVERSATION_MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Failed to generate initial message: {e}")
        return (
            f"Hi! You recently tried to call {business.business_name}. "
            f"How can we help you today? 😊\n\n_Powered by SnapReply — snapreply.co.uk_"
        )
