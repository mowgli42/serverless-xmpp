"""Shared data models for xmpp-p2p-chat."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

JID_PATTERN = re.compile(r"^[^@\s]+@[^@\s/]+$")


class MessageDirection(StrEnum):
    IN = "in"
    OUT = "out"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class DirectEndpoint(BaseModel):
    host: str
    port: int = 5222
    public_key_fingerprint: str | None = None


class ContactCredentials(BaseModel):
    username: str | None = None
    password_ref: str | None = None
    password: str | None = None  # dev-only inline password


class Contact(BaseModel):
    id: str
    jid: str
    name: str
    avatar: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    preferred_transport: str = "xmpp-server"
    xmpp_server: str | None = None
    direct: DirectEndpoint | None = None
    credentials: ContactCredentials | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("jid")
    @classmethod
    def validate_jid(cls, value: str) -> str:
        if not JID_PATTERN.match(value):
            raise ValueError(f"Invalid JID format: {value}")
        return value.lower()


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    chat_id: str
    direction: MessageDirection
    body: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stanza_id: str | None = None
    delivered: bool = False
    read: bool = False
    status: DeliveryStatus = DeliveryStatus.PENDING
    raw_stanza: dict[str, Any] | None = None


class ChatSession(BaseModel):
    chat_id: str
    contact_id: str
    remote_jid: str
    transport: str = "xmpp-server"
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PresenceInfo(BaseModel):
    contact_id: str
    show: str = "offline"
    status: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AddressBook(BaseModel):
    contacts: list[Contact] = Field(default_factory=list)


class ConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class TransportStatus(BaseModel):
    transport: str
    state: ConnectionState
    error: str | None = None
    jid: str | None = None


class HealthStatus(BaseModel):
    ok: bool
    uptime_seconds: float
    contact_count: int
    active_chats: int
    pending_outbox: int
    warnings: list[str] = Field(default_factory=list)
