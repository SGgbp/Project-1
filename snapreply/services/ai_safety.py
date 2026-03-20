"""
AI reply safety guardrails.
Holds messages that could cause legal/reputational risk before sending to customers.
"""
from typing import Optional

MAX_REPLY_LENGTH = 300

DANGEROUS_PHRASES = [
    "will definitely",
    "i promise",
    "guaranteed",
    "100%",
    "will cost",
    "the price is",
    "it'll be £",
    "that costs",
    "free of charge",
    "no charge",
    "can be there today",
    "will arrive at",
    "i'll be there",
    "it will be £",
    "costs £",
    "price is £",
    "charge you",
]

UNPROFESSIONAL_PHRASES = [
    "i don't know",
    "i have no idea",
    "i can't help with that",
    "that's not possible",
    "i cannot help",
    "no idea",
    "not my problem",
    "i don't care",
]


def check_reply_safety(reply_text: str, owner_name: str = "") -> dict:
    """
    Check an AI-generated reply for dangerous or unprofessional content.

    Returns:
        {
            safe_to_send: bool,
            issues: list[str],
            hold_reason: str | None
        }
    """
    issues = []
    lower = reply_text.lower()

    # Check dangerous phrases
    for phrase in DANGEROUS_PHRASES:
        if phrase in lower:
            issues.append(f"Dangerous phrase detected: '{phrase}'")

    # Check unprofessional phrases
    for phrase in UNPROFESSIONAL_PHRASES:
        if phrase in lower:
            issues.append(f"Unprofessional phrase detected: '{phrase}'")

    # Check length
    if len(reply_text) > MAX_REPLY_LENGTH:
        issues.append(f"Reply too long: {len(reply_text)} chars (max {MAX_REPLY_LENGTH})")

    safe_to_send = len([i for i in issues if "Dangerous" in i or "Unprofessional" in i]) == 0
    hold_reason = "; ".join(issues) if issues and not safe_to_send else None

    return {
        "safe_to_send": safe_to_send,
        "issues": issues,
        "hold_reason": hold_reason,
    }
