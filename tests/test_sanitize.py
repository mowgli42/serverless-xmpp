"""Tests for message sanitization."""

from xmpp_p2p_chat.common.sanitize import sanitize_message_body


def test_strips_control_characters():
    assert sanitize_message_body("hello\x00world") == "helloworld"


def test_preserves_newlines_and_tabs():
    assert sanitize_message_body("line1\nline2\ttab") == "line1\nline2\ttab"


def test_caps_length():
    long = "a" * 70000
    assert len(sanitize_message_body(long)) == 65536
