"""Tests for config and models."""

from pathlib import Path

import pytest

from xmpp_p2p_chat.common.config import load_config
from xmpp_p2p_chat.common.models import Contact


def test_contact_validates_jid():
    contact = Contact(id="alice", jid="alice@example.com", name="Alice")
    assert contact.jid == "alice@example.com"


def test_contact_rejects_bad_jid():
    with pytest.raises(ValueError):
        Contact(id="bad", jid="not-a-jid", name="Bad")


def test_load_config_defaults(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        f"""
[data]
directory = "{data_dir}"

[xmpp]
jid = "test@localhost"
password = "secret"
server = "localhost"
""",
        encoding="utf-8",
    )
    cfg = load_config(config_file)
    assert cfg.data_directory == data_dir.resolve()
    assert cfg.xmpp.jid == "test@localhost"
    assert cfg.api_host == "127.0.0.1"
