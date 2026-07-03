"""Tests for mDNS discovery helpers."""

from __future__ import annotations

from xmpp_p2p_chat.connection_service.discovery.mdns import (
    MdnsDiscovery,
    _decode_prop,
    _jid_to_service_name,
)


def test_jid_to_service_name():
    assert _jid_to_service_name("alice@p2p.local") == "alice-p2p-local"
    assert _jid_to_service_name("bob@test.example.com") == "bob-test-example-com"


def test_decode_prop():
    props = {b"jid": b"alice@p2p.local", b"fp": b"SHA256:abc"}
    assert _decode_prop(props, "jid") == "alice@p2p.local"
    assert _decode_prop(props, "fp") == "SHA256:abc"
    assert _decode_prop(props, "missing") is None


def test_mdns_start_stop():
    discovery = MdnsDiscovery(
        local_jid="alice@p2p.local",
        listen_port=15223,
        fingerprint="SHA256:test",
    )
    discovery.start()
    assert discovery._zeroconf is not None
    discovery.stop()
    assert discovery._zeroconf is None
    assert discovery.peers == []
