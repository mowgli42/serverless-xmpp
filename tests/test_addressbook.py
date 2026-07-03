"""Tests for address book manager."""

import json
from pathlib import Path

import pytest

from xmpp_p2p_chat.common.models import Contact
from xmpp_p2p_chat.connection_service.addressbook import AddressBookError, AddressBookManager


def test_addressbook_load_add_update_remove(tmp_path: Path):
    primary = tmp_path / "addressbook.json"
    manager = AddressBookManager(primary_path=primary, fragments_dir=tmp_path / "addressbooks.d")
    manager.load()
    assert manager.contacts == []

    contact = Contact(id="bob", jid="bob@localhost", name="Bob")
    manager.add(contact)
    assert len(manager.contacts) == 1

    reloaded = AddressBookManager(primary_path=primary, fragments_dir=tmp_path / "addressbooks.d")
    reloaded.load()
    assert reloaded.get("bob").name == "Bob"

    reloaded.update("bob", {"name": "Robert"})
    assert reloaded.get("bob").name == "Robert"

    reloaded.remove("bob")
    assert reloaded.get("bob") is None


def test_addressbook_malformed_quarantine(tmp_path: Path):
    primary = tmp_path / "addressbook.json"
    primary.write_text("{not json", encoding="utf-8")
    manager = AddressBookManager(primary_path=primary)
    manager.load()
    assert not primary.exists()
    assert primary.with_suffix(".json.bad").exists()
    assert manager.warnings


def test_addressbook_duplicate_id(tmp_path: Path):
    primary = tmp_path / "addressbook.json"
    primary.write_text(
        json.dumps(
            [
                {"id": "a", "jid": "a@localhost", "name": "A"},
                {"id": "a", "jid": "b@localhost", "name": "B"},
            ]
        ),
        encoding="utf-8",
    )
    manager = AddressBookManager(primary_path=primary)
    manager.load()
    assert len(manager.contacts) == 1
    assert manager.warnings

    with pytest.raises(AddressBookError):
        manager.add(Contact(id="a", jid="c@localhost", name="C"))


def test_addressbook_warns_missing_p2p_fingerprint(tmp_path: Path):
    primary = tmp_path / "addressbook.json"
    primary.write_text(
        json.dumps(
            [
                {
                    "id": "bob",
                    "jid": "bob@p2p.local",
                    "name": "Bob",
                    "preferred_transport": "direct-p2p",
                    "direct": {"host": "127.0.0.1", "port": 5224, "public_key_fingerprint": ""},
                }
            ]
        ),
        encoding="utf-8",
    )
    manager = AddressBookManager(primary_path=primary)
    manager.load()
    assert any("missing" in w.lower() and "fingerprint" in w.lower() for w in manager.warnings)
