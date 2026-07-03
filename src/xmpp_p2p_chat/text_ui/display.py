"""Pure display helpers for the Textual TUI (unit-testable)."""

from __future__ import annotations

from datetime import datetime

from xmpp_p2p_chat.common.addressbook_hash import render_hash_grid_rich


def presence_symbol(show: str) -> str:
    return {"available": "●", "away": "◐", "busy": "◉", "offline": "○"}.get(show, "○")


def transport_label(contact: dict) -> str:
    transport = contact.get("preferred_transport", "xmpp-server")
    if transport == "direct-p2p":
        direct = contact.get("direct") or {}
        return f"P2P {direct.get('host', '?')}:{direct.get('port', '?')}"
    server = contact.get("xmpp_server") or "auto"
    return f"XMPP ({server})"


def format_contact_detail(contact: dict, presence: dict) -> str:
    pres = presence.get(contact.get("id", ""), {})
    show = pres.get("show", "offline")
    status = pres.get("status", "")
    lines = [
        f"[bold]{contact.get('name', '?')}[/]  ({contact.get('id', '?')})",
        f"JID: [cyan]{contact.get('jid', '?')}[/]",
        f"Transport: {transport_label(contact)}",
        f"Presence: {presence_symbol(show)} {show}" + (f" — {status}" if status else ""),
    ]
    tags = contact.get("tags") or []
    if tags:
        lines.append(f"Tags: {', '.join(tags)}")
    notes = contact.get("notes") or ""
    if notes:
        lines.append(f"Notes: {notes}")
    direct = contact.get("direct")
    if direct:
        fp = direct.get("public_key_fingerprint")
        lines.append(f"Direct: {direct.get('host')}:{direct.get('port')}")
        if fp:
            lines.append(f"Fingerprint: [dim]{fp[:48]}…[/]" if len(fp) > 48 else f"Fingerprint: {fp}")
    return "\n".join(lines)


def format_contact_summary(
    *,
    version: int | str,
    contact_count: int,
    online_count: int,
    warning_count: int = 0,
) -> str:
    warn = f" · [yellow]{warning_count} warn[/]" if warning_count else ""
    return f"v{version} · {contact_count} contacts · {online_count} online{warn}"


PRESENCE_SORT_ORDER = {"available": 0, "away": 1, "busy": 2, "offline": 3}


def find_local_contact(contacts: list[dict], local_jid: str) -> dict | None:
    needle = local_jid.lower()
    for contact in contacts:
        if contact.get("jid", "").lower() == needle:
            return contact
    return None


def is_transport_connected(connection: dict | None) -> bool:
    if not connection:
        return False
    return any(t.get("state") == "connected" for t in connection.get("transports") or [])


def format_local_identity(local_jid: str, local_contact: dict | None = None) -> str:
    if local_contact:
        name = local_contact.get("name", local_jid)
        return f"[bold]You:[/] {name} [dim]({local_jid})[/]"
    return f"[bold]You:[/] [cyan]{local_jid}[/] [dim]· not listed in address book[/]"


def format_hash_compact(content_hash: str, *, short_len: int = 12) -> str:
    if not content_hash:
        return ""
    short = content_hash.replace("SHA256:", "")[:short_len]
    return f"[dim]Book {short}…[/]"


def format_hash_awaiting(content_hash: str, *, grid: int = 8) -> str:
    if not content_hash:
        return "[yellow]Awaiting connection[/] — loading address book…"
    short = content_hash.replace("SHA256:", "")[:12]
    return (
        f"[yellow]Awaiting connection[/] — verify book hash [dim]{short}…[/]\n"
        + render_hash_grid_rich(content_hash, grid=grid)
    )


def sort_contacts(
    contacts: list[dict],
    presence: dict[str, dict],
    *,
    mode: str = "status",
) -> list[dict]:
    if mode == "name":
        return sorted(contacts, key=lambda c: c.get("name", "").lower())
    return sorted(
        contacts,
        key=lambda c: (
            PRESENCE_SORT_ORDER.get(presence.get(c["id"], {}).get("show", "offline"), 99),
            c.get("name", "").lower(),
        ),
    )


def prepare_contact_list(
    contacts: list[dict],
    presence: dict[str, dict],
    *,
    needle: str = "",
    sort_mode: str = "status",
) -> list[dict]:
    filtered = filter_contacts(contacts, needle)
    return sort_contacts(filtered, presence, mode=sort_mode)


def format_hash_sidebar(content_hash: str, *, grid: int = 8, short_len: int = 16) -> str:
    """Full hash grid for settings / address book screens."""
    if not content_hash:
        return ""
    short = content_hash.replace("SHA256:", "")[:short_len]
    return f"[dim]Book hash {short}…[/]\n" + render_hash_grid_rich(content_hash, grid=grid)


def format_message_timestamp(ts: str | datetime) -> str:
    if isinstance(ts, datetime):
        return ts.strftime("%H:%M")
    if isinstance(ts, str) and "T" in ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
        except ValueError:
            return ts[:5] if len(ts) >= 5 else ts
    return str(ts)[:5] if ts else ""


def format_message_line(
    msg: dict,
    *,
    peer_name: str = "Peer",
) -> tuple[str, str]:
    """Return (style_class, rich_text_line) for one chat message."""
    ts = format_message_timestamp(msg.get("timestamp", ""))
    direction = msg.get("direction", "in")
    name = "You" if direction == "out" else peer_name
    style = "msg-out" if direction == "out" else "msg-in"
    status = msg.get("status", "")
    marker = " [green]✓[/]" if status in ("delivered", "sent") else (
        " [yellow]…[/]" if status == "pending" else ""
    )
    align = "right" if direction == "out" else "left"
    body = msg.get("body", "")
    line = (
        f"[{style}][{align}][dim]{ts}[/dim] {name}:[/{align}]\n"
        f"[{style}][{align}]{body}{marker}[/{align}][/{style}]"
    )
    return style, line


def format_message_log(messages: list[dict], *, peer_name: str = "Peer") -> str:
    if not messages:
        return "[dim]No messages yet. Say hello![/]"
    return "\n\n".join(format_message_line(m, peer_name=peer_name)[1] for m in messages)


def format_pending_update_line(update: dict) -> str:
    action = update.get("action", "?")
    from_jid = update.get("from_jid", "?")
    contact_id = update.get("contact_id", "?")
    return f"[cyan]{action}[/] from {from_jid} · contact [bold]{contact_id}[/]"


def format_sync_status_panel(
    *,
    sync_status: dict,
    pending_updates: list[dict] | None = None,
    max_pending_lines: int = 4,
) -> str:
    enabled = sync_status.get("enabled", False)
    auto_apply = sync_status.get("auto_apply", False)
    pending_count = sync_status.get("pending_count", 0)
    secret_configured = sync_status.get("secret_configured", False)

    if not secret_configured:
        state = "[yellow]Not configured[/] — set [addressbook.sync] secret in config"
    elif enabled:
        state = "[green]Enabled[/]"
    else:
        state = "[dim]Disabled[/]"

    mode = "auto-apply" if auto_apply else "manual review"
    lines = [
        f"[bold]Address book sync[/]  {state}",
        f"Mode: {mode} · Pending: {pending_count}",
    ]

    pending = pending_updates or []
    if pending_count and not pending:
        lines.append("[dim]Loading pending updates…[/]")
    elif pending:
        for update in pending[:max_pending_lines]:
            lines.append(f"  • {format_pending_update_line(update)}")
        if len(pending) > max_pending_lines:
            lines.append(f"  [dim]…and {len(pending) - max_pending_lines} more[/]")

    return "\n".join(lines)


def format_addressbook_status_panel(
    *,
    health: dict,
    ab_status: dict,
    connection: dict,
    contact_count: int | None = None,
) -> str:
    ok = health.get("ok", True)
    count = contact_count if contact_count is not None else ab_status.get("contact_count", 0)
    version = ab_status.get("version", 0)
    warnings = (ab_status.get("warnings") or []) + (health.get("warnings") or [])
    outbox = health.get("pending_outbox", 0)
    uptime = int(health.get("uptime_seconds", 0))
    transports = connection.get("transports") or []
    transport_line = " · ".join(
        f"{t.get('transport', '?')}:{t.get('state', '?')}" for t in transports
    ) or "no transports"
    fp = connection.get("p2p_fingerprint")
    fp_line = ""
    if fp:
        fp_line = f"\nP2P fingerprint: [dim]{fp[:44]}…[/]" if len(fp) > 44 else f"\nP2P fingerprint: {fp}"

    status_icon = "[green]✓ OK[/]" if ok and not warnings else "[yellow]⚠ Issues[/]"
    warn_block = ""
    if warnings:
        warn_block = "\n[yellow]" + "\n".join(f"• {w}" for w in warnings[:4]) + "[/]"
        if len(warnings) > 4:
            warn_block += f"\n[dim]…and {len(warnings) - 4} more warnings[/]"

    primary = ab_status.get("primary_path", "")
    path_line = f"\n[dim]File: {primary}[/]" if primary else ""

    return (
        f"{status_icon}  [bold]v{version}[/] · {count} contacts · outbox {outbox} · uptime {uptime}s\n"
        f"Transports: {transport_line}{fp_line}{path_line}{warn_block}"
    )


def filter_contacts(contacts: list[dict], needle: str) -> list[dict]:
    q = needle.lower()
    if not q:
        return list(contacts)
    return [
        c
        for c in contacts
        if q in c.get("name", "").lower()
        or q in c.get("jid", "").lower()
        or q in c.get("id", "").lower()
    ]


__all__ = [
    "filter_contacts",
    "find_local_contact",
    "format_addressbook_status_panel",
    "format_contact_detail",
    "format_contact_summary",
    "format_hash_awaiting",
    "format_hash_compact",
    "format_hash_sidebar",
    "format_local_identity",
    "format_message_line",
    "format_message_log",
    "format_message_timestamp",
    "format_pending_update_line",
    "format_sync_status_panel",
    "is_transport_connected",
    "prepare_contact_list",
    "presence_symbol",
    "sort_contacts",
    "transport_label",
]
