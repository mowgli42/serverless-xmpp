"""Textual TUI for xmpp-p2p-chat."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from xmpp_p2p_chat.common.api_client import APIClient
from xmpp_p2p_chat.common.config import load_config

logger = logging.getLogger(__name__)


class ContactSelected(Message):
    def __init__(self, contact_id: str, name: str) -> None:
        super().__init__()
        self.contact_id = contact_id
        self.name = name


class ChatApp(App):
    CSS = """
    #sidebar {
        width: 30;
        border-right: solid $primary;
    }
    #chat-log {
        height: 1fr;
        padding: 1;
    }
    .msg-in {
        color: $text;
    }
    .msg-out {
        color: $success;
        text-style: bold;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "focus_contacts", "Contacts"),
        Binding("slash", "focus_input", "Message"),
        Binding("r", "refresh_contacts", "Refresh"),
        Binding("question_mark", "show_help", "Help"),
    ]

    def __init__(self, api_url: str | None = None, token: str = "") -> None:
        super().__init__()
        config = load_config()
        self.api_url = api_url or config.api_ws_url
        self.token = token or config.api_token
        self.client = APIClient(self.api_url, self.token)
        self.contacts: list[dict] = []
        self.presence: dict[str, dict] = {}
        self.current_chat_id: str | None = None
        self.current_contact_name: str = ""
        self.messages: list[dict] = []
        self.contact_filter: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("Contacts", id="contacts-title")
                yield Input(placeholder="Filter contacts...", id="contact-filter")
                yield ListView(id="contact-list")
            with Vertical():
                yield Label("Select a contact", id="chat-title")
                yield VerticalScroll(Static("", id="chat-log"))
                yield Input(placeholder="Type a message and press Enter...", id="message-input")
        yield Static("Connecting to service...", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.client.on_event(self._handle_event)
        asyncio.create_task(self.client.connect())
        self.set_interval(3, self._refresh_status)

    @work(exclusive=True)
    async def _load_contacts(self) -> None:
        try:
            result = await self.client.call("addressbook.list")
            self.contacts = result.get("contacts", [])
            self.presence = result.get("presence", {})
            await self._render_contacts()
            self.query_one("#status-bar", Static).update(f"Connected · {len(self.contacts)} contacts")
        except Exception as exc:  # noqa: BLE001
            self.query_one("#status-bar", Static).update(f"Error: {exc}")

    async def _render_contacts(self) -> None:
        list_view = self.query_one("#contact-list", ListView)
        await list_view.clear()
        needle = self.contact_filter.lower()
        for contact in self.contacts:
            if needle and needle not in contact["name"].lower() and needle not in contact["jid"].lower():
                continue
            pres = self.presence.get(contact["id"], {})
            show = pres.get("show", "offline")
            label = f"[{'green' if show == 'available' else 'dim'}]●[/] {contact['name']}"
            await list_view.append(ListItem(Label(label), id=f"contact-{contact['id']}"))

    @on(Input.Changed, "#contact-filter")
    async def on_contact_filter_changed(self, event: Input.Changed) -> None:
        self.contact_filter = event.value
        await self._render_contacts()

    @on(ListView.Selected)
    async def on_contact_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if not item_id.startswith("contact-"):
            return
        contact_id = item_id.removeprefix("contact-")
        contact = next((c for c in self.contacts if c["id"] == contact_id), None)
        if not contact:
            return
        self.current_chat_id = contact_id
        self.current_contact_name = contact["name"]
        self.query_one("#chat-title", Label).update(f"Chat with {contact['name']}")
        await self._open_chat(contact_id)

    async def _open_chat(self, contact_id: str) -> None:
        await self.client.call("chat.start", {"contact_id": contact_id})
        result = await self.client.call("chat.get_history", {"chat_id": contact_id, "limit": 100})
        self.messages = result.get("messages", [])
        await self._render_messages()

    async def _render_messages(self) -> None:
        log = self.query_one("#chat-log", Static)
        lines = []
        for msg in self.messages:
            ts = msg.get("timestamp", "")
            if isinstance(ts, str) and "T" in ts:
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
                except ValueError:
                    pass
            direction = msg.get("direction", "in")
            prefix = "You" if direction == "out" else self.current_contact_name
            style = "msg-out" if direction == "out" else "msg-in"
            status = msg.get("status", "")
            marker = " ✓" if status == "delivered" else (" …" if status == "pending" else "")
            lines.append(f"[{style}]{ts} {prefix}: {msg['body']}{marker}[/]")
        log.update("\n".join(lines) if lines else "[dim]No messages yet. Say hello![/]")

    @on(Input.Submitted, "#message-input")
    async def on_message_submit(self, event: Input.Submitted) -> None:
        body = event.value.strip()
        if not body or not self.current_chat_id:
            return
        event.input.value = ""
        optimistic = {
            "direction": "out",
            "body": body,
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
        }
        self.messages.append(optimistic)
        await self._render_messages()
        try:
            result = await self.client.call(
                "chat.send_message", {"chat_id": self.current_chat_id, "body": body}
            )
            sent = result.get("message", optimistic)
            self.messages[-1] = sent
            await self._render_messages()
        except Exception as exc:  # noqa: BLE001
            self.query_one("#status-bar", Static).update(f"Send failed: {exc}")

    def _handle_event(self, event: str, params: dict) -> None:
        if event == "message.received" and params.get("chat_id") == self.current_chat_id:
            self.messages.append(params.get("message", {}))
            self.call_from_thread(self._render_messages_sync)
        elif event == "message.updated" and params.get("chat_id") == self.current_chat_id:
            updated = params.get("message", {})
            for i, msg in enumerate(self.messages):
                if msg.get("id") == updated.get("id"):
                    self.messages[i] = updated
                    break
            self.call_from_thread(self._render_messages_sync)
        elif event in ("presence.updated", "addressbook.updated"):
            self.call_from_thread(self._load_contacts)
        elif event == "connection.changed":
            state = params.get("state", "unknown")
            self.call_from_thread(
                lambda: self.query_one("#status-bar", Static).update(f"XMPP: {state}")
            )

    def _render_messages_sync(self) -> None:
        asyncio.create_task(self._render_messages())

    async def _refresh_status(self) -> None:
        try:
            result = await self.client.call("connection.status")
            transports = result.get("transports", [])
            if transports:
                parts = [f"{t.get('transport', '?')}:{t.get('state', '?')}" for t in transports]
                self.query_one("#status-bar", Static).update(
                    f"{' · '.join(parts)} · {len(self.contacts)} contacts"
                )
        except Exception:
            self.query_one("#status-bar", Static).update("Service unavailable — retrying...")

    def action_show_help(self) -> None:
        self.notify(
            "q=quit · c=contacts · /=message · r=refresh · ?=help · Enter=send",
            title="Keyboard shortcuts",
            timeout=8,
        )

    def action_focus_contacts(self) -> None:
        self.query_one("#contact-list", ListView).focus()

    def action_focus_input(self) -> None:
        self.query_one("#message-input", Input).focus()

    def action_refresh_contacts(self) -> None:
        self._load_contacts()

    async def on_ready(self) -> None:
        await asyncio.sleep(1)
        self._load_contacts()

    async def action_quit(self) -> None:
        await self.client.disconnect()
        self.exit()
