"""mDNS LAN discovery for direct P2P peers (XEP-0174 inspired)."""

from __future__ import annotations

import logging
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass

from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_TYPE = "_xmpp-p2p._tcp.local."
_JID_SAFE = re.compile(r"[^a-zA-Z0-9-]")


@dataclass
class DiscoveredPeer:
    jid: str
    host: str
    port: int
    fingerprint: str | None = None
    service_name: str = ""


def _local_lan_ip() -> str:
    """Best-effort LAN address for mDNS advertisement."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _jid_to_service_name(jid: str) -> str:
    local, _, domain = jid.partition("@")
    safe_local = _JID_SAFE.sub("-", local) or "peer"
    safe_domain = _JID_SAFE.sub("-", domain.replace(".", "-")) or "local"
    return f"{safe_local}-{safe_domain}"


def _decode_prop(props: dict[bytes, bytes] | None, key: str) -> str | None:
    if not props:
        return None
    raw = props.get(key.encode()) or props.get(key.upper().encode())
    if raw is None:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


class _MdnsListener:
    def __init__(self, owner: MdnsDiscovery) -> None:
        self._owner = owner

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._owner._handle_service(zc, type_, name, ServiceStateChange.Added)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._owner._handle_service(zc, type_, name, ServiceStateChange.Removed)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self._owner._handle_service(zc, type_, name, ServiceStateChange.Updated)


class MdnsDiscovery:
    """Advertise this node and browse for peers on the local network."""

    def __init__(
        self,
        local_jid: str,
        listen_port: int,
        fingerprint: str,
        service_type: str = DEFAULT_SERVICE_TYPE,
        on_updated: Callable[[], None] | None = None,
    ) -> None:
        self.local_jid = local_jid
        self.listen_port = listen_port
        self.fingerprint = fingerprint
        self.service_type = service_type if service_type.endswith(".") else f"{service_type}."
        self._on_updated = on_updated
        self._zeroconf: Zeroconf | None = None
        self._browser: ServiceBrowser | None = None
        self._registered_name: str | None = None
        self._peers: dict[str, DiscoveredPeer] = {}

    @property
    def peers(self) -> list[DiscoveredPeer]:
        return sorted(self._peers.values(), key=lambda p: p.jid)

    def start(self) -> None:
        if self._zeroconf:
            return
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self._register_service()
        listener = _MdnsListener(self)
        self._browser = ServiceBrowser(self._zeroconf, self.service_type, listener)
        logger.info("mDNS discovery started for %s on port %d", self.local_jid, self.listen_port)

    def stop(self) -> None:
        if not self._zeroconf:
            return
        if self._browser:
            self._browser.cancel()
            self._browser = None
        if self._registered_name:
            try:
                self._zeroconf.unregister_service(
                    ServiceInfo(self.service_type, self._registered_name)
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("mDNS unregister: %s", exc)
            self._registered_name = None
        self._zeroconf.close()
        self._zeroconf = None
        self._peers.clear()

    def _register_service(self) -> None:
        assert self._zeroconf is not None
        lan_ip = _local_lan_ip()
        service_name = _jid_to_service_name(self.local_jid)
        full_name = f"{service_name}.{self.service_type}"
        props = {
            b"jid": self.local_jid.encode("utf-8"),
            b"fp": self.fingerprint.encode("utf-8"),
            b"transport": b"direct-p2p",
        }
        info = ServiceInfo(
            self.service_type,
            full_name,
            addresses=[socket.inet_aton(lan_ip)],
            port=self.listen_port,
            properties=props,
        )
        self._zeroconf.register_service(info)
        self._registered_name = full_name
        logger.debug("mDNS registered %s at %s:%d", full_name, lan_ip, self.listen_port)

    def _handle_service(
        self,
        zc: Zeroconf,
        type_: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if self._registered_name and name == self._registered_name:
            return

        if state_change is ServiceStateChange.Removed:
            if name in self._peers:
                del self._peers[name]
                self._notify_updated()
            return

        info = zc.get_service_info(type_, name)
        if not info:
            return

        jid = _decode_prop(info.properties, "jid")
        if not jid:
            return
        if jid.lower() == self.local_jid.lower():
            return

        host = socket.inet_ntoa(info.addresses[0]) if info.addresses else ""
        if not host:
            return

        peer = DiscoveredPeer(
            jid=jid.lower(),
            host=host,
            port=info.port or self.listen_port,
            fingerprint=_decode_prop(info.properties, "fp"),
            service_name=name,
        )
        self._peers[name] = peer
        logger.info("mDNS discovered peer %s at %s:%d", peer.jid, peer.host, peer.port)
        self._notify_updated()

    def _notify_updated(self) -> None:
        if self._on_updated:
            self._on_updated()
