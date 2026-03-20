"""
AI conversation parsing tests — no API calls needed.
Tests the _parse_reply function in isolation.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.ai_conversation import _parse_reply


def test_clean_reply_no_blocks():
    text = "Hi there! How can I help you today? 😊"
    reply, booking, ended = _parse_reply(text)
    assert reply == text
    assert booking is None
    assert ended is False


def test_booking_confirmed_extracted():
    text = """Great, I've got all the details!
<BOOKING_CONFIRMED>
{
  "customer_name": "Sarah Jones",
  "service_type": "Driving Lesson",
  "preferred_date": "2025-06-10",
  "preferred_time": "morning",
  "location": "Manchester",
  "notes": "First lesson"
}
</BOOKING_CONFIRMED>"""
    reply, booking, ended = _parse_reply(text)
    assert booking is not None
    assert booking["customer_name"] == "Sarah Jones"
    assert booking["service_type"] == "Driving Lesson"
    assert "BOOKING_CONFIRMED" not in reply


def test_conversation_end_extracted():
    text = "Thanks for booking! See you soon 😊<CONVERSATION_END>true</CONVERSATION_END>"
    reply, booking, ended = _parse_reply(text)
    assert ended is True
    assert "CONVERSATION_END" not in reply


def test_both_blocks_extracted():
    text = """Perfect! I have everything I need.
<BOOKING_CONFIRMED>
{"customer_name": "Tom", "service_type": "Cut", "preferred_date": "tomorrow", "preferred_time": "afternoon", "location": "", "notes": ""}
</BOOKING_CONFIRMED>
<CONVERSATION_END>true</CONVERSATION_END>"""
    reply, booking, ended = _parse_reply(text)
    assert booking["customer_name"] == "Tom"
    assert ended is True
    assert "BOOKING_CONFIRMED" not in reply
    assert "CONVERSATION_END" not in reply


def test_malformed_booking_json_doesnt_crash():
    text = "<BOOKING_CONFIRMED>not valid json {{{</BOOKING_CONFIRMED>"
    reply, booking, ended = _parse_reply(text)
    assert booking is None
    assert ended is False
