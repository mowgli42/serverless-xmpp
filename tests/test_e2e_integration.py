"""Phase 7 integration tests for spec scenarios."""

from __future__ import annotations

import asyncio
import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
import websockets

from xmpp_p2p_chat.common.config import load_config
from xmpp_p2p_chat.common.models import (
    ChatSession,
    ConnectionState,
    Contact,
    DeliveryStatus,
    DirectEndpoint,
    Message,
    MessageDirection,
    TransportStatus,
)
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager
from xmpp_p2p_chat.connection_service.service import ConnectionService
from xmpp_p2p_chat.connection_service.session import SessionManager
from xmpp_p2p_chat.connection_service.transports.base import BaseTransport


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _service_config(tmp_path: Path, port: int, p2p_port: int | None = None) -> Path:
    data_dir = tmp_path / "data"
    if p2p_port is None:
        p2p_port = _free_port()
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f"""
[data]
directory = "{data_dir}"
import_bundled_if_empty = false

[connection]
api_host = "127.0.0.1"
api_port = {port}

[p2p]
local_jid = "alice@p2p.local"
listen_host = "127.0.0.1"
listen_port = {p2p_port}
mdns_enabled = false

[ui]
serve_web = false

[xmpp]
jid = ""
password = ""
""",
        encoding="utf-8",
    )
    return config_file


async def _rpc(method: str, params: dict | None = None, port: int = 18766):
    uri = f"ws://127.0.0.1:{port}/rpc"
    async with websockets.connect(uri) as ws:
        req_id = "1"
        await ws.send(
            json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        )
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=5))


@pytest.fixture
async def service(tmp_path: Path):
    api_port = _free_port()
    cfg = load_config(_service_config(tmp_path, api_port))
    svc = ConnectionService(cfg)
    await svc.start()
    svc._test_api_port = api_port  # noqa: SLF001 — test helper
    yield svc
    await svc.shutdown()


@pytest.mark.asyncio
async def test_history_after_service_restart(tmp_path: Path):
    """Spec: chat history survives service restart."""
    api_port = _free_port()
    config_file = _service_config(tmp_path, api_port)
    cfg = load_config(config_file)

    svc1 = ConnectionService(cfg)
    await svc1.start()

    svc1.addressbook.add(Contact(id="bob", jid="bob@p2p.local", name="Bob"))
    await svc1.persistence.save_message(
        Message(
            id="hist-1",
            chat_id="bob",
            direction=MessageDirection.IN,
            body="Before restart",
            timestamp=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
            delivered=True,
            status=DeliveryStatus.DELIVERED,
        )
    )
    await svc1.shutdown()

    svc2 = ConnectionService(load_config(config_file))
    await svc2.start()
    try:
        result = await _rpc("chat.get_history", {"chat_id": "bob", "limit": 10}, port=api_port)
        messages = result["result"]["messages"]
        assert len(messages) == 1
        assert messages[0]["body"] == "Before restart"
    finally:
        await svc2.shutdown()


@pytest.mark.asyncio
async def test_dual_client_addressbook_sync(service: ConnectionService):
    """Spec: multiple UIs stay in sync via push notifications."""
    uri = f"ws://127.0.0.1:{service._test_api_port}/rpc"  # noqa: SLF001
    async with websockets.connect(uri) as ws1, websockets.connect(uri) as ws2:
        await ws1.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "addressbook.add",
                    "params": {
                        "contact": {"id": "sync-test", "jid": "sync@p2p.local", "name": "Sync"}
                    },
                }
            )
        )
        await ws1.recv()

        push = await asyncio.wait_for(ws2.recv(), timeout=3)
        data = json.loads(push)
        assert data.get("method") == "addressbook.updated"


class _FlakyTransport(BaseTransport):
    """Fails first send, succeeds on reconnect — simulates offline queuing."""

    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0
        self._state = ConnectionState.DISCONNECTED

    def status(self) -> TransportStatus:
        return TransportStatus(transport="fake", state=self._state, jid="alice@p2p.local")

    async def connect(self, **kwargs) -> None:
        self._state = ConnectionState.CONNECTED
        await self._emit_state(self._state)

    async def disconnect(self) -> None:
        self._state = ConnectionState.DISCONNECTED

    async def send_message(self, to_jid: str, body: str, message_id: str | None = None) -> str:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("transport offline")
        return message_id or "sent-id"

    async def set_presence(self, show: str = "available", status: str = "") -> None:
        pass


@pytest.mark.asyncio
async def test_outbox_drains_on_transport_reconnect(tmp_path: Path):
    """Spec: queued messages drain when transport reconnects."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    ab = AddressBookManager(data_dir / "addressbook.json", data_dir / "addressbooks.d")
    ab.load()
    contact = Contact(
        id="bob",
        jid="bob@p2p.local",
        name="Bob",
        preferred_transport="direct-p2p",
        direct=DirectEndpoint(host="127.0.0.1", port=9999),
    )
    ab.add(contact)

    db = PersistenceManager(data_dir / "messages.db")
    await db.initialize()

    pushes: list[tuple[str, dict]] = []

    def on_push(event: str, params: dict) -> None:
        pushes.append((event, params))

    cfg = load_config(_service_config(tmp_path, _free_port(), p2p_port=_free_port()))
    cfg.p2p.mdns_enabled = False
    sessions = SessionManager(cfg, ab, db, on_push)
    await sessions.initialize()

    fake = _FlakyTransport()
    fake._state = ConnectionState.CONNECTED

    async def fake_get_transport(_contact: Contact) -> BaseTransport:
        return fake

    sessions._get_transport = fake_get_transport  # type: ignore[method-assign]
    sessions._sessions["bob"] = ChatSession(
        chat_id="bob",
        contact_id="bob",
        remote_jid="bob@p2p.local",
        transport="direct-p2p",
    )

    msg = await sessions.send_message("bob", "queued while offline")
    assert msg.status == DeliveryStatus.PENDING
    pending = await db.get_pending_outbox("bob")
    assert len(pending) == 1

    await sessions._drain_outbox()
    pending_after = await db.get_pending_outbox("bob")
    assert len(pending_after) == 0
    assert fake.attempts >= 2

    await sessions.shutdown()
    await db.close()
