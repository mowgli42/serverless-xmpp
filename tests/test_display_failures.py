"""Service-level failure scenarios for display troubleshooting."""

from __future__ import annotations

import json

import pytest
import websockets


async def _rpc(port: int, method: str, params: dict | None = None):
    uri = f"ws://127.0.0.1:{port}/rpc"
    async with websockets.connect(uri) as ws:
        req_id = "1"
        await ws.send(
            json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        )
        return json.loads(await ws.recv())


@pytest.mark.asyncio
async def test_rpc_invalid_json_returns_parse_error(service):
    port = service._test_api_port  # noqa: SLF001
    uri = f"ws://127.0.0.1:{port}/rpc"
    async with websockets.connect(uri) as ws:
        await ws.send("{not-json")
        raw = await ws.recv()
        data = json.loads(raw)
        assert data["error"]["code"] == -32700


@pytest.mark.asyncio
async def test_addressbook_add_invalid_jid_returns_error(service):
    port = service._test_api_port  # noqa: SLF001
    uri = f"ws://127.0.0.1:{port}/rpc"
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "addressbook.add",
                    "params": {"contact": {"id": "bad", "jid": "not-a-jid", "name": "Bad"}},
                }
            )
        )
        data = json.loads(await ws.recv())
        assert "error" in data


@pytest.mark.asyncio
async def test_health_reports_warnings_after_malformed_fragment(tmp_path, service):
    port = service._test_api_port  # noqa: SLF001
    frag_dir = service.config.addressbooks_dir
    frag_dir.mkdir(parents=True, exist_ok=True)
    (frag_dir / "bad.json").write_text("{broken", encoding="utf-8")
    service.addressbook.reload()
    result = await _rpc(port, "system.health")
    assert result["result"]["warnings"] or service.addressbook.warnings


@pytest.mark.asyncio
async def test_flood_of_addressbook_list_calls(service):
    port = service._test_api_port  # noqa: SLF001
    for _ in range(50):
        result = await _rpc(port, "addressbook.list")
        assert "status" in result["result"]
        assert result["result"]["status"]["content_hash"].startswith("SHA256:")


@pytest.mark.asyncio
async def test_status_after_unknown_rpc_method(service):
    port = service._test_api_port  # noqa: SLF001
    uri = f"ws://127.0.0.1:{port}/rpc"
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps({"jsonrpc": "2.0", "id": "99", "method": "nonexistent.method", "params": {}})
        )
        data = json.loads(await ws.recv())
        assert "error" in data
    health = await _rpc(port, "system.health")
    assert health["result"]["ok"] is True
