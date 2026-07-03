"""Main connection service."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

import websockets

from xmpp_p2p_chat.common.config import AppConfig, load_config
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager
from xmpp_p2p_chat.connection_service.api import RpcServer
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager
from xmpp_p2p_chat.connection_service.session import SessionManager

logger = logging.getLogger(__name__)


class ConnectionService:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_config()
        self.addressbook = AddressBookManager(
            primary_path=self.config.addressbook_path,
            fragments_dir=self.config.addressbooks_dir,
            on_updated=self._on_addressbook_updated,
        )
        self.persistence = PersistenceManager(self.config.db_path)
        self.rpc = RpcServer(self)
        self.sessions = SessionManager(
            config=self.config,
            addressbook=self.addressbook,
            persistence=self.persistence,
            on_push=self._on_push,
        )
        self._ws_server: websockets.server.Serve | None = None
        self._shutdown_event = asyncio.Event()

    def _on_push(self, event: str, params: dict[str, Any]) -> None:
        asyncio.create_task(self.rpc.broadcast(event, params))

    def _on_addressbook_updated(self) -> None:
        asyncio.create_task(
            self.rpc.broadcast("addressbook.updated", {"contacts": len(self.addressbook.contacts)})
        )

    async def start(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )

        self.addressbook.load()
        await self.persistence.initialize()
        await self.sessions.initialize()

        host = self.config.api_host
        port = self.config.api_port
        self._ws_server = await websockets.serve(
            self.rpc.handle_client,
            host,
            port,
            ping_interval=20,
            ping_timeout=20,
        )
        logger.info(
            "Connection service listening on ws://%s:%d/rpc (%d contacts)",
            host,
            port,
            len(self.addressbook.contacts),
        )

    async def run_forever(self) -> None:
        await self.start()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        await self._shutdown_event.wait()

    async def shutdown(self) -> None:
        logger.info("Shutting down connection service...")
        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        await self.sessions.shutdown()
        await self.persistence.close()
        self._shutdown_event.set()
