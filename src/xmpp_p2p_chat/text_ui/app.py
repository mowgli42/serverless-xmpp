"""Textual TUI for xmpp-p2p-chat."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from xmpp_p2p_chat.common.api_client import APIClient
from xmpp_p2p_chat.common.config import load_config
from xmpp_p2p_chat.text_ui.display import (
    filter_contacts,
    format_contact_summary,
    format_hash_sidebar,
    format_message_log,
    presence_symbol,
    transport_label,
)
from xmpp_p2p_chat.text_ui.screens.addressbook import (
    AddContactScreen,
    AddressBookScreen,
)

logger = logging.getLogger(__name__)


class ChatApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    #sidebar {
        width: 36;
        min-width: 28;
        border-right: solid $primary;
        background: $panel;
    }
    #sidebar-header {
        padding: 0 1;
        height: auto;
        border-bottom: solid $primary-darken-2;
        background: $boost;
    }
    #contacts-title {
        text-style: bold;
        color: $accent;
        padding: 1 0 0 0;
    }
    #contact-summary {
        color: $text-muted;
        padding: 0 0 0 0;
    }
    #addressbook-hash {
        height: auto;
        padding: 0 0 1 0;
        color: $text-muted;
    }
    #contact-filter {
        margin: 0 1 1 1;
    }
    #contact-list {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    #contact-list ListItem {
        padding: 0 1;
        height: auto;
        min-height: 3;
    }
    #contact-list ListItem.--highlight {
        background: $primary 20%;
    }
    .contact-name {
        text-style: bold;
    }
    .contact-meta {
        color: $text-muted;
    }
    #main-pane {
        width: 1fr;
    }
    #chat-header {
        padding: 1;
        border-bottom: solid $primary-darken-2;
        background: $boost;
        height: auto;
    }
    #chat-title {
        text-style: bold;
        color: $text;
    }
    #chat-subtitle {
        color: $text-muted;
    }
    #chat-scroll {
        height: 1fr;
        border: solid $primary-darken-3;
        margin: 0 1;
    }
    #chat-log {
        padding: 1;
        width: 100%;
    }
    .msg-in {
        color: $text;
    }
    .msg-out {
        color: $success;
        text-style: bold;
    }
    .msg-time {
        color: $text-muted;
    }
    #message-input {
        margin: 1;
        border: tall $primary;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary-darken-3;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "focus_contacts", "Contacts"),
        Binding("a", "open_addressbook", "Address Book"),
        Binding("n", "new_contact", "New contact"),
        Binding("slash", "focus_input", "Message"),
        Binding("r", "refresh_contacts", "Refresh"),
        Binding("question_mark", "show_help", "Help"),
    ]

    TITLE = "Serverless XMPP"

    def __init__(self, api_url: str | None = None, token: str = "") -> None:
        super().__init__()
        config = load_config()
        self.api_url = api_url or config.api_ws_url
        self.token = token or config.api_token
        self.client = APIClient(self.api_url, self.token)
        self.contacts: list[dict] = []
        self.presence: dict[str, dict] = {}
        self.health: dict = {}
        self.addressbook_status: dict = {}
        self.current_chat_id: str | None = None
        self.current_contact: dict | None = None
        self.messages: list[dict] = []
        self.contact_filter: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                with Vertical(id="sidebar-header"):
                    yield Label("Contacts", id="contacts-title")
                    yield Static("Loading…", id="contact-summary")
                    yield Static("", id="addressbook-hash")
                yield Input(placeholder="Search name or JID…", id="contact-filter")
                yield ListView(id="contact-list")
            with Vertical(id="main-pane"):
                with Vertical(id="chat-header"):
                    yield Label("Select a contact to chat", id="chat-title")
                    yield Static("", id="chat-subtitle")
                with VerticalScroll(id="chat-scroll"):
                    yield Static("[dim]Pick a contact from the sidebar, or press [bold]a[/] for address book.[/]", id="chat-log")
                yield Input(
                    placeholder="Type a message and press Enter…",
                    id="message-input",
                    disabled=True,
                )
        yield Static("Connecting to service…", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.client.on_event(self._handle_event)
        asyncio.create_task(self.client.connect())
        self.set_interval(5, self._refresh_status)

    @work(exclusive=True)
    async def _load_contacts(self) -> None:
        try:
            result = await self.client.call("addressbook.list")
            self.contacts = result.get("contacts", [])
            self.presence = result.get("presence", {})
            self.addressbook_status = result.get("status") or {}
            try:
                self.health = await self.client.call("system.health")
            except Exception:
                self.health = {}
            await self._render_contacts()
            self._update_contact_summary()
            self._update_hash_display()
        except Exception as exc:  # noqa: BLE001
            self.query_one("#status-bar", Static).update(f"[red]Error: {exc}[/]")

    def _update_contact_summary(self) -> None:
        warnings = len(self.health.get("warnings") or []) + len(
            self.addressbook_status.get("warnings") or []
        )
        online = sum(
            1 for c in self.contacts if self.presence.get(c["id"], {}).get("show") == "available"
        )
        self.query_one("#contact-summary", Static).update(
            format_contact_summary(
                version=self.addressbook_status.get("version", "?"),
                contact_count=len(self.contacts),
                online_count=online,
                warning_count=warnings,
            )
        )

    def _update_hash_display(self) -> None:
        widget = self.query_one("#addressbook-hash", Static)
        widget.update(format_hash_sidebar(self.addressbook_status.get("content_hash", "")))

    async def _render_contacts(self) -> None:
        list_view = self.query_one("#contact-list", ListView)
        await list_view.clear()
        for contact in filter_contacts(self.contacts, self.contact_filter):
            cid = contact["id"]
            name = contact.get("name", "?")
            jid = contact.get("jid", "?")
            pres = self.presence.get(cid, {})
            show = pres.get("show", "offline")
            sym = presence_symbol(show)
            sym_color = "green" if show == "available" else ("yellow" if show == "away" else "dim")
            transport = transport_label(contact)
            label = (
                f"[{sym_color}]{sym}[/] [bold]{name}[/]\n"
                f"[dim]{jid}[/]\n"
                f"[dim italic]{transport}[/]"
            )
            await list_view.append(ListItem(Label(label), id=f"contact-{cid}"))

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
        await self._select_contact(contact)

    async def _select_contact(self, contact: dict) -> None:
        self.current_chat_id = contact["id"]
        self.current_contact = contact
        self.query_one("#chat-title", Label).update(f"Chat with {contact['name']}")
        pres = self.presence.get(contact["id"], {})
        show = pres.get("show", "offline")
        self.query_one("#chat-subtitle", Static).update(
            f"{contact['jid']} · {transport_label(contact)} · {presence_symbol(show)} {show}"
        )
        self.query_one("#message-input", Input).disabled = False
        await self._open_chat(contact["id"])

    async def _open_chat(self, contact_id: str) -> None:
        await self.client.call("chat.start", {"contact_id": contact_id})
        result = await self.client.call("chat.get_history", {"chat_id": contact_id, "limit": 100})
        self.messages = result.get("messages", [])
        await self._render_messages()

    async def _render_messages(self) -> None:
        log = self.query_one("#chat-log", Static)
        peer = (self.current_contact or {}).get("name", "Peer")
        log.update(format_message_log(self.messages, peer_name=peer))
        if self.messages:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.scroll_end(animate=False)

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
            self.notify(f"Send failed: {exc}", severity="error")

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
                lambda: self.query_one("#status-bar", Static).update(
                    f"Transport: {state} · {len(self.contacts)} contacts"
                )
            )

    def _render_messages_sync(self) -> None:
        asyncio.create_task(self._render_messages())

    async def _refresh_status(self) -> None:
        try:
            result = await self.client.call("connection.status")
            transports = result.get("transports", [])
            parts = [f"{t.get('transport', '?')}:{t.get('state', '?')}" for t in transports]
            health = await self.client.call("system.health")
            self.health = health
            self._update_contact_summary()
            outbox = health.get("pending_outbox", 0)
            line = f"{' · '.join(parts)} · {len(self.contacts)} contacts"
            if outbox:
                line += f" · [yellow]outbox {outbox}[/]"
            self.query_one("#status-bar", Static).update(line)
        except Exception:
            self.query_one("#status-bar", Static).update("[red]Service unavailable — retrying…[/]")

    async def action_open_addressbook(self) -> None:
        contact_id = await self.push_screen_wait(AddressBookScreen(self.client))
        if contact_id:
            contact = next((c for c in self.contacts if c["id"] == contact_id), None)
            if contact:
                await self._select_contact(contact)
            else:
                self._load_contacts()

    async def action_new_contact(self) -> None:
        result = await self.push_screen_wait(AddContactScreen(self.client))
        if result:
            self._load_contacts()
            self.notify(f"Added contact: {result}")

    def action_show_help(self) -> None:
        self.notify(
            "a=address book · n=new contact · c=contacts · /=message · r=refresh · ?=help",
            title="Keyboard shortcuts",
            timeout=10,
        )

    def action_focus_contacts(self) -> None:
        self.query_one("#contact-list", ListView).focus()

    def action_focus_input(self) -> None:
        if not self.query_one("#message-input", Input).disabled:
            self.query_one("#message-input", Input).focus()

    def action_refresh_contacts(self) -> None:
        self._load_contacts()

    async def on_ready(self) -> None:
        await asyncio.sleep(1)
        self._load_contacts()

    async def action_quit(self) -> None:
        await self.client.disconnect()
        self.exit()
