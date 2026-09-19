"""Address book screens for the Textual TUI."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Input, Label, Static

from xmpp_p2p_chat.common.addressbook_hash import render_hash_grid_rich
from xmpp_p2p_chat.common.api_client import APIClient
from xmpp_p2p_chat.text_ui.display import (
    format_addressbook_status_panel,
    format_contact_detail,
    format_sync_status_panel,
    presence_symbol,
    transport_label,
)


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no confirmation dialog."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 60;
        height: auto;
        border: solid $error;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self.message)
            with Horizontal():
                yield Button("Yes", id="yes", variant="error")
                yield Button("No", id="no")

    @on(Button.Pressed, "#yes")
    def on_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def on_no(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class AddContactScreen(ModalScreen[str | None]):
    """Form to create a new address book contact."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    AddContactScreen {
        align: center middle;
    }
    #add-dialog {
        width: 70;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #add-dialog .field-label {
        margin-top: 1;
        color: $text-muted;
    }
    #add-actions {
        margin-top: 1;
        height: auto;
    }
    """

    def __init__(self, client: APIClient) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        with Vertical(id="add-dialog"):
            yield Label("[bold]New contact[/bold]")
            yield Label("ID (unique slug)", classes="field-label")
            yield Input(placeholder="bob", id="field-id")
            yield Label("Display name", classes="field-label")
            yield Input(placeholder="Bob", id="field-name")
            yield Label("JID", classes="field-label")
            yield Input(placeholder="bob@p2p.local", id="field-jid")
            yield Label("Transport (direct-p2p or xmpp-server)", classes="field-label")
            yield Input(placeholder="direct-p2p", id="field-transport")
            yield Label("P2P host (if direct)", classes="field-label")
            yield Input(placeholder="192.168.1.50", id="field-host")
            yield Label("P2P port", classes="field-label")
            yield Input(placeholder="5223", id="field-port")
            yield Label("Cert fingerprint (optional)", classes="field-label")
            yield Input(placeholder="SHA256:...", id="field-fp")
            with Horizontal(id="add-actions"):
                yield Button("Create", id="create", variant="primary")
                yield Button("Cancel", id="cancel")

    @on(Button.Pressed, "#create")
    async def on_create(self) -> None:
        cid = self.query_one("#field-id", Input).value.strip()
        name = self.query_one("#field-name", Input).value.strip()
        jid = self.query_one("#field-jid", Input).value.strip().lower()
        transport = self.query_one("#field-transport", Input).value.strip() or "direct-p2p"
        host = self.query_one("#field-host", Input).value.strip()
        port_str = self.query_one("#field-port", Input).value.strip() or "5223"
        fp = self.query_one("#field-fp", Input).value.strip()

        if not cid or not name or not jid:
            self.notify("ID, name, and JID are required", severity="error")
            return

        contact: dict = {
            "id": cid,
            "name": name,
            "jid": jid,
            "preferred_transport": transport,
        }
        if transport == "direct-p2p" and host:
            try:
                port = int(port_str)
            except ValueError:
                self.notify("Port must be a number", severity="error")
                return
            direct: dict = {"host": host, "port": port}
            if fp:
                direct["public_key_fingerprint"] = fp
            contact["direct"] = direct

        try:
            result = await self.client.call("addressbook.add", {"contact": contact})
            self.dismiss(result.get("id", cid))
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Failed: {exc}", severity="error")

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AddressBookScreen(ModalScreen[str | None]):
    """View address book status, browse contacts, add or remove entries."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
        Binding("n", "new_contact", "New"),
        Binding("delete", "remove_contact", "Remove"),
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "open_chat", "Chat"),
    ]

    CSS = """
    AddressBookScreen {
        align: center middle;
    }
    #ab-dialog {
        width: 92%;
        height: 92%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #ab-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    #ab-status {
        height: auto;
        max-height: 9;
        padding: 1;
        margin-bottom: 1;
        border: solid $primary-darken-2;
        background: $panel;
    }
    #ab-sync {
        height: auto;
        max-height: 10;
        padding: 1;
        margin-bottom: 1;
        border: solid $primary-darken-3;
        background: $boost;
    }
    #ab-hash {
        height: auto;
        padding: 0 1 1 1;
        margin-bottom: 1;
    }
    #ab-table {
        height: 1fr;
        min-height: 10;
    }
    #ab-detail {
        height: auto;
        max-height: 8;
        padding: 1;
        margin-top: 1;
        border: solid $primary-darken-3;
        background: $boost;
    }
    #ab-actions {
        height: auto;
        margin-top: 1;
    }
    #ab-sync-actions {
        height: auto;
        margin-top: 1;
    }
    #ab-sync-actions Button {
        margin-right: 1;
    }
    #ab-actions Button {
        margin-right: 1;
    }
    """

    def __init__(self, client: APIClient) -> None:
        super().__init__()
        self.client = client
        self.contacts: list[dict] = []
        self.presence: dict[str, dict] = {}
        self.health: dict = {}
        self.connection: dict = {}
        self.ab_status: dict = {}
        self.sync_status: dict = {}
        self.pending_updates: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="ab-dialog"):
            yield Label("Address Book — Status & Contacts", id="ab-title")
            yield Static("Loading…", id="ab-status")
            yield Static("", id="ab-sync")
            yield Static("", id="ab-hash")
            yield DataTable(id="ab-table", cursor_type="row", zebra_stripes=True)
            yield Static("[dim]Select a contact · Enter opens chat · n=new · delete=remove[/dim]", id="ab-detail")
            with Horizontal(id="ab-sync-actions"):
                yield Button("Sync now", id="btn-sync-now")
                yield Button("Enable sync", id="btn-sync-enable")
                yield Button("Disable sync", id="btn-sync-disable")
                yield Button("Auto-apply", id="btn-sync-auto")
                yield Button("Apply pending", id="btn-sync-apply")
                yield Button("Reject pending", id="btn-sync-reject")
            with Horizontal(id="ab-actions"):
                yield Button("New contact", id="btn-new", variant="primary")
                yield Button("Remove", id="btn-remove", variant="error")
                yield Button("Refresh", id="btn-refresh")
                yield Button("Close", id="btn-close")
            yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#ab-table", DataTable)
        table.add_columns(" ", "Name", "JID", "Transport", "Presence")
        await self.refresh_data()

    async def refresh_data(self) -> None:
        try:
            listed = await self.client.call("addressbook.list")
            self.contacts = listed.get("contacts", [])
            self.presence = listed.get("presence", {})
            self.ab_status = listed.get("status") or await self.client.call("addressbook.status")
            self.health = await self.client.call("system.health")
            self.connection = await self.client.call("connection.status")
            self.sync_status = await self.client.call("addressbook.sync_status")
            pending = await self.client.call("addressbook.get_pending_updates")
            self.pending_updates = pending.get("updates", [])
        except Exception as exc:  # noqa: BLE001
            self.query_one("#ab-status", Static).update(f"[red]Error loading address book: {exc}[/]")
            return

        self._render_status()
        self._render_sync()
        self._render_table()
        self._render_detail(None)

    def _render_sync(self) -> None:
        self.query_one("#ab-sync", Static).update(
            format_sync_status_panel(
                sync_status=self.sync_status,
                pending_updates=self.pending_updates,
            )
        )
        secret_ok = self.sync_status.get("secret_configured", False)
        enabled = self.sync_status.get("enabled", False)
        auto_apply = self.sync_status.get("auto_apply", False)
        has_pending = bool(self.pending_updates)

        self.query_one("#btn-sync-now", Button).disabled = not (secret_ok and enabled)
        self.query_one("#btn-sync-enable", Button).disabled = not secret_ok or enabled
        self.query_one("#btn-sync-disable", Button).disabled = not enabled
        self.query_one("#btn-sync-auto", Button).disabled = not enabled
        self.query_one("#btn-sync-auto", Button).label = (
            "Auto-apply: on" if auto_apply else "Auto-apply: off"
        )
        self.query_one("#btn-sync-apply", Button).disabled = not has_pending
        self.query_one("#btn-sync-reject", Button).disabled = not has_pending

    def _render_status(self) -> None:
        self.query_one("#ab-status", Static).update(
            format_addressbook_status_panel(
                health=self.health,
                ab_status=self.ab_status,
                connection=self.connection,
                contact_count=len(self.contacts),
            )
        )

        hash_widget = self.query_one("#ab-hash", Static)
        content_hash = self.ab_status.get("content_hash", "")
        if content_hash:
            short = content_hash.replace("SHA256:", "")[:16]
            hash_widget.update(
                f"[bold]Content fingerprint[/] [dim]({short}…)[/]\n"
                + render_hash_grid_rich(content_hash, grid=8)
            )
        else:
            hash_widget.update("")

    def _render_table(self) -> None:
        table = self.query_one("#ab-table", DataTable)
        table.clear(columns=False)
        for contact in self.contacts:
            cid = contact["id"]
            pres = self.presence.get(cid, {})
            show = pres.get("show", "offline")
            table.add_row(
                presence_symbol(show),
                contact.get("name", "?"),
                contact.get("jid", "?"),
                transport_label(contact),
                show,
                key=cid,
            )

    def _render_detail(self, contact_id: str | None) -> None:
        detail = self.query_one("#ab-detail", Static)
        if not contact_id:
            detail.update("[dim]Select a contact · Enter opens chat · n=new · delete=remove[/dim]")
            return
        contact = next((c for c in self.contacts if c["id"] == contact_id), None)
        if not contact:
            detail.update("[dim]Contact not found[/dim]")
            return
        detail.update(format_contact_detail(contact, self.presence))

    def _selected_contact_id(self) -> str | None:
        table = self.query_one("#ab-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            return str(row_key.value)
        except Exception:
            if table.cursor_row < len(self.contacts):
                return self.contacts[table.cursor_row]["id"]
            return None

    @on(DataTable.RowHighlighted)
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None:
            self._render_detail(str(event.row_key.value))

    async def action_refresh(self) -> None:
        try:
            await self.client.call("addressbook.reload")
        except Exception:
            pass
        await self.refresh_data()
        self.notify("Address book reloaded from disk")

    async def action_new_contact(self) -> None:
        result = await self.app.push_screen_wait(AddContactScreen(self.client))
        if result:
            await self.refresh_data()
            self.notify(f"Added contact: {result}")

    async def action_remove_contact(self) -> None:
        contact_id = self._selected_contact_id()
        if not contact_id:
            self.notify("Select a contact to remove", severity="warning")
            return
        contact = next((c for c in self.contacts if c["id"] == contact_id), None)
        name = contact.get("name", contact_id) if contact else contact_id
        if not await self.app.push_screen_wait(
            ConfirmScreen(f"Remove contact [bold]{name}[/] ({contact_id})?")
        ):
            return
        try:
            await self.client.call("addressbook.remove", {"id": contact_id})
            await self.refresh_data()
            self.notify(f"Removed {name}")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Remove failed: {exc}", severity="error")

    async def action_open_chat(self) -> None:
        contact_id = self._selected_contact_id()
        if contact_id:
            self.dismiss(contact_id)

    async def action_dismiss(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-new")
    async def on_new_pressed(self) -> None:
        await self.action_new_contact()

    @on(Button.Pressed, "#btn-remove")
    async def on_remove_pressed(self) -> None:
        await self.action_remove_contact()

    @on(Button.Pressed, "#btn-refresh")
    async def on_refresh_pressed(self) -> None:
        await self.action_refresh()

    @on(Button.Pressed, "#btn-close")
    async def on_close_pressed(self) -> None:
        await self.action_dismiss()

    @on(Button.Pressed, "#btn-sync-now")
    async def on_sync_now_pressed(self) -> None:
        try:
            await self.client.call("addressbook.sync_now")
            self.notify("Address book sync pushed to XMPP contacts")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Sync failed: {exc}", severity="error")
            return
        await self.refresh_data()

    @on(Button.Pressed, "#btn-sync-enable")
    async def on_sync_enable_pressed(self) -> None:
        try:
            self.sync_status = await self.client.call(
                "addressbook.enable_sync", {"enabled": True}
            )
            self.notify("Address book sync enabled")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Enable failed: {exc}", severity="error")
            return
        await self.refresh_data()

    @on(Button.Pressed, "#btn-sync-disable")
    async def on_sync_disable_pressed(self) -> None:
        try:
            self.sync_status = await self.client.call(
                "addressbook.enable_sync", {"enabled": False}
            )
            self.notify("Address book sync disabled")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Disable failed: {exc}", severity="error")
            return
        await self.refresh_data()

    @on(Button.Pressed, "#btn-sync-auto")
    async def on_sync_auto_pressed(self) -> None:
        auto_apply = not self.sync_status.get("auto_apply", False)
        try:
            self.sync_status = await self.client.call(
                "addressbook.enable_sync",
                {"enabled": True, "auto_apply": auto_apply},
            )
            self.notify(f"Auto-apply {'enabled' if auto_apply else 'disabled'}")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Auto-apply toggle failed: {exc}", severity="error")
            return
        await self.refresh_data()

    @on(Button.Pressed, "#btn-sync-apply")
    async def on_sync_apply_pressed(self) -> None:
        if not self.pending_updates:
            return
        pending_id = self.pending_updates[0]["id"]
        try:
            await self.client.call("addressbook.apply_pending_update", {"id": pending_id})
            self.notify("Applied pending sync update")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Apply failed: {exc}", severity="error")
            return
        await self.action_refresh()

    @on(Button.Pressed, "#btn-sync-reject")
    async def on_sync_reject_pressed(self) -> None:
        if not self.pending_updates:
            return
        pending_id = self.pending_updates[0]["id"]
        try:
            await self.client.call("addressbook.reject_pending_update", {"id": pending_id})
            self.notify("Rejected pending sync update")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Reject failed: {exc}", severity="error")
            return
        await self.refresh_data()
