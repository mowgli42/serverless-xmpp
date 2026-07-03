"""Minimal XMPP XML stream helpers for direct peer-to-peer messaging (XEP-0174 inspired)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from uuid import uuid4

NS_CLIENT = "jabber:client"
NS_STREAM = "http://etherx.jabber.org/streams"

STREAM_HEADER_RE = re.compile(
    rb"<stream:stream\b[^>]*>",
    re.IGNORECASE,
)


def stream_open(local_jid: str, remote_jid: str) -> str:
    return (
        "<?xml version='1.0'?>"
        f"<stream:stream xmlns='{NS_CLIENT}' xmlns:stream='{NS_STREAM}' "
        f"from='{local_jid}' to='{remote_jid}' version='1.0'>"
    )


def stream_close() -> str:
    return "</stream:stream>"


def message_stanza(from_jid: str, to_jid: str, body: str, message_id: str | None = None) -> str:
    mid = message_id or str(uuid4())
    return (
        f"<message xmlns='{NS_CLIENT}' type='chat' id='{mid}' "
        f"from='{from_jid}' to='{to_jid}'>"
        f"<body>{_escape_xml(body)}</body></message>"
    )


def presence_stanza(from_jid: str, to_jid: str, show: str = "available", status: str = "") -> str:
    if show == "available":
        show_attr = ""
    else:
        show_attr = f"<show>{_escape_xml(show)}</show>"
    status_attr = f"<status>{_escape_xml(status)}</status>" if status else ""
    return (
        f"<presence xmlns='{NS_CLIENT}' from='{from_jid}' to='{to_jid}'>"
        f"{show_attr}{status_attr}</presence>"
    )


def parse_message(stanza_xml: str) -> tuple[str, str, str | None] | None:
    """Return (from_jid, body, stanza_id) or None if not a chat message."""
    try:
        root = ET.fromstring(stanza_xml)
    except ET.ParseError:
        return None
    if root.tag.split("}")[-1] != "message":
        return None
    body_text = None
    for el in root.iter():
        if el.tag.split("}")[-1] == "body" and el.text:
            body_text = el.text
            break
    if not body_text or not body_text.strip():
        return None
    from_jid = root.get("from", "")
    stanza_id = root.get("id")
    return from_jid, body_text, stanza_id


def parse_presence(stanza_xml: str) -> tuple[str, str, str] | None:
    try:
        root = ET.fromstring(stanza_xml)
    except ET.ParseError:
        return None
    if root.tag.split("}")[-1] != "presence":
        return None
    from_jid = root.get("from", "")
    show_el = root.find(f"{{{NS_CLIENT}}}show") or root.find("show")
    status_el = root.find(f"{{{NS_CLIENT}}}status") or root.find("status")
    show = show_el.text if show_el is not None and show_el.text else "available"
    status = status_el.text if status_el is not None and status_el.text else ""
    return from_jid, show, status


def extract_stream_jids(header: bytes) -> tuple[str, str]:
    text = header.decode("utf-8", errors="replace")
    from_match = re.search(r"from=['\"]([^'\"]+)['\"]", text)
    to_match = re.search(r"to=['\"]([^'\"]+)['\"]", text)
    return (
        from_match.group(1) if from_match else "",
        to_match.group(1) if to_match else "",
    )


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&apos;")
        .replace('"', "&quot;")
    )
