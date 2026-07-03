"""Tests for keyring-backed XMPP credential resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from xmpp_p2p_chat.common.config import AppConfig, XMPPConfig
from xmpp_p2p_chat.common.models import Contact, ContactCredentials
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager
from xmpp_p2p_chat.connection_service.session import SessionManager


@pytest.fixture
async def session_manager(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    cfg = AppConfig(data_directory=data_dir, xmpp=XMPPConfig(jid="alice@example.com"))
    ab = AddressBookManager(data_dir / "ab.json", data_dir / "ab.d")
    ab.load()
    db = PersistenceManager(data_dir / "messages.db")
    await db.initialize()
    mgr = SessionManager(cfg, ab, db, on_push=lambda *_: None)
    yield mgr
    await mgr.shutdown()
    await db.close()


@pytest.mark.asyncio
async def test_resolve_password_from_config_ref(session_manager: SessionManager):
    session_manager.config.xmpp.password_ref = "keyring:main-account"
    with patch(
        "xmpp_p2p_chat.connection_service.session.resolve_password",
        return_value="secret-from-keyring",
    ) as mock_resolve:
        password = session_manager._resolve_xmpp_password()
        assert password == "secret-from-keyring"
        mock_resolve.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_password_from_contact_credentials(session_manager: SessionManager):
    contact = Contact(
        id="bob",
        jid="bob@example.com",
        name="Bob",
        credentials=ContactCredentials(password_ref="keyring:bob-creds"),
    )
    with patch(
        "xmpp_p2p_chat.connection_service.session.resolve_password",
        return_value="contact-secret",
    ):
        password = session_manager._resolve_xmpp_password(contact)
        assert password == "contact-secret"
