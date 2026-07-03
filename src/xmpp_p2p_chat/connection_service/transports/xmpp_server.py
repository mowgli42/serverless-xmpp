"""XMPP server transport using slixmpp."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

import slixmpp
from slixmpp.exceptions import IqError, IqTimeout

from xmpp_p2p_chat.common.models import ConnectionState, TransportStatus
from xmpp_p2p_chat.connection_service.transports.base import BaseTransport

logger = logging.getLogger(__name__)


class XMPPClient(slixmpp.ClientXMPP):
    def __init__(
        self,
        jid: str,
        password: str,
        server: str | None = None,
        port: int = 5222,
        transport: XMPPServerTransport | None = None,
    ) -> None:
        super().__init__(jid, password)
        self.transport_ref = transport
        if server:
            self.connect_address = (server, port)
        self.register_plugin("xep_0030")  # Service Discovery
        self.register_plugin("xep_0199")  # XMPP Ping
        self.add_event_handler("session_start", self._on_session_start)
        self.add_event_handler("message", self._on_message)
        self.add_event_handler("presence", self._on_presence)
        self.add_event_handler("disconnected", self._on_disconnected)

    async def _on_session_start(self, _event: Any) -> None:
        await self.send_presence()
        if self.transport_ref:
            await self.transport_ref._handle_connected()

    async def _on_message(self, msg: slixmpp.Message) -> None:
        if msg["type"] not in ("chat", "normal") or not msg["body"]:
            return
        from_jid = str(msg["from"].bare)
        body = str(msg["body"])
        stanza_id = str(msg["id"]) if msg["id"] else None
        if self.transport_ref and self.transport_ref._on_message:
            await self.transport_ref._on_message(from_jid, body, stanza_id)

    async def _on_presence(self, pres: slixmpp.Presence) -> None:
        if pres["type"] in ("subscribe", "subscribed", "unsubscribe", "unsubscribed"):
            return
        from_jid = str(pres["from"].bare)
        show = str(pres["show"]) if pres["show"] else "available"
        status = str(pres["status"]) if pres["status"] else ""
        if self.transport_ref and self.transport_ref._on_presence:
            await self.transport_ref._on_presence(from_jid, show, status)

    async def _on_disconnected(self, _event: Any) -> None:
        if self.transport_ref:
            await self.transport_ref._handle_disconnected()


class XMPPServerTransport(BaseTransport):
    def __init__(
        self,
        jid: str,
        password: str,
        server: str | None = None,
        port: int = 5222,
        enforce_tls: bool = True,
    ) -> None:
        super().__init__()
        self.jid = jid
        self.password = password
        self.server = server
        self.port = port
        self.enforce_tls = enforce_tls
        self._client: XMPPClient | None = None
        self._state = ConnectionState.DISCONNECTED
        self._error: str | None = None
        self._connect_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._should_reconnect = True
        self._backoff = 1.0

    def status(self) -> TransportStatus:
        return TransportStatus(
            transport="xmpp-server",
            state=self._state,
            error=self._error,
            jid=self.jid,
        )

    async def connect(self, **kwargs: Any) -> None:
        self._should_reconnect = True
        await self._do_connect()

    async def _do_connect(self) -> None:
        if self._state == ConnectionState.CONNECTED:
            return

        self._state = ConnectionState.CONNECTING
        self._error = None
        await self._emit_state(self._state)

        try:
            self._client = XMPPClient(
                self.jid,
                self.password,
                server=self.server or None,
                port=self.port,
                transport=self,
            )
            if self.enforce_tls:
                self._client.use_ssl = False
                self._client.use_tls = True

            self._connect_task = asyncio.create_task(self._client.connect())
            await asyncio.wait_for(self._connect_task, timeout=30.0)
        except Exception as exc:  # noqa: BLE001
            self._state = ConnectionState.ERROR
            self._error = str(exc)
            logger.exception("XMPP connection failed")
            await self._emit_state(self._state, self._error)
            if self._should_reconnect:
                self._schedule_reconnect()
            raise

    async def _handle_connected(self) -> None:
        self._state = ConnectionState.CONNECTED
        self._error = None
        self._backoff = 1.0
        await self._emit_state(self._state)
        logger.info("XMPP connected as %s", self.jid)

    async def _handle_disconnected(self) -> None:
        if self._state == ConnectionState.DISCONNECTED:
            return
        self._state = ConnectionState.DISCONNECTED
        await self._emit_state(self._state)
        if self._should_reconnect:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        delay = min(self._backoff, 300.0)
        self._backoff = min(self._backoff * 2, 300.0)
        self._state = ConnectionState.RECONNECTING
        logger.info("Scheduling XMPP reconnect in %.1fs", delay)

        async def _reconnect() -> None:
            await asyncio.sleep(delay)
            if self._should_reconnect:
                try:
                    await self._do_connect()
                except Exception:  # noqa: BLE001
                    pass

        self._reconnect_task = asyncio.create_task(_reconnect())

    async def disconnect(self) -> None:
        self._should_reconnect = False
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._state = ConnectionState.DISCONNECTED
        await self._emit_state(self._state)

    async def send_message(self, to_jid: str, body: str, message_id: str | None = None) -> str:
        if not self._client or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("XMPP transport not connected")
        mid = message_id or str(uuid4())
        self._client.send_message(mto=to_jid, mbody=body, mtype="chat", mid=mid)
        return mid

    async def set_presence(self, show: str = "available", status: str = "") -> None:
        if not self._client or self._state != ConnectionState.CONNECTED:
            return
        if show == "available":
            await self._client.send_presence(pstatus=status)
        else:
            await self._client.send_presence(pshow=show, pstatus=status)

    async def ping(self) -> bool:
        if not self._client or self._state != ConnectionState.CONNECTED:
            return False
        try:
            await self._client["xep_0199"].ping()
            return True
        except (IqError, IqTimeout):
            return False
