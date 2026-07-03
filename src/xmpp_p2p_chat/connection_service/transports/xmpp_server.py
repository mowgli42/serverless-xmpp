"""XMPP server transport using slixmpp with XEP-0198/0199 support."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import slixmpp
from slixmpp.exceptions import IqError, IqTimeout
from slixmpp.stanza import Iq
from slixmpp.xmlstream.handler import Callback
from slixmpp.xmlstream.matcher import MatchXPath

from xmpp_p2p_chat.common.models import ConnectionState, TransportStatus, XmppErrorInfo
from xmpp_p2p_chat.connection_service.addressbook_sync import SYNC_NAMESPACE
from xmpp_p2p_chat.connection_service.transports.base import BaseTransport
from xmpp_p2p_chat.connection_service.xmpp.errors import parse_xmpp_error
from xmpp_p2p_chat.connection_service.xmpp.sm_state import (
    StreamManagementState,
    clear_sm_state,
    load_sm_state,
    save_sm_state,
)

logger = logging.getLogger(__name__)

SyncIqHandler = Callable[[Iq], Awaitable[None]]


class XMPPClient(slixmpp.ClientXMPP):
    def __init__(
        self,
        jid: str,
        password: str,
        server: str | None = None,
        port: int = 5222,
        transport: XMPPServerTransport | None = None,
        *,
        stream_management_enabled: bool = True,
        sm_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(jid, password)
        self.transport_ref = transport
        if server:
            self.connect_address = (server, port)

        self.register_plugin("xep_0030")
        self.register_plugin("xep_0199")
        if stream_management_enabled:
            cfg = {"allow_resume": True}
            if sm_config:
                cfg.update(sm_config)
            self.register_plugin("xep_0198", config=cfg)

        self.add_event_handler("session_start", self._on_session_start)
        self.add_event_handler("message", self._on_message)
        self.add_event_handler("presence", self._on_presence)
        self.add_event_handler("disconnected", self._on_disconnected)
        if stream_management_enabled:
            self.add_event_handler("sm_enabled", self._on_sm_enabled)
            self.add_event_handler("session_resumed", self._on_session_resumed)
            self.add_event_handler("sm_failed", self._on_sm_failed)

        self.register_handler(
            Callback(
                "AddressBook Sync IQ",
                MatchXPath(f"{{{SYNC_NAMESPACE}}}update"),
                self._on_addressbook_sync_iq,
            )
        )

    async def _on_session_start(self, _event: Any) -> None:
        await self.send_presence()
        if self.transport_ref:
            await self.transport_ref._handle_connected()

    async def _on_sm_enabled(self, _event: Any) -> None:
        if self.transport_ref:
            self.transport_ref._sm_active = True
            self.transport_ref._persist_sm_state()

    async def _on_session_resumed(self, _event: Any) -> None:
        logger.info("XMPP stream management session resumed")
        if self.transport_ref:
            self.transport_ref._persist_sm_state()

    async def _on_sm_failed(self, _event: Any) -> None:
        logger.warning("XMPP stream management resume/enable failed")
        if self.transport_ref:
            self.transport_ref._clear_sm_state()

    async def _on_addressbook_sync_iq(self, iq: Iq) -> None:
        if self.transport_ref and self.transport_ref._on_sync_iq:
            await self.transport_ref._on_sync_iq(iq)

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
            self.transport_ref._persist_sm_state()
            await self.transport_ref._handle_disconnected()


class XMPPServerTransport(BaseTransport):
    def __init__(
        self,
        jid: str,
        password: str,
        server: str | None = None,
        port: int = 5222,
        enforce_tls: bool = True,
        *,
        data_dir: Path | None = None,
        stream_management_enabled: bool = True,
        ping_interval_seconds: int = 90,
        ping_timeout_seconds: int = 30,
    ) -> None:
        super().__init__()
        self.jid = jid
        self.password = password
        self.server = server
        self.port = port
        self.enforce_tls = enforce_tls
        self.data_dir = data_dir
        self.stream_management_enabled = stream_management_enabled
        self.ping_interval_seconds = ping_interval_seconds
        self.ping_timeout_seconds = ping_timeout_seconds
        self._client: XMPPClient | None = None
        self._state = ConnectionState.DISCONNECTED
        self._error: str | None = None
        self._error_info: XmppErrorInfo | None = None
        self._connect_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._should_reconnect = True
        self._backoff = 1.0
        self._on_sync_iq: SyncIqHandler | None = None
        self._sm_active = False

    def set_sync_handler(self, handler: SyncIqHandler) -> None:
        self._on_sync_iq = handler

    def status(self) -> TransportStatus:
        sm_summary = None
        if self.stream_management_enabled:
            sm_summary = {
                "enabled": self._sm_active,
                "sm_id_present": bool(self._current_sm_id()),
            }
        return TransportStatus(
            transport="xmpp-server",
            state=self._state,
            error=self._error,
            jid=self.jid,
            error_condition=self._error_info.condition if self._error_info else None,
            error_type=self._error_info.error_type if self._error_info else None,
            stream_management=sm_summary,
        )

    def _current_sm_id(self) -> str | None:
        if not self._client or "xep_0198" not in self._client.plugins:
            return None
        return self._client["xep_0198"].sm_id

    def _sm_plugin(self):
        if self._client and "xep_0198" in self._client.plugins:
            return self._client["xep_0198"]
        return None

    def _persist_sm_state(self) -> None:
        if not self.data_dir or not self.stream_management_enabled:
            return
        plugin = self._sm_plugin()
        if not plugin or not plugin.sm_id:
            return
        save_sm_state(
            self.data_dir,
            StreamManagementState(
                jid=self.jid,
                sm_id=plugin.sm_id,
                handled=int(plugin.handled),
                last_ack=int(plugin.last_ack),
            ),
        )

    def _clear_sm_state(self) -> None:
        if self.data_dir:
            clear_sm_state(self.data_dir)

    def _load_sm_config(self) -> dict[str, Any]:
        if not self.data_dir or not self.stream_management_enabled:
            return {}
        saved = load_sm_state(self.data_dir, self.jid)
        if not saved or not saved.sm_id:
            return {}
        return {
            "sm_id": saved.sm_id,
            "handled": saved.handled,
            "last_ack": saved.last_ack,
            "allow_resume": True,
        }

    def _set_error_from_exception(self, exc: BaseException) -> None:
        self._error_info = parse_xmpp_error(exc)
        self._error = self._error_info.text or str(exc)
        if self._error_info.condition:
            logger.warning(
                "XMPP error condition=%s type=%s: %s",
                self._error_info.condition,
                self._error_info.error_type,
                self._error,
            )

    async def connect(self, **kwargs: Any) -> None:
        self._should_reconnect = True
        await self._do_connect()

    async def _do_connect(self) -> None:
        if self._state == ConnectionState.CONNECTED:
            return

        self._state = ConnectionState.CONNECTING
        self._error = None
        self._error_info = None
        await self._emit_state(self._state)

        try:
            self._client = XMPPClient(
                self.jid,
                self.password,
                server=self.server or None,
                port=self.port,
                transport=self,
                stream_management_enabled=self.stream_management_enabled,
                sm_config=self._load_sm_config(),
            )
            if self.enforce_tls:
                self._client.use_ssl = False
                self._client.use_tls = True

            self._connect_task = asyncio.create_task(self._client.connect())
            await asyncio.wait_for(self._connect_task, timeout=30.0)
        except Exception as exc:  # noqa: BLE001
            self._state = ConnectionState.ERROR
            self._set_error_from_exception(exc)
            logger.exception("XMPP connection failed")
            await self._emit_state(self._state, self._error)
            if self._should_reconnect:
                self._schedule_reconnect()
            raise

    async def _handle_connected(self) -> None:
        self._state = ConnectionState.CONNECTED
        self._error = None
        self._error_info = None
        self._backoff = 1.0
        self._sm_active = bool(self._current_sm_id())
        self._start_ping_loop()
        await self._emit_state(self._state)
        logger.info("XMPP connected as %s (SM=%s)", self.jid, self._sm_active)

    async def _handle_disconnected(self) -> None:
        self._stop_ping_loop()
        if self._state == ConnectionState.DISCONNECTED:
            return
        self._state = ConnectionState.DISCONNECTED
        self._sm_active = False
        await self._emit_state(self._state)
        if self._should_reconnect:
            self._schedule_reconnect()

    def _start_ping_loop(self) -> None:
        self._stop_ping_loop()
        if self.ping_interval_seconds <= 0:
            return

        async def _loop() -> None:
            while self._state == ConnectionState.CONNECTED and self._should_reconnect:
                await asyncio.sleep(self.ping_interval_seconds)
                if self._state != ConnectionState.CONNECTED:
                    break
                ok = await self._ping_with_timeout()
                if not ok:
                    logger.warning("XMPP ping failed — treating connection as dead")
                    if self._client:
                        try:
                            await self._client.disconnect()
                        except Exception:  # noqa: BLE001
                            pass
                    await self._handle_disconnected()
                    break

        self._ping_task = asyncio.create_task(_loop())

    def _stop_ping_loop(self) -> None:
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
        self._ping_task = None

    async def _ping_with_timeout(self) -> bool:
        if not self._client or self._state != ConnectionState.CONNECTED:
            return False
        try:
            await asyncio.wait_for(
                self._client["xep_0199"].ping(),
                timeout=float(self.ping_timeout_seconds),
            )
            return True
        except (IqError, IqTimeout, TimeoutError) as exc:
            self._set_error_from_exception(exc)
            return False

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
        self._stop_ping_loop()
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        self._persist_sm_state()
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._state = ConnectionState.DISCONNECTED
        self._sm_active = False
        await self._emit_state(self._state)

    async def send_message(self, to_jid: str, body: str, message_id: str | None = None) -> str:
        if not self._client or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("XMPP transport not connected")
        mid = message_id or str(uuid4())
        self._client.send_message(mto=to_jid, mbody=body, mtype="chat", mid=mid)
        return mid

    async def send_sync_iq(self, to_jid: str, payload: dict[str, Any]) -> None:
        if not self._client or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("XMPP transport not connected")
        iq = self._client.Iq()
        iq["type"] = "set"
        iq["to"] = to_jid
        iq["id"] = str(uuid4())
        encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
        iq["addressbook_update"]["payload"] = encoded
        await iq.send()

    async def set_presence(self, show: str = "available", status: str = "") -> None:
        if not self._client or self._state != ConnectionState.CONNECTED:
            return
        if show == "available":
            await self._client.send_presence(pstatus=status)
        else:
            await self._client.send_presence(pshow=show, pstatus=status)

    async def ping(self) -> bool:
        return await self._ping_with_timeout()
