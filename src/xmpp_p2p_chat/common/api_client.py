"""WebSocket JSON-RPC client for UIs."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import websockets

from xmpp_p2p_chat.common.structured_logging import log_event

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, dict], None]


class APIClient:
    def __init__(self, url: str, token: str = "") -> None:
        self.url = url
        self.token = token
        self._ws: websockets.ClientConnection | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._handlers: list[EventHandler] = []
        self._reader_task: asyncio.Task | None = None
        self._connected = asyncio.Event()
        self._should_run = True

    def on_event(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def connect(self) -> None:
        self._should_run = True
        while self._should_run:
            try:
                self._ws = await websockets.connect(self.url, ping_interval=20, ping_timeout=20)
                if self.token:
                    await self.call("auth", {"token": self.token})
                self._connected.set()
                self._reader_task = asyncio.create_task(self._read_loop())
                await self._reader_task
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("API connection lost: %s", exc)
                log_event(
                    logger,
                    logging.WARNING,
                    "ui.api.disconnected",
                    error=str(exc),
                    url=self.url,
                )
                self._connected.clear()
                self._fail_pending(exc)
                if self._should_run:
                    await asyncio.sleep(2)

    async def disconnect(self) -> None:
        self._should_run = False
        if self._reader_task:
            self._reader_task.cancel()
        if self._ws:
            await self._ws.close()

    async def call(self, method: str, params: dict | None = None, timeout: float = 30.0) -> Any:
        await self._connected.wait()
        if not self._ws:
            raise RuntimeError("Not connected")
        req_id = str(uuid4())
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        await self._ws.send(json.dumps(payload))
        return await asyncio.wait_for(future, timeout=timeout)

    async def _read_loop(self) -> None:
        assert self._ws
        async for raw in self._ws:
            message = json.loads(raw)
            if "id" in message and message["id"] in self._pending:
                future = self._pending.pop(message["id"])
                if "error" in message:
                    future.set_exception(RuntimeError(message["error"]["message"]))
                else:
                    future.set_result(message.get("result"))
            elif "method" in message:
                event = message["method"]
                params = message.get("params", {})
                for handler in self._handlers:
                    handler(event, params)

    def _fail_pending(self, exc: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()
