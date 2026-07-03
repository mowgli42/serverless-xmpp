"""Unit tests for TUI display helpers and Textual widget rendering."""

from __future__ import annotations

import pytest

from xmpp_p2p_chat.text_ui.app import ChatApp
from xmpp_p2p_chat.text_ui.display import (
    filter_contacts,
    format_addressbook_status_panel,
    format_contact_detail,
    format_contact_summary,
    format_hash_sidebar,
    format_message_log,
    format_message_timestamp,
    presence_symbol,
    transport_label,
)

SAMPLE_CONTACTS = [
    {"id": "bob", "jid": "bob@p2p.local", "name": "Bob", "preferred_transport": "direct-p2p",
     "direct": {"host": "10.0.0.1", "port": 5224}},
    {"id": "carol", "jid": "carol@p2p.local", "name": "Carol", "preferred_transport": "xmpp-server"},
]


class TestDisplayHelpers:
    def test_presence_symbols(self):
        assert presence_symbol("available") == "●"
        assert presence_symbol("offline") == "○"
        assert presence_symbol("unknown") == "○"

    def test_transport_label_p2p(self):
        label = transport_label(SAMPLE_CONTACTS[0])
        assert "P2P" in label
        assert "10.0.0.1" in label

    def test_transport_label_xmpp(self):
        assert "XMPP" in transport_label(SAMPLE_CONTACTS[1])

    def test_format_contact_detail_includes_jid(self):
        detail = format_contact_detail(SAMPLE_CONTACTS[0], {"bob": {"show": "available"}})
        assert "bob@p2p.local" in detail
        assert "Bob" in detail

    def test_contact_summary_with_warnings(self):
        text = format_contact_summary(version=3, contact_count=5, online_count=2, warning_count=1)
        assert "v3" in text
        assert "5 contacts" in text
        assert "warn" in text

    def test_hash_sidebar_empty(self):
        assert format_hash_sidebar("") == ""

    def test_hash_sidebar_renders_grid(self):
        h = "SHA256:" + "ab" * 32
        text = format_hash_sidebar(h)
        assert "Book hash" in text
        assert "█" in text

    def test_message_timestamp_iso(self):
        assert format_message_timestamp("2026-07-03T14:30:00+00:00") == "14:30"

    def test_message_log_pending_marker(self):
        log = format_message_log(
            [{"direction": "out", "body": "hi", "timestamp": "2026-07-03T12:00:00Z", "status": "pending"}],
            peer_name="Bob",
        )
        assert "hi" in log
        assert "…" in log

    def test_message_log_delivered_marker(self):
        log = format_message_log(
            [{"direction": "in", "body": "ok", "timestamp": "2026-07-03T12:00:00Z", "status": "delivered"}],
            peer_name="Bob",
        )
        assert "✓" in log

    def test_filter_contacts_by_jid(self):
        result = filter_contacts(SAMPLE_CONTACTS, "carol@")
        assert len(result) == 1
        assert result[0]["id"] == "carol"

    def test_addressbook_status_panel_ok(self):
        panel = format_addressbook_status_panel(
            health={"ok": True, "pending_outbox": 0, "uptime_seconds": 10, "warnings": []},
            ab_status={"version": 1, "content_hash": "SHA256:x", "primary_path": "/data/ab.json"},
            connection={"transports": [{"transport": "direct-p2p", "state": "connected"}]},
            contact_count=2,
        )
        assert "✓ OK" in panel
        assert "v1" in panel
        assert "direct-p2p:connected" in panel


class TestChatAppDisplay:
    """Textual Pilot tests for main chat display workflow."""

    @pytest.mark.asyncio
    async def test_sidebar_shows_version_and_hash(self, mock_api):
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api
        app.contacts = mock_api.responses["addressbook.list"]["contacts"]
        app.presence = mock_api.responses["addressbook.list"]["presence"]
        app.addressbook_status = {
            **mock_api.responses["addressbook.list"]["status"],
            "content_hash": "SHA256:" + "c" * 64,
        }
        app.health = mock_api.responses["system.health"]

        async with app.run_test(size=(120, 40)):
            app._update_contact_summary()
            app._update_hash_display()
            summary = str(app.query_one("#contact-summary").content)
            assert "v2" in summary
            hash_panel = str(app.query_one("#addressbook-hash").content)
            assert "█" in hash_panel

    @pytest.mark.asyncio
    async def test_contact_filter_narrows_list(self, mock_api):
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api
        app.contacts = mock_api.responses["addressbook.list"]["contacts"]
        app.presence = mock_api.responses["addressbook.list"]["presence"]

        async with app.run_test(size=(120, 40)):
            await app._render_contacts()
            assert len(app.query("#contact-list ListItem")) == 2
            app.contact_filter = "carol"
            await app._render_contacts()
            assert len(app.query("#contact-list ListItem")) == 1

    @pytest.mark.asyncio
    async def test_message_render_shows_chat_history(self, mock_api):
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api
        app.current_contact = {"name": "Bob"}
        app.messages = [
            {"direction": "in", "body": "Hello", "timestamp": "2026-07-03T10:00:00Z", "status": "delivered"},
            {"direction": "out", "body": "Hi", "timestamp": "2026-07-03T10:01:00Z", "status": "sent"},
        ]

        async with app.run_test(size=(120, 40)):
            await app._render_messages()
            log = str(app.query_one("#chat-log").content)
            assert "Hello" in log
            assert "Hi" in log


class TestAddressBookScreenDisplay:
    @pytest.mark.asyncio
    async def test_addressbook_screen_status_panel(self, mock_api):
        from xmpp_p2p_chat.text_ui.screens.addressbook import AddressBookScreen

        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        screen = AddressBookScreen(mock_api)

        async with app.run_test(size=(120, 40)):
            await app.push_screen(screen)
            await screen.refresh_data()
            status = str(screen.query_one("#ab-status").content)
            assert "v2" in status
            assert "contacts" in status
            hash_text = str(screen.query_one("#ab-hash").content)
            assert "█" in hash_text
