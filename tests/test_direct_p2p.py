"""Tests for direct P2P transport."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from xmpp_p2p_chat.common.certs import ensure_p2p_certificates, verify_fingerprint
from xmpp_p2p_chat.connection_service.transports.direct_p2p import DirectP2PTransport, PeerEndpoint
from xmpp_p2p_chat.connection_service.transports.xmpp_stream import (
    message_stanza,
    parse_message,
    stream_open,
)


def test_cert_generation_and_fingerprint(tmp_path: Path):
    cert_path, key_path, fp = ensure_p2p_certificates(tmp_path, "alice")
    assert cert_path.exists()
    assert key_path.exists()
    assert fp.startswith("SHA256:")
    assert verify_fingerprint(cert_path.read_bytes(), fp)


def test_xmpp_stream_helpers():
    xml = message_stanza("alice@p2p.local", "bob@p2p.local", "hello", "mid-1")
    parsed = parse_message(xml)
    assert parsed == ("alice@p2p.local", "hello", "mid-1")
    assert "bob@p2p.local" in stream_open("alice@p2p.local", "bob@p2p.local")


@pytest.mark.asyncio
async def test_direct_p2p_message_exchange(tmp_path: Path):
    alice_dir = tmp_path / "alice"
    bob_dir = tmp_path / "bob"
    _, _, bob_fp = ensure_p2p_certificates(bob_dir, "bob")
    _, _, alice_fp = ensure_p2p_certificates(alice_dir, "alice")

    received: list[tuple[str, str]] = []

    async def on_alice_message(from_jid: str, body: str, _stanza_id: str | None) -> None:
        received.append((from_jid, body))

    async def on_bob_message(from_jid: str, body: str, _stanza_id: str | None) -> None:
        received.append((from_jid, body))

    alice = DirectP2PTransport(
        local_jid="alice@p2p.local",
        cert_dir=alice_dir,
        listen_host="127.0.0.1",
        listen_port=15223,
    )
    bob = DirectP2PTransport(
        local_jid="bob@p2p.local",
        cert_dir=bob_dir,
        listen_host="127.0.0.1",
        listen_port=15224,
    )
    alice.on_message(on_alice_message)
    bob.on_message(on_bob_message)

    await alice.connect()
    await bob.connect()

    bob.register_peer(
        PeerEndpoint("alice@p2p.local", "127.0.0.1", 15223, fingerprint=alice_fp)
    )
    alice.register_peer(
        PeerEndpoint("bob@p2p.local", "127.0.0.1", 15224, fingerprint=bob_fp)
    )

    await alice.connect_peer(PeerEndpoint("bob@p2p.local", "127.0.0.1", 15224, bob_fp))
    await alice.send_message("bob@p2p.local", "Hello Bob, P2P works!")
    await asyncio.sleep(0.3)

    assert any(body == "Hello Bob, P2P works!" for _from, body in received)

    await bob.connect_peer(PeerEndpoint("alice@p2p.local", "127.0.0.1", 15223, alice_fp))
    await bob.send_message("alice@p2p.local", "Hi Alice!")
    await asyncio.sleep(0.3)

    assert any(body == "Hi Alice!" for _from, body in received)

    await alice.disconnect()
    await bob.disconnect()
