"""Session and chat routing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from xmpp_p2p_chat.common.config import AppConfig
from xmpp_p2p_chat.common.models import (
    ChatSession,
    ConnectionState,
    DeliveryStatus,
    Message,
    MessageDirection,
    TransportStatus,
)
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager
from xmpp_p2p_chat.connection_service.transports.xmpp_server import XMPPServerTransport

logger = logging.getLogger(__name__)

PushCallback = Callable[[str, dict], None]


class SessionManager:
    def __init__(
        self,
        config: AppConfig,
        addressbook: AddressBookManager,
        persistence: PersistenceManager,
        on_push: PushCallback,
    ) -> None:
        self.config = config
        self.addressbook = addressbook
        self.persistence = persistence
        self.on_push = on_push
        self._transport: XMPPServerTransport | None = None
        self._sessions: dict[str, ChatSession] = {}
        self._jid_to_contact: dict[str, str] = {}

    async def initialize(self) -> None:
        for contact in self.addressbook.contacts:
            self._jid_to_contact[contact.jid.lower()] = contact.id

        if self.config.xmpp.jid and self.config.xmpp.password:
            await self._ensure_transport()

        for session in await self.persistence.list_active_chats():
            self._sessions[session.chat_id] = session

    async def _ensure_transport(self) -> XMPPServerTransport:
        if self._transport and self._transport.status().state == ConnectionState.CONNECTED:
            return self._transport

        if not self._transport:
            self._transport = XMPPServerTransport(
                jid=self.config.xmpp.jid,
                password=self.config.xmpp.password,
                server=self.config.xmpp.server or None,
                port=self.config.xmpp.port,
                enforce_tls=self.config.enforce_tls,
            )
            self._transport.on_message(self._handle_incoming_message)
            self._transport.on_presence(self._handle_presence)
            self._transport.on_state(self._handle_transport_state)

        await self._transport.connect()
        return self._transport

    async def start_chat(self, contact_id: str) -> ChatSession:
        contact = self.addressbook.get(contact_id)
        if not contact:
            raise ValueError(f"Contact not found: {contact_id}")

        chat_id = contact_id
        existing = self._sessions.get(chat_id)
        if existing:
            return existing

        await self._ensure_transport()

        session = ChatSession(
            chat_id=chat_id,
            contact_id=contact_id,
            remote_jid=contact.jid,
            transport=contact.preferred_transport,
        )
        self._sessions[chat_id] = session
        self._jid_to_contact[contact.jid.lower()] = contact_id
        await self.persistence.save_chat(session)
        return session

    async def send_message(self, chat_id: str, body: str) -> Message:
        session = self._sessions.get(chat_id)
        if not session:
            session = await self.persistence.get_chat(chat_id)
            if session:
                self._sessions[chat_id] = session
        if not session:
            raise ValueError(f"Chat not found: {chat_id}")

        message = Message(
            id=str(uuid4()),
            chat_id=chat_id,
            direction=MessageDirection.OUT,
            body=body,
            timestamp=datetime.now(UTC),
            status=DeliveryStatus.PENDING,
        )

        transport = self._transport
        if transport and transport.status().state == ConnectionState.CONNECTED:
            try:
                stanza_id = await transport.send_message(session.remote_jid, body, message.id)
                message.stanza_id = stanza_id
                message.status = DeliveryStatus.SENT
                message.delivered = True
                await self.persistence.save_message(message)
                self.on_push(
                    "message.updated",
                    {"chat_id": chat_id, "message": message.model_dump(mode="json")},
                )
                return message
            except Exception as exc:  # noqa: BLE001
                logger.warning("Send failed, queueing: %s", exc)
                message.status = DeliveryStatus.PENDING
                await self.persistence.queue_outbound(message)
                self.on_push(
                    "message.updated",
                    {"chat_id": chat_id, "message": message.model_dump(mode="json")},
                )
                return message

        message.status = DeliveryStatus.PENDING
        await self.persistence.queue_outbound(message)
        self.on_push(
            "message.updated",
            {"chat_id": chat_id, "message": message.model_dump(mode="json")},
        )
        return message

    async def get_history(
        self, chat_id: str, limit: int = 50, before: datetime | None = None
    ) -> list[Message]:
        return await self.persistence.get_history(chat_id, limit=limit, before=before)

    async def set_presence(self, show: str, status: str = "") -> None:
        if self._transport:
            await self._transport.set_presence(show, status)

    def connection_status(self) -> list[TransportStatus]:
        if self._transport:
            return [self._transport.status()]
        return [
            TransportStatus(
                transport="xmpp-server",
                state=ConnectionState.DISCONNECTED,
                jid=self.config.xmpp.jid or None,
            )
        ]

    async def reconnect(self) -> None:
        if self._transport:
            await self._transport.disconnect()
        self._transport = None
        await self._ensure_transport()
        await self._drain_outbox()

    async def _handle_incoming_message(
        self, from_jid: str, body: str, stanza_id: str | None
    ) -> None:
        contact_id = self._jid_to_contact.get(from_jid.lower())
        if not contact_id:
            contact_id = from_jid.lower().split("@")[0]
            self._jid_to_contact[from_jid.lower()] = contact_id

        chat_id = contact_id
        if chat_id not in self._sessions:
            contact = self.addressbook.get(contact_id)
            session = ChatSession(
                chat_id=chat_id,
                contact_id=contact_id,
                remote_jid=from_jid if "@" in from_jid else (contact.jid if contact else from_jid),
            )
            self._sessions[chat_id] = session
            await self.persistence.save_chat(session)

        message = Message(
            chat_id=chat_id,
            direction=MessageDirection.IN,
            body=body,
            stanza_id=stanza_id,
            delivered=True,
            status=DeliveryStatus.DELIVERED,
        )
        await self.persistence.save_message(message)
        self.on_push(
            "message.received",
            {"chat_id": chat_id, "message": message.model_dump(mode="json")},
        )

    async def _handle_presence(self, from_jid: str, show: str, status: str) -> None:
        contact_id = self._jid_to_contact.get(from_jid.lower(), from_jid.lower())
        await self.persistence.save_presence(contact_id, show, status)
        self.on_push(
            "presence.updated",
            {"contact_id": contact_id, "show": show, "status": status},
        )

    async def _handle_transport_state(self, status: TransportStatus) -> None:
        self.on_push("connection.changed", status.model_dump(mode="json"))
        if status.state == ConnectionState.CONNECTED:
            await self._drain_outbox()

    async def _drain_outbox(self) -> None:
        if not self._transport or self._transport.status().state != ConnectionState.CONNECTED:
            return
        pending = await self.persistence.get_pending_outbox()
        for message in pending:
            session = self._sessions.get(message.chat_id)
            if not session:
                session = await self.persistence.get_chat(message.chat_id)
            if not session:
                continue
            try:
                stanza_id = await self._transport.send_message(
                    session.remote_jid, message.body, message.id
                )
                await self.persistence.mark_sent(message.id, stanza_id)
                await self.persistence.mark_delivered(message.id)
                message.status = DeliveryStatus.DELIVERED
                message.delivered = True
                self.on_push(
                    "message.updated",
                    {"chat_id": message.chat_id, "message": message.model_dump(mode="json")},
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Outbox drain failed for %s: %s", message.id, exc)

    async def shutdown(self) -> None:
        if self._transport:
            await self._transport.disconnect()
