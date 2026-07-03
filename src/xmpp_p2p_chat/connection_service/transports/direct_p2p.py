"""Direct peer-to-peer XMPP transport over TLS (XEP-0174 inspired)."""

from __future__ import annotations

import asyncio
import logging
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from xmpp_p2p_chat.common.certs import ensure_p2p_certificates, verify_fingerprint
from xmpp_p2p_chat.common.models import ConnectionState, TransportStatus
from xmpp_p2p_chat.connection_service.transports.base import BaseTransport
from xmpp_p2p_chat.connection_service.transports.xmpp_stream import (
    message_stanza,
    parse_message,
    parse_presence,
    presence_stanza,
    stream_close,
    stream_open,
)

logger = logging.getLogger(__name__)


@dataclass
class PeerEndpoint:
    jid: str
    host: str
    port: int
    fingerprint: str | None = None


@dataclass
class _PeerStream:
    remote_jid: str
    local_jid: str
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    read_task: asyncio.Task | None = None


class DirectP2PTransport(BaseTransport):
    """Manages inbound TLS listener and outbound peer connections for serverless XMPP."""

    def __init__(
        self,
        local_jid: str,
        cert_dir: Path,
        listen_host: str = "0.0.0.0",
        listen_port: int = 5223,
        allow_self_signed: bool = True,
    ) -> None:
        super().__init__()
        self.local_jid = local_jid
        self.cert_dir = cert_dir
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.allow_self_signed = allow_self_signed
        self._cert_path: Path | None = None
        self._key_path: Path | None = None
        self._fingerprint: str = ""
        self._server: asyncio.Server | None = None
        self._peers: dict[str, _PeerStream] = {}
        self._peer_endpoints: dict[str, PeerEndpoint] = {}
        self._state = ConnectionState.DISCONNECTED
        self._error: str | None = None
        self._lock = asyncio.Lock()

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def register_peer(self, endpoint: PeerEndpoint) -> None:
        self._peer_endpoints[endpoint.jid.lower()] = endpoint

    def status(self) -> TransportStatus:
        connected = sum(1 for p in self._peers.values() if not p.writer.is_closing())
        detail = f"{connected} peer(s) on :{self.listen_port}"
        return TransportStatus(
            transport="direct-p2p",
            state=self._state,
            error=self._error,
            jid=f"{self.local_jid} ({detail})",
        )

    async def connect(self, **kwargs: Any) -> None:
        """Start the inbound TLS listener."""
        if self._server:
            return

        self._cert_path, self._key_path, self._fingerprint = ensure_p2p_certificates(
            self.cert_dir, common_name=self.local_jid.split("@")[0]
        )
        ssl_ctx = self._server_ssl_context()
        self._server = await asyncio.start_server(
            self._connection_handler,
            host=self.listen_host,
            port=self.listen_port,
            ssl=ssl_ctx,
        )
        self._state = ConnectionState.CONNECTED
        self._error = None
        await self._emit_state(self._state)
        logger.info(
            "Direct P2P listening on %s:%d (fingerprint %s)",
            self.listen_host,
            self.listen_port,
            self._fingerprint,
        )

    async def connect_peer(self, endpoint: PeerEndpoint) -> None:
        """Establish or verify outbound TLS+XMPP stream to a peer."""
        jid_key = endpoint.jid.lower()
        existing = self._peers.get(jid_key)
        if existing and not existing.writer.is_closing():
            return

        ssl_ctx = self._client_ssl_context(endpoint.fingerprint)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(endpoint.host, endpoint.port, ssl=ssl_ctx),
                timeout=15.0,
            )
        except Exception as exc:
            self._state = ConnectionState.ERROR
            self._error = f"Peer connect failed ({endpoint.jid}): {exc}"
            logger.warning(self._error)
            await self._emit_state(self._state, self._error)
            raise

        if endpoint.fingerprint:
            ssl_obj = writer.get_extra_info("ssl_object")
            peer_cert = ssl_obj.getpeercert(binary_form=True) if ssl_obj else None
            if not verify_fingerprint(peer_cert, endpoint.fingerprint, der=True):
                writer.close()
                raise ssl.SSLError(f"Certificate fingerprint mismatch for {endpoint.jid}")

        writer.write(stream_open(self.local_jid, endpoint.jid).encode("utf-8"))
        await writer.drain()
        await self._read_stream_open(reader)

        peer = _PeerStream(
            remote_jid=endpoint.jid,
            local_jid=self.local_jid,
            reader=reader,
            writer=writer,
        )
        peer.read_task = asyncio.create_task(self._read_loop(peer))
        async with self._lock:
            self._peers[jid_key] = peer
        self._peer_endpoints[jid_key] = endpoint
        logger.info("Connected to peer %s at %s:%d", endpoint.jid, endpoint.host, endpoint.port)

    async def disconnect(self) -> None:
        async with self._lock:
            for peer in list(self._peers.values()):
                await self._close_peer(peer)
            self._peers.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._state = ConnectionState.DISCONNECTED
        await self._emit_state(self._state)

    async def send_message(self, to_jid: str, body: str, message_id: str | None = None) -> str:
        jid_key = to_jid.lower()
        peer = self._peers.get(jid_key)
        if not peer or peer.writer.is_closing():
            endpoint = self._peer_endpoints.get(jid_key)
            if not endpoint:
                raise RuntimeError(f"No P2P endpoint configured for {to_jid}")
            await self.connect_peer(endpoint)
            peer = self._peers[jid_key]

        mid = message_id or str(uuid4())
        stanza = message_stanza(self.local_jid, to_jid, body, mid)
        peer.writer.write(stanza.encode("utf-8"))
        await peer.writer.drain()
        return mid

    async def set_presence(self, show: str = "available", status: str = "") -> None:
        async with self._lock:
            peers = list(self._peers.values())
        for peer in peers:
            if peer.writer.is_closing():
                continue
            stanza = presence_stanza(self.local_jid, peer.remote_jid, show, status)
            peer.writer.write(stanza.encode("utf-8"))
            await peer.writer.drain()

    def _connection_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        logger.info("Inbound P2P TCP connection accepted")
        asyncio.create_task(self._handle_inbound(reader, writer))

    async def _handle_inbound(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            header = await self._read_stream_open(reader)
            if not header or b"<stream:stream" not in header:
                return
            from_jid, to_jid = self._parse_stream_jids(header)
            remote_jid = from_jid or to_jid
            if not remote_jid:
                logger.warning("Inbound P2P stream missing JID")
                return

            endpoint = self._peer_endpoints.get(remote_jid.lower())
            if endpoint and endpoint.fingerprint:
                ssl_obj = writer.get_extra_info("ssl_object")
                peer_cert = ssl_obj.getpeercert(binary_form=True) if ssl_obj else None
                if peer_cert and not verify_fingerprint(
                    peer_cert, endpoint.fingerprint, der=True
                ):
                    logger.error("Rejected inbound P2P: fingerprint mismatch for %s", remote_jid)
                    writer.close()
                    return
                if not peer_cert and not self.allow_self_signed:
                    logger.error("Rejected inbound P2P: no client certificate from %s", remote_jid)
                    writer.close()
                    return

            response = stream_open(self.local_jid, remote_jid)
            writer.write(response.encode("utf-8"))
            await writer.drain()

            peer = _PeerStream(
                remote_jid=remote_jid,
                local_jid=self.local_jid,
                reader=reader,
                writer=writer,
            )
            peer.read_task = asyncio.create_task(self._read_loop(peer))
            async with self._lock:
                self._peers[remote_jid.lower()] = peer
            logger.info("Accepted inbound P2P stream from %s", remote_jid)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Inbound P2P handler error: %s", exc)
            writer.close()

    async def _read_loop(self, peer: _PeerStream) -> None:
        buffer = b""
        try:
            while True:
                chunk = await peer.reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while True:
                    stanza, buffer = self._extract_stanza(buffer)
                    if stanza is None:
                        break
                    await self._dispatch_stanza(stanza.decode("utf-8", errors="replace"))
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("P2P read loop ended for %s: %s", peer.remote_jid, exc)
        finally:
            async with self._lock:
                self._peers.pop(peer.remote_jid.lower(), None)
            await self._close_peer(peer)

    async def _dispatch_stanza(self, stanza_xml: str) -> None:
        if msg := parse_message(stanza_xml):
            from_jid, body, stanza_id = msg
            if self._on_message:
                await self._on_message(from_jid, body, stanza_id)
            return
        if pres := parse_presence(stanza_xml):
            from_jid, show, status = pres
            if self._on_presence:
                await self._on_presence(from_jid, show, status)

    async def _close_peer(self, peer: _PeerStream) -> None:
        if peer.read_task and not peer.read_task.done():
            peer.read_task.cancel()
        try:
            peer.writer.write(stream_close().encode("utf-8"))
            await peer.writer.drain()
        except Exception:  # noqa: BLE001
            pass
        peer.writer.close()
        try:
            await peer.writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass

    def _server_ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        assert self._cert_path and self._key_path
        ctx.load_cert_chain(str(self._cert_path), str(self._key_path))
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _client_ssl_context(self, expected_fingerprint: str | None) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        assert self._cert_path and self._key_path
        ctx.load_cert_chain(str(self._cert_path), str(self._key_path))
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    @staticmethod
    async def _read_stream_open(reader: asyncio.StreamReader, limit: int = 8192) -> bytes:
        """Read a complete XMPP stream opening tag (past the XML declaration)."""
        data = b""
        while len(data) < limit:
            chunk = await reader.read(512)
            if not chunk:
                break
            data += chunk
            marker = b"<stream:stream"
            start = data.find(marker)
            if start == -1:
                continue
            end = data.find(b">", start)
            if end != -1:
                return data[: end + 1]
        return data

    @staticmethod
    async def _read_until(
        reader: asyncio.StreamReader, marker: bytes, limit: int = 8192
    ) -> bytes:
        data = b""
        while marker not in data and len(data) < limit:
            chunk = await reader.read(512)
            if not chunk:
                break
            data += chunk
        return data

    @staticmethod
    def _parse_stream_jids(header: bytes) -> tuple[str, str]:
        text = header.decode("utf-8", errors="replace")
        import re

        from_match = re.search(r"from=['\"]([^'\"]+)['\"]", text)
        to_match = re.search(r"to=['\"]([^'\"]+)['\"]", text)
        return (
            from_match.group(1) if from_match else "",
            to_match.group(1) if to_match else "",
        )

    @staticmethod
    def _extract_stanza(buffer: bytes) -> tuple[bytes | None, bytes]:
        """Extract one complete top-level XML element from buffer."""
        text = buffer.decode("utf-8", errors="replace")
        for tag in ("message", "presence", "iq"):
            start = text.find(f"<{tag}")
            if start == -1:
                continue
            end_tag = f"</{tag}>"
            end = text.find(end_tag, start)
            if end == -1:
                return None, buffer
            end += len(end_tag)
            stanza = text[start:end].encode("utf-8")
            rest = (text[end:]).encode("utf-8")
            return stanza, rest
        if len(buffer) > 65536:
            return None, b""
        return None, buffer
