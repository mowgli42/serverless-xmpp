"""Tests for address book hashing and status."""

from __future__ import annotations

import json
from pathlib import Path

from xmpp_p2p_chat.common.addressbook_hash import (
    compute_content_hash,
    hash_block_colors,
    render_hash_grid_rich,
)
from xmpp_p2p_chat.common.models import Contact
from xmpp_p2p_chat.connection_service.addressbook import AddressBookManager


def test_compute_content_hash_stable():
    contacts = [{"id": "a", "jid": "a@p2p.local", "name": "A", "preferred_transport": "direct-p2p"}]
    h1 = compute_content_hash(contacts)
    h2 = compute_content_hash(contacts)
    assert h1 == h2
    assert h1.startswith("SHA256:")


def test_hash_blocks_length():
    h = compute_content_hash([{"id": "x", "jid": "x@p2p.local", "name": "X"}])
    blocks = hash_block_colors(h)
    assert len(blocks) == 64
    assert render_hash_grid_rich(h, grid=8).count("█") == 64


def test_addressbook_version_and_hash_on_mutations(tmp_path: Path):
    primary = tmp_path / "addressbook.json"
    manager = AddressBookManager(primary_path=primary)
    manager.process_startup(import_if_empty=False)
    assert manager.version == 0
    assert manager.content_hash.startswith("SHA256:")

    manager.add(Contact(id="alice", jid="alice@p2p.local", name="Alice"))
    assert manager.version == 1
    status = manager.status()
    assert status.contact_count == 1
    assert len(status.hash_blocks) == 64

    manager.add(Contact(id="bob", jid="bob@p2p.local", name="Bob"))
    assert manager.version == 2
    assert manager.content_hash != status.content_hash


def test_bundled_import_on_empty(tmp_path: Path):
    primary = tmp_path / "addressbook.json"
    bundled = tmp_path / "bundled.json"
    bundled.write_text(
        json.dumps([{"id": "seed", "jid": "seed@p2p.local", "name": "Seed"}]),
        encoding="utf-8",
    )
    manager = AddressBookManager(primary_path=primary)
    manager.process_startup(bundled_path=bundled, import_if_empty=True)
    assert manager.get("seed") is not None
    assert manager.status().bundled_source == str(bundled)


def test_reload_detects_external_change(tmp_path: Path):
    primary = tmp_path / "addressbook.json"
    manager = AddressBookManager(primary_path=primary)
    manager.process_startup(import_if_empty=False)
    manager.add(Contact(id="a", jid="a@p2p.local", name="A"))
    v1 = manager.version

    primary.write_text(
        json.dumps([{"id": "b", "jid": "b@p2p.local", "name": "B", "preferred_transport": "xmpp-server"}]),
        encoding="utf-8",
    )
    manager.reload()
    assert manager.get("b") is not None
    assert manager.get("a") is None
    assert manager.version >= v1
