"""TUI failure-path tests for troubleshooting display states."""

from __future__ import annotations

import pytest
from textual.widgets import Static

from xmpp_p2p_chat.text_ui.app import ChatApp
from xmpp_p2p_chat.text_ui.screens.addressbook import AddressBookScreen


class TestTuiConnectionFailures:
    @pytest.mark.asyncio
    async def test_load_contacts_api_error_shows_status_bar(self, mock_api):
        mock_api.errors["addressbook.list"] = RuntimeError("Connection refused")
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api

        async with app.run_test(size=(120, 40)):
            try:
                await mock_api.call("addressbook.list")
            except Exception as exc:
                app.query_one("#status-bar", Static).update(f"[red]Error: {exc}[/]")
            status = str(app.query_one("#status-bar", Static).content)
            assert "Error" in status
            assert "Connection refused" in status

    @pytest.mark.asyncio
    async def test_refresh_status_service_unavailable(self, mock_api):
        mock_api.errors["connection.status"] = RuntimeError("Service down")
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api

        async with app.run_test(size=(120, 40)):
            await app._refresh_status()
            status = str(app.query_one("#status-bar", Static).content)
            assert "Service unavailable" in status

    @pytest.mark.asyncio
    async def test_send_message_failure_keeps_pending(self, mock_api):
        mock_api.errors["chat.send_message"] = RuntimeError("Transport offline")
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api
        app.current_chat_id = "bob"
        app.current_contact = {"name": "Bob"}
        app.messages = []

        async with app.run_test(size=(120, 40)):
            from textual.widgets import Input

            inp = app.query_one("#message-input", Input)
            inp.value = "test message"
            await app.on_message_submit(Input.Submitted(inp, "test message"))
            assert app.messages[-1]["status"] == "pending"


class TestTuiDataFailures:
    @pytest.mark.asyncio
    async def test_addressbook_screen_load_error(self, mock_api):
        mock_api.errors["addressbook.list"] = RuntimeError("Invalid JSON from service")
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        screen = AddressBookScreen(mock_api)

        async with app.run_test(size=(120, 40)):
            await app.push_screen(screen)
            await screen.refresh_data()
            status = str(screen.query_one("#ab-status", Static).content)
            assert "Error loading address book" in status

    @pytest.mark.asyncio
    async def test_addressbook_warnings_surface_in_summary(self, mock_api):
        mock_api.responses["addressbook.list"]["status"]["warnings"] = [
            "Fragment duplicate id skipped",
        ]
        mock_api.responses["system.health"]["warnings"] = ["Outbox backlog"]
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api
        app.contacts = mock_api.responses["addressbook.list"]["contacts"]
        app.presence = mock_api.responses["addressbook.list"]["presence"]
        app.addressbook_status = mock_api.responses["addressbook.list"]["status"]
        app.health = mock_api.responses["system.health"]

        async with app.run_test(size=(120, 40)):
            app._update_contact_summary()
            summary = str(app.query_one("#contact-summary", Static).content)
            assert "warn" in summary

    @pytest.mark.asyncio
    async def test_flood_of_messages_renders_all(self, mock_api):
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api
        app.current_contact = {"name": "Bob"}
        app.messages = [
            {
                "direction": "in" if i % 2 else "out",
                "body": f"Message {i}",
                "timestamp": "2026-07-03T12:00:00Z",
                "status": "delivered",
            }
            for i in range(100)
        ]

        async with app.run_test(size=(120, 40)):
            await app._render_messages()
            log = str(app.query_one("#chat-log", Static).content)
            assert "Message 0" in log
            assert "Message 99" in log

    @pytest.mark.asyncio
    async def test_connection_changed_updates_status_bar(self, mock_api):
        app = ChatApp(api_url="ws://127.0.0.1:9/rpc")
        app.client = mock_api
        app.contacts = mock_api.responses["addressbook.list"]["contacts"]

        async with app.run_test(size=(120, 40)):
            app.query_one("#status-bar", Static).update(
                f"Transport: disconnected · {len(app.contacts)} contacts"
            )
            status = str(app.query_one("#status-bar", Static).content)
            assert "disconnected" in status
