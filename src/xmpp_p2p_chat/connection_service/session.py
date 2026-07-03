"""Session and chat routing with pluggable transport selection."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from xmpp_p2p_chat.common.config import AppConfig
from xmpp_p2p_chat.common.models import (
    ChatSession,
    ConnectionState,
    Contact,
    DeliveryStatus,
    Message,
    MessageDirection,
    TransportStatus,
)
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager
from xmpp_p2p_chat.connection_service.transports.base import BaseTransport
from xmpp_p2p_chat.connection_service.transports.direct_p2p import DirectP2PTransport, PeerEndpoint
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
        self._xmpp: XMPPServerTransport | None = None
        self._p2p: DirectP2PTransport | None = None
        self._sessions: dict[str, ChatSession] = {}
        self._jid_to_contact: dict[str, str] = {}

    async def initialize(self) -> None:
        for contact in self.addressbook.contacts:
            self._jid_to_contact[contact.jid.lower()] = contact.id

        if self._needs_p2p():
            await self._ensure_p2p()

        if self._needs_xmpp():
            await self._ensure_xmpp()

        for session in await self.persistence.list_active_chats():
            self._sessions[session.chat_id] = session

    def _needs_p2p(self) -> bool:
        if self.config.p2p.local_jid:
            return True
        return any(
            c.preferred_transport == "direct-p2p" or c.direct for c in self.addressbook.contacts
        )

    def _needs_xmpp(self) -> bool:
        if not (self.config.xmpp.jid and self.config.xmpp.password):
            return False
        if self.config.default_transport == "xmpp-server":
            return True
        return any(c.preferred_transport == "xmpp-server" for c in self.addressbook.contacts)

    async def _ensure_p2p(self) -> DirectP2PTransport:
        if not self._p2p:
            self._p2p = DirectP2PTransport(
                local_jid=self.config.effective_local_jid,
                cert_dir=self.config.p2p_cert_dir,
                listen_host=self.config.p2p.listen_host,
                listen_port=self.config.p2p.listen_port,
                allow_self_signed=self.config.allow_self_signed_direct,
            )
            self._p2p.on_message(self._handle_incoming_message)
            self._p2p.on_presence(self._handle_presence)
            self._p2p.on_state(self._handle_transport_state)
            for contact in self.addressbook.contacts:
                self._register_p2p_peer(contact)

        if not self._p2p._server:  # noqa: SLF001 - startup guard
            await self._p2p.connect()
        return self._p2p

    async def _ensure_xmpp(self) -> XMPPServerTransport:
        if self._xmpp and self._xmpp.status().state == ConnectionState.CONNECTED:
            return self._xmpp

        if not self._xmpp:
            self._xmpp = XMPPServerTransport(
                jid=self.config.xmpp.jid,
                password=self.config.xmpp.password,
                server=self.config.xmpp.server or None,
                port=self.config.xmpp.port,
                enforce_tls=self.config.enforce_tls,
            )
            self._xmpp.on_message(self._handle_incoming_message)
            self._xmpp.on_presence(self._handle_presence)
            self._xmpp.on_state(self._handle_transport_state)

        await self._xmpp.connect()
        return self._xmpp

    def _register_p2p_peer(self, contact: Contact) -> None:
        if not self._p2p or not contact.direct:
            return
        self._p2p.register_peer(
            PeerEndpoint(
                jid=contact.jid,
                host=contact.direct.host,
                port=contact.direct.port,
                fingerprint=contact.direct.public_key_fingerprint,
            )
        )

    def _resolve_transport_name(self, contact: Contact) -> str:
        if contact.preferred_transport == "direct-p2p" and contact.direct:
            return "direct-p2p"
        if contact.preferred_transport == "xmpp-server":
            return "xmpp-server"
        if contact.direct and self.config.default_transport == "direct-p2p":
            return "direct-p2p"
        return self.config.default_transport

    async def _get_transport(self, contact: Contact) -> BaseTransport:
        name = self._resolve_transport_name(contact)
        if name == "direct-p2p":
            if not contact.direct:
                raise ValueError(f"Contact {contact.id} requires direct endpoint for P2P transport")
            p2p = await self._ensure_p2p()
            self._register_p2p_peer(contact)
            await p2p.connect_peer(
                PeerEndpoint(
                    jid=contact.jid,
                    host=contact.direct.host,
                    port=contact.direct.port,
                    fingerprint=contact.direct.public_key_fingerprint,
                )
            )
            return p2p
        return await self._ensure_xmpp()

    async def start_chat(self, contact_id: str) -> ChatSession:
        contact = self.addressbook.get(contact_id)
        if not contact:
            raise ValueError(f"Contact not found: {contact_id}")

        chat_id = contact_id
        existing = self._sessions.get(chat_id)
        if existing:
            return existing

        transport_name = self._resolve_transport_name(contact)
        await self._get_transport(contact)

        session = ChatSession(
            chat_id=chat_id,
            contact_id=contact_id,
            remote_jid=contact.jid,
            transport=transport_name,
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

        contact = self.addressbook.get(session.contact_id)
        if not contact:
            raise ValueError(f"Contact not found for chat: {chat_id}")

        message = Message(
            id=str(uuid4()),
            chat_id=chat_id,
            direction=MessageDirection.OUT,
            body=body,
            timestamp=datetime.now(UTC),
            status=DeliveryStatus.PENDING,
        )

        try:
            transport = await self._get_transport(contact)
            if transport.status().state not in (
                ConnectionState.CONNECTED,
                ConnectionState.CONNECTING,
            ):
                raise RuntimeError(f"Transport {session.transport} not connected")

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

    async def get_history(
        self, chat_id: str, limit: int = 50, before: datetime | None = None
    ) -> list[Message]:
        return await self.persistence.get_history(chat_id, limit=limit, before=before)

    async def set_presence(self, show: str, status: str = "") -> None:
        if self._p2p:
            await self._p2p.set_presence(show, status)
        if self._xmpp and self._xmpp.status().state == ConnectionState.CONNECTED:
            await self._xmpp.set_presence(show, status)

    def connection_status(self) -> list[TransportStatus]:
        statuses: list[TransportStatus] = []
        if self._p2p:
            statuses.append(self._p2p.status())
        elif self._needs_p2p():
            statuses.append(
                TransportStatus(
                    transport="direct-p2p",
                    state=ConnectionState.DISCONNECTED,
                    jid=self.config.effective_local_jid,
                )
            )
        if self._xmpp:
            statuses.append(self._xmpp.status())
        elif self._needs_xmpp():
            statuses.append(
                TransportStatus(
                    transport="xmpp-server",
                    state=ConnectionState.DISCONNECTED,
                    jid=self.config.xmpp.jid or None,
                )
            )
        if not statuses:
            statuses.append(
                TransportStatus(
                    transport=self.config.default_transport,
                    state=ConnectionState.DISCONNECTED,
                )
            )
        return statuses

    def p2p_fingerprint(self) -> str | None:
        return self._p2p.fingerprint if self._p2p else None

    async def reconnect(self) -> None:
        if self._xmpp:
            await self._xmpp.disconnect()
            self._xmpp = None
        if self._p2p:
            await self._p2p.disconnect()
            self._p2p = None
        if self._needs_p2p():
            await self._ensure_p2p()
        if self._needs_xmpp():
            await self._ensure_xmpp()
        await self._drain_outbox()

    async def _handle_incoming_message(
        self, from_jid: str, body: str, stanza_id: str | None
    ) -> None:
        bare = from_jid.split("/")[0].lower()
        contact_id = self._jid_to_contact.get(bare)
        if not contact_id:
            contact_id = bare.split("@")[0]
            self._jid_to_contact[bare] = contact_id

        chat_id = contact_id
        if chat_id not in self._sessions:
            contact = self.addressbook.get(contact_id)
            session = ChatSession(
                chat_id=chat_id,
                contact_id=contact_id,
                remote_jid=bare if "@" in bare else (contact.jid if contact else from_jid),
                transport=contact.preferred_transport if contact else "direct-p2p",
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
        bare = from_jid.split("/")[0].lower()
        contact_id = self._jid_to_contact.get(bare, bare.split("@")[0])
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
        pending = await self.persistence.get_pending_outbox()
        for message in pending:
            session = self._sessions.get(message.chat_id)
            if not session:
                session = await self.persistence.get_chat(message.chat_id)
            if not session:
                continue
            contact = self.addressbook.get(session.contact_id)
            if not contact:
                continue
            try:
                transport = await self._get_transport(contact)
                stanza_id = await transport.send_message(
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
        if self._p2p:
            await self._p2p.disconnect()
        if self._xmpp:
            await self._xmpp.disconnect()
