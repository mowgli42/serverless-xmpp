"""Shared pytest fixtures for display and integration tests."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Any

import pytest

from xmpp_p2p_chat.common.config import load_config
from xmpp_p2p_chat.connection_service.service import ConnectionService


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class MockAPIClient:
    """In-memory API client for TUI display tests."""

    def __init__(self) -> None:
        self.responses: dict[str, Any] = {}
        self.errors: dict[str, Exception] = {}
        self.calls: list[tuple[str, dict | None]] = []
        self._handlers: list = []
        self._connected = asyncio.Event()
        self._connected.set()

    def on_event(self, handler) -> None:
        self._handlers.append(handler)

    def emit(self, event: str, params: dict) -> None:
        for handler in self._handlers:
            handler(event, params)

    async def connect(self) -> None:
        return

    async def disconnect(self) -> None:
        return

    async def call(self, method: str, params: dict | None = None, timeout: float = 30.0) -> Any:
        self.calls.append((method, params))
        if method in self.errors:
            raise self.errors[method]
        if method in self.responses:
            return self.responses[method]
        return {}


@pytest.fixture
def mock_api() -> MockAPIClient:
    client = MockAPIClient()
    client.responses = {
        "addressbook.list": {
            "contacts": [
                {
                    "id": "bob",
                    "jid": "bob@p2p.local",
                    "name": "Bob",
                    "preferred_transport": "direct-p2p",
                    "direct": {"host": "127.0.0.1", "port": 5224, "public_key_fingerprint": "SHA256:abc"},
                },
                {
                    "id": "carol",
                    "jid": "carol@p2p.local",
                    "name": "Carol",
                    "preferred_transport": "xmpp-server",
                },
            ],
            "presence": {
                "bob": {"show": "available", "status": "Online"},
                "carol": {"show": "away", "status": ""},
            },
            "status": {
                "version": 2,
                "content_hash": "SHA256:" + "a" * 64,
                "contact_count": 2,
                "warnings": [],
                "primary_path": "/tmp/addressbook.json",
            },
        },
        "system.health": {"ok": True, "warnings": [], "pending_outbox": 0, "uptime_seconds": 42},
        "connection.status": {
            "transports": [{"transport": "direct-p2p", "state": "connected"}],
            "p2p_fingerprint": "SHA256:deadbeef",
            "local_jid": "alice@p2p.local",
        },
        "chat.start": {"chat_id": "bob", "transport": "direct-p2p"},
        "chat.get_history": {"messages": []},
        "chat.send_message": {
            "message": {
                "id": "m1",
                "direction": "out",
                "body": "hello",
                "status": "sent",
                "timestamp": "2026-07-03T12:00:00+00:00",
            }
        },
        "addressbook.sync_status": {
            "enabled": False,
            "auto_apply": False,
            "pending_count": 0,
            "secret_configured": False,
        },
        "addressbook.get_pending_updates": {"updates": []},
    }
    return client


@pytest.fixture
async def service(tmp_path: Path):
    api_port = free_port()
    p2p_port = free_port()
    config_file = tmp_path / "config.toml"
    data_dir = tmp_path / "data"
    log_json = tmp_path / "service.json.log"
    config_file.write_text(
        f"""
[data]
directory = "{data_dir}"
import_bundled_if_empty = false

[connection]
api_host = "127.0.0.1"
api_port = {api_port}

[p2p]
listen_host = "127.0.0.1"
listen_port = {p2p_port}
mdns_enabled = false

[ui]
serve_web = false

[logging]
level = "INFO"
json_file = "{log_json}"
ebk_stderr = true

[xmpp]
jid = ""
password = ""
""",
        encoding="utf-8",
    )
    cfg = load_config(config_file)
    svc = ConnectionService(cfg)
    await svc.start()
    svc._test_api_port = api_port  # noqa: SLF001
    svc._test_log_json = log_json  # noqa: SLF001
    yield svc
    await svc.shutdown()
