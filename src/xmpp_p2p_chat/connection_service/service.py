"""Main connection service."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from typing import Any

import websockets

from xmpp_p2p_chat.common.config import AppConfig, load_config
from xmpp_p2p_chat.common.paths import bundled_addressbook_path
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager
from xmpp_p2p_chat.connection_service.api import RpcServer
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager
from xmpp_p2p_chat.connection_service.session import SessionManager
from xmpp_p2p_chat.connection_service.web_server import WebUIServer, find_web_ui_dist

logger = logging.getLogger(__name__)

_LOCALHOST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ConnectionService:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or load_config()
        self._validate_bind_addresses()
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
        self._web_server: WebUIServer | None = None
        self._shutdown_event = asyncio.Event()

    def _validate_bind_addresses(self) -> None:
        if self.config.api_host not in _LOCALHOST_HOSTS:
            logger.warning(
                "API host %s is not localhost — ensure this is intentional (spec requires 127.0.0.1 by default)",
                self.config.api_host,
            )
        if self.config.ui.web_host not in _LOCALHOST_HOSTS:
            logger.warning("Web UI host %s is not localhost", self.config.ui.web_host)

    def _on_push(self, event: str, params: dict[str, Any]) -> None:
        asyncio.create_task(self.rpc.broadcast(event, params))

    def _on_addressbook_updated(self) -> None:
        status = self.addressbook.status().model_dump(mode="json")
        asyncio.create_task(
            self.rpc.broadcast(
                "addressbook.updated",
                {
                    "contacts": len(self.addressbook.contacts),
                    "version": status["version"],
                    "content_hash": status["content_hash"],
                },
            )
        )

    def _resolve_bundled_addressbook(self) -> Path | None:
        if self.config.bundled_addressbook:
            path = Path(self.config.bundled_addressbook).expanduser()
            if path.exists():
                return path.resolve()
        return bundled_addressbook_path()

    def _resolve_web_root(self) -> Path | None:
        if self.config.ui.web_root:
            return Path(self.config.ui.web_root).expanduser().resolve()
        return find_web_ui_dist()

    async def start(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )

        self.addressbook.process_startup(
            bundled_path=self._resolve_bundled_addressbook(),
            import_if_empty=self.config.import_bundled_if_empty,
        )
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

        if self.config.ui.serve_web:
            web_root = self._resolve_web_root()
            if web_root:
                self._web_server = WebUIServer(
                    self.config.ui.web_host,
                    self.config.ui.web_port,
                    web_root,
                )
                self._web_server.start()

    async def run_forever(self) -> None:
        await self.start()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        await self._shutdown_event.wait()

    async def shutdown(self) -> None:
        logger.info("Shutting down connection service...")
        if self._web_server:
            self._web_server.stop()
        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        await self.sessions.shutdown()
        await self.persistence.close()
        self._shutdown_event.set()
