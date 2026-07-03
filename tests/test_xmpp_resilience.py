"""Tests for XMPP error parsing and SM state persistence."""

from __future__ import annotations

from pathlib import Path

from slixmpp.exceptions import IqTimeout

from xmpp_p2p_chat.connection_service.xmpp.errors import parse_xmpp_error
from xmpp_p2p_chat.connection_service.xmpp.sm_state import (
    StreamManagementState,
    clear_sm_state,
    load_sm_state,
    save_sm_state,
)


class TestParseXmppError:
    def test_iq_timeout_maps_to_remote_server_timeout(self):
        info = parse_xmpp_error(IqTimeout("ping timed out"))
        assert info.condition == "remote-server-timeout"
        assert info.error_type == "cancel"

    def test_generic_exception(self):
        info = parse_xmpp_error(RuntimeError("not-authorized during bind"))
        assert info.condition == "not-authorized"


class TestStreamManagementState:
    def test_round_trip(self, tmp_path: Path):
        state = StreamManagementState(
            jid="alice@example.com",
            sm_id="sm-abc",
            handled=10,
            last_ack=8,
        )
        save_sm_state(tmp_path, state)
        loaded = load_sm_state(tmp_path, "alice@example.com")
        assert loaded is not None
        assert loaded.sm_id == "sm-abc"
        assert loaded.handled == 10

    def test_jid_mismatch_ignored(self, tmp_path: Path):
        save_sm_state(
            tmp_path,
            StreamManagementState(jid="bob@example.com", sm_id="x", handled=0, last_ack=0),
        )
        assert load_sm_state(tmp_path, "alice@example.com") is None

    def test_clear_removes_file(self, tmp_path: Path):
        save_sm_state(
            tmp_path,
            StreamManagementState(jid="alice@example.com", sm_id="x", handled=0, last_ack=0),
        )
        clear_sm_state(tmp_path)
        assert load_sm_state(tmp_path, "alice@example.com") is None
