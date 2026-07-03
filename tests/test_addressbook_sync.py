"""Tests for signed address book sync."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from xmpp_p2p_chat.common.config import AddressBookSyncConfig
from xmpp_p2p_chat.common.models import Contact
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager
from xmpp_p2p_chat.connection_service.addressbook_sync import AddressBookSyncService
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager


class _FakeSyncUpdate:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def __getitem__(self, key: str) -> str:
        if key == "payload":
            return self._payload
        raise KeyError(key)


class _FakeSyncIq:
    def __init__(self, from_jid: str, payload_b64: str) -> None:
        self._from = from_jid
        self._payload = payload_b64

    def __getitem__(self, key: str):
        if key == "from":
            return type("Jid", (), {"bare": self._from})()
        if key == "addressbook_update":
            return _FakeSyncUpdate(self._payload)
        raise KeyError(key)


@pytest.fixture
async def sync_env(tmp_path):
    ab_path = tmp_path / "addressbook.json"
    ab_path.write_text("[]", encoding="utf-8")
    ab = AddressBookManager(primary_path=ab_path)
    ab.load()
    ab.add(
        Contact(
            id="alice",
            jid="alice@example.com",
            name="Alice",
            preferred_transport="xmpp-server",
        )
    )
    ab.add(
        Contact(
            id="bob",
            jid="bob@example.com",
            name="Bob",
            preferred_transport="xmpp-server",
        )
    )
    db = PersistenceManager(tmp_path / "messages.db")
    await db.initialize()
    config = AddressBookSyncConfig(enabled=True, secret="test-secret", auto_apply=False)
    pushes: list[tuple[str, dict]] = []

    def on_push(event: str, params: dict) -> None:
        pushes.append((event, params))

    svc = AddressBookSyncService(ab, db, config, on_push)
    yield svc, ab, db, pushes
    await db.close()


class TestAddressBookSyncSigning:
    @pytest.mark.asyncio
    async def test_sign_and_verify(self, sync_env):
        svc, ab, _db, _ = sync_env
        contact = ab.get("bob")
        payload = svc.build_update_payload(action="add", contact=contact)
        assert svc.verify_payload(payload)

    @pytest.mark.asyncio
    async def test_tampered_signature_rejected(self, sync_env):
        svc, ab, _db, _ = sync_env
        contact = ab.get("bob")
        payload = svc.build_update_payload(action="add", contact=contact)
        payload["signature"] = "invalid"
        assert not svc.verify_payload(payload)


class TestAddressBookSyncInbound:
    @pytest.mark.asyncio
    async def test_untrusted_jid_rejected(self, sync_env):
        svc, _ab, db, pushes = sync_env
        import base64
        import json

        payload = svc.build_update_payload(
            action="add", contact=Contact(id="x", jid="x@y.z", name="X")
        )
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        iq = _FakeSyncIq("stranger@evil.com", encoded)

        await svc.handle_inbound_iq(iq)  # type: ignore[arg-type]
        assert len(await db.list_sync_pending()) == 0
        assert pushes == []

    @pytest.mark.asyncio
    async def test_valid_update_goes_to_pending(self, sync_env):
        svc, ab, db, pushes = sync_env
        import base64
        import json

        new_contact = Contact(id="carol", jid="carol@example.com", name="Carol")
        payload = svc.build_update_payload(action="add", contact=new_contact)
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        iq = _FakeSyncIq("bob@example.com", encoded)

        await svc.handle_inbound_iq(iq)  # type: ignore[arg-type]
        pending = await db.list_sync_pending()
        assert len(pending) == 1
        assert pending[0].from_jid == "bob@example.com"
        assert pushes[0][0] == "addressbook.sync_pending"

    @pytest.mark.asyncio
    async def test_stale_timestamp_rejected(self, sync_env):
        svc, _ab, db, _ = sync_env
        import base64
        import json

        old_ts = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        contact = Contact(id="carol", jid="carol@example.com", name="Carol")
        payload = svc.build_update_payload(action="add", contact=contact)
        payload["timestamp"] = old_ts
        payload["signature"] = svc.sign_payload(payload)
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        iq = _FakeSyncIq("bob@example.com", encoded)

        await svc.handle_inbound_iq(iq)  # type: ignore[arg-type]
        assert len(await db.list_sync_pending()) == 0

    @pytest.mark.asyncio
    async def test_apply_pending_adds_contact(self, sync_env):
        svc, ab, db, _ = sync_env
        contact = Contact(id="carol", jid="carol@example.com", name="Carol")
        payload = svc.build_update_payload(action="add", contact=contact)
        pending_id = "p1"
        await db.save_sync_pending(
            pending_id,
            from_jid="bob@example.com",
            action="add",
            contact_id="carol",
            payload=payload,
        )
        assert await svc.apply_pending(pending_id)
        assert ab.get("carol") is not None

    @pytest.mark.asyncio
    async def test_sync_now_requires_transport(self, sync_env):
        svc, _ab, _db, _ = sync_env
        with pytest.raises(RuntimeError, match="XMPP transport"):
            await svc.sync_now()

    @pytest.mark.asyncio
    async def test_sync_now_sends_to_peers(self, sync_env):
        svc, _ab, _db, _ = sync_env
        sender = AsyncMock()
        svc.set_send_iq(sender)
        result = await svc.sync_now()
        assert result["sent"] == 2
        assert sender.await_count == 2
