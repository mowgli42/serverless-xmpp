"""Parse XMPP error stanzas and slixmpp exceptions into structured info."""

from __future__ import annotations

from slixmpp.exceptions import IqError, IqTimeout, XMPPError

from xmpp_p2p_chat.common.models import XmppErrorInfo


def parse_xmpp_error(exc: BaseException) -> XmppErrorInfo:
    """Extract condition, type, and text from slixmpp/XMPP failures."""
    if isinstance(exc, IqTimeout):
        return XmppErrorInfo(
            condition="remote-server-timeout",
            error_type="cancel",
            text="IQ request timed out",
            raw=str(exc),
        )

    stanza = None
    if isinstance(exc, IqError):
        stanza = exc.iq
    elif isinstance(exc, XMPPError):
        stanza = getattr(exc, "stanza", None)

    if stanza is not None:
        condition = None
        error_type = None
        text = None
        error_elem = stanza.find("{urn:ietf:params:xml:ns:xmpp-stanzas}error")
        if error_elem is not None:
            error_type = error_elem.get("type")
            for child in error_elem:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag != "text":
                    condition = tag
                elif child.text:
                    text = child.text
        return XmppErrorInfo(
            condition=condition,
            error_type=error_type,
            text=text or str(exc),
            raw=str(stanza),
        )

    message = str(exc)
    lowered = message.lower()
    for hint, condition in (
        ("not-authorized", "not-authorized"),
        ("policy-violation", "policy-violation"),
        ("item-not-found", "item-not-found"),
        ("remote-server-timeout", "remote-server-timeout"),
        ("service-unavailable", "service-unavailable"),
    ):
        if hint in lowered:
            return XmppErrorInfo(condition=condition, text=message, raw=message)

    return XmppErrorInfo(text=message, raw=message)
