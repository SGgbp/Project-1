"""
10 unit tests for ai_safety.py — all must pass before launch.
Run with: python -m pytest tests/test_safety.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.ai_safety import check_reply_safety


def test_clean_message_is_safe():
    result = check_reply_safety("Hi! Thanks for getting in touch. How can I help you today? 😊")
    assert result["safe_to_send"] is True
    assert result["hold_reason"] is None


def test_price_promise_is_held():
    result = check_reply_safety("A lesson will cost £35 for an hour.")
    assert result["safe_to_send"] is False
    assert any("will cost" in i for i in result["issues"])


def test_guarantee_phrase_is_held():
    result = check_reply_safety("I guaranteed we can fit you in this week!")
    assert result["safe_to_send"] is False


def test_100_percent_phrase_is_held():
    result = check_reply_safety("You'll 100% love the results.")
    assert result["safe_to_send"] is False


def test_price_pound_sign_is_held():
    result = check_reply_safety("That costs £50 for the full treatment.")
    assert result["safe_to_send"] is False


def test_unprofessional_i_dont_know():
    result = check_reply_safety("I don't know when they're available.")
    assert result["safe_to_send"] is False
    assert any("Unprofessional" in i for i in result["issues"])


def test_unprofessional_cant_help():
    result = check_reply_safety("I can't help with that request, sorry.")
    assert result["safe_to_send"] is False


def test_message_too_long_has_issue():
    long_msg = "A" * 301
    result = check_reply_safety(long_msg)
    assert any("too long" in i for i in result["issues"])


def test_message_exactly_at_limit_is_safe():
    msg = "A" * 300
    result = check_reply_safety(msg)
    assert result["safe_to_send"] is True


def test_booking_confirmation_message_is_safe():
    result = check_reply_safety(
        "Perfect! I've noted your booking request for a driving lesson next Tuesday morning. "
        "Dave will confirm the exact time shortly 😊"
    )
    assert result["safe_to_send"] is True
    assert result["hold_reason"] is None
