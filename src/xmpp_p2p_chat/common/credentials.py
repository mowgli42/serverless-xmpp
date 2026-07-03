"""Secure credential storage via OS keyring."""

from __future__ import annotations

import logging

import keyring

from xmpp_p2p_chat.common.models import ContactCredentials

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "xmpp-p2p-chat"


def store_secret(entry_id: str, secret: str) -> str:
    """Store a secret in the OS keyring; returns a password_ref value."""
    keyring.set_password(KEYRING_SERVICE, entry_id, secret)
    return f"keyring:{entry_id}"


def get_secret(entry_id: str) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, entry_id)


def resolve_password(credentials: ContactCredentials | None) -> str | None:
    """Resolve password from inline (dev) or keyring reference."""
    if not credentials:
        return None
    if credentials.password:
        return credentials.password
    if credentials.password_ref and credentials.password_ref.startswith("keyring:"):
        entry_id = credentials.password_ref.removeprefix("keyring:")
        secret = get_secret(entry_id)
        if secret is None:
            logger.warning("Keyring entry not found: %s", entry_id)
        return secret
    return None
