"""WebSocket JSON-RPC API layer."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import websockets

from xmpp_p2p_chat.common.models import Contact, HealthStatus
from xmpp_p2p_chat.common.structured_logging import log_event

logger = logging.getLogger(__name__)

ClientConnection = websockets.ServerConnection


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class RpcServer:
    def __init__(self, service: ConnectionService) -> None:  # noqa: F821
        self.service = service
        self.clients: set[ClientConnection] = set()
        self._authenticated: set[ClientConnection] = set()
        self._started_at = datetime.now(UTC)

    async def handle_client(self, websocket: ClientConnection) -> None:
        self.clients.add(websocket)
        token_required = bool(self.service.config.api_token)
        if not token_required:
            self._authenticated.add(websocket)
        logger.info("Client connected (%d total)", len(self.clients))
        log_event(
            logger,
            logging.INFO,
            "rpc.client.connected",
            client_count=len(self.clients),
            auth_required=token_required,
        )
        try:
            async for raw in websocket:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_error(websocket, None, -32700, "Parse error")
                    continue

                if token_required and websocket not in self._authenticated:
                    if message.get("method") == "auth":
                        token = (message.get("params") or {}).get("token", "")
                        if token == self.service.config.api_token:
                            self._authenticated.add(websocket)
                            await self._send_result(websocket, message.get("id"), {"ok": True})
                        else:
                            await self._send_error(websocket, message.get("id"), -32001, "Unauthorized")
                            await websocket.close(code=4001, reason="Unauthorized")
                        continue
                    await self._send_error(websocket, message.get("id"), -32001, "Auth required")
                    continue

                if "method" in message:
                    await self._handle_request(websocket, message)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            self._authenticated.discard(websocket)
            logger.info("Client disconnected (%d remaining)", len(self.clients))
            log_event(
                logger,
                logging.INFO,
                "rpc.client.disconnected",
                client_count=len(self.clients),
            )

    async def _handle_request(self, websocket: ClientConnection, message: dict) -> None:
        req_id = message.get("id")
        method = message.get("method", "")
        params = message.get("params") or {}

        try:
            result = await self._dispatch(method, params)
            if req_id is not None:
                await self._send_result(websocket, req_id, result)
        except JsonRpcError as exc:
            await self._send_error(websocket, req_id, exc.code, exc.message, exc.data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("RPC error for %s", method)
            log_event(
                logger,
                logging.ERROR,
                "rpc.error",
                method=method,
                error=str(exc),
            )
            await self._send_error(websocket, req_id, -32603, str(exc))

    async def _dispatch(self, method: str, params: dict) -> Any:
        svc = self.service

        if method == "addressbook.list":
            contacts = svc.addressbook.list()
            presence_map = {}
            for c in contacts:
                show, status = await svc.persistence.get_presence(c.id)
                presence_map[c.id] = {"show": show, "status": status}
            ab_status = svc.addressbook.status().model_dump(mode="json")
            return {
                "contacts": [c.model_dump(mode="json") for c in contacts],
                "presence": presence_map,
                "status": ab_status,
            }

        if method == "addressbook.status":
            return svc.addressbook.status().model_dump(mode="json")

        if method == "addressbook.reload":
            svc.addressbook.reload()
            return svc.addressbook.status().model_dump(mode="json")

        if method == "addressbook.add":
            contact_data = params.get("contact", params)
            if "id" not in contact_data:
                contact_data["id"] = str(uuid4())
            contact = Contact.model_validate(contact_data)
            added = svc.addressbook.add(contact)
            return {"id": added.id, "contact": added.model_dump(mode="json")}

        if method == "addressbook.update":
            contact_id = params["id"]
            partial = params.get("partial", {k: v for k, v in params.items() if k != "id"})
            updated = svc.addressbook.update(contact_id, partial)
            return {"contact": updated.model_dump(mode="json")}

        if method == "addressbook.remove":
            svc.addressbook.remove(params["id"])
            return {"ok": True}

        if method == "chat.start":
            session = await svc.sessions.start_chat(params["contact_id"])
            return {"chat_id": session.chat_id, "session": session.model_dump(mode="json")}

        if method == "chat.send_message":
            message = await svc.sessions.send_message(params["chat_id"], params["body"])
            return {"message": message.model_dump(mode="json")}

        if method == "chat.get_history":
            before = None
            if params.get("before"):
                before = datetime.fromisoformat(params["before"])
            messages = await svc.sessions.get_history(
                params["chat_id"],
                limit=int(params.get("limit", 50)),
                before=before,
            )
            return {"messages": [m.model_dump(mode="json") for m in messages]}

        if method == "presence.set":
            await svc.sessions.set_presence(params.get("show", "available"), params.get("status", ""))
            return {"ok": True}

        if method == "connection.status":
            statuses = svc.sessions.connection_status()
            result = {"transports": [s.model_dump(mode="json") for s in statuses]}
            fp = svc.sessions.p2p_fingerprint()
            if fp:
                result["p2p_fingerprint"] = fp
                result["p2p_listen_port"] = svc.config.p2p.listen_port
            return result

        if method == "connection.reconnect":
            await svc.sessions.reconnect()
            return {"ok": True}

        if method == "discovery.list":
            peers = svc.sessions.discovered_peers()
            return {
                "peers": [
                    {
                        "jid": p.jid,
                        "host": p.host,
                        "port": p.port,
                        "fingerprint": p.fingerprint,
                        "service_name": p.service_name,
                    }
                    for p in peers
                ]
            }

        if method == "discovery.apply":
            contact = svc.sessions.apply_discovered_endpoint(params["contact_id"])
            if not contact:
                raise JsonRpcError(-32004, "No matching discovered peer for contact")
            return {"contact": contact.model_dump(mode="json")}

        if method == "system.health":
            uptime = (datetime.now(UTC) - self._started_at).total_seconds()
            health = HealthStatus(
                ok=len(svc.addressbook.warnings) == 0,
                uptime_seconds=uptime,
                contact_count=len(svc.addressbook.contacts),
                active_chats=len(svc.sessions._sessions),
                pending_outbox=await svc.persistence.pending_outbox_count(),
                warnings=svc.addressbook.warnings,
            )
            return health.model_dump(mode="json")

        if method == "system.shutdown":
            asyncio.create_task(svc.shutdown())
            return {"ok": True}

        raise JsonRpcError(-32601, f"Method not found: {method}")

    async def broadcast(self, event: str, params: dict) -> None:
        if not self.clients:
            return
        payload = json.dumps({"jsonrpc": "2.0", "method": event, "params": params}, default=str)
        dead: list[ClientConnection] = []
        for client in self.clients:
            if self.service.config.api_token and client not in self._authenticated:
                continue
            try:
                await client.send(payload)
            except websockets.ConnectionClosed:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)
            self._authenticated.discard(client)

    async def _send_result(self, websocket: ClientConnection, req_id: Any, result: Any) -> None:
        await websocket.send(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, default=str))

    async def _send_error(
        self,
        websocket: ClientConnection,
        req_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }
        if data is not None:
            payload["error"]["data"] = data
        await websocket.send(json.dumps(payload, default=str))
