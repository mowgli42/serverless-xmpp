"""Transport layer abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from xmpp_p2p_chat.common.models import ConnectionState, TransportStatus

MessageCallback = Callable[[str, str, str | None], Awaitable[None]]
PresenceCallback = Callable[[str, str, str], Awaitable[None]]
StateCallback = Callable[[TransportStatus], Awaitable[None]]


class BaseTransport(ABC):
    def __init__(self) -> None:
        self._on_message: MessageCallback | None = None
        self._on_presence: PresenceCallback | None = None
        self._on_state: StateCallback | None = None

    def on_message(self, callback: MessageCallback) -> None:
        self._on_message = callback

    def on_presence(self, callback: PresenceCallback) -> None:
        self._on_presence = callback

    def on_state(self, callback: StateCallback) -> None:
        self._on_state = callback

    @abstractmethod
    async def connect(self, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, to_jid: str, body: str, message_id: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def set_presence(self, show: str = "available", status: str = "") -> None:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> TransportStatus:
        raise NotImplementedError

    async def _emit_state(self, state: ConnectionState, error: str | None = None) -> None:
        if self._on_state:
            await self._on_state(self.status())
