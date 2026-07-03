# Text TUI display walkthrough

Step-by-step tour of the **Textual TUI** display states, keyboard workflow, and what to expect when things go wrong.

See also: [display-walkthrough-web.md](display-walkthrough-web.md) · [troubleshooting-displays.md](troubleshooting-displays.md)

---

## 1. Launch

```bash
# Terminal 1
python -m xmpp_p2p_chat.connection_service

# Terminal 2
python -m xmpp_p2p_chat.text_ui
```

**Initial display**

| Region | Content |
|--------|---------|
| Header | App title + clock |
| Sidebar header | `Loading…` → `v{N} · {count} contacts · {online} online` |
| Hash grid | 8×8 colored blocks under contact summary (when address book loaded) |
| Contact list | One row per contact: presence dot, name, JID, transport |
| Main pane | “Select a contact to chat” placeholder |
| Status bar | Transport state · contact count · optional outbox count |

---

## 2. Normal workflow

### Step A — Browse contacts

1. Use **↑/↓** or **j/k** to highlight a contact in the sidebar.
2. Type in the **Search** box to filter by name or JID (`filter_contacts` in `text_ui/display.py`).
3. Press **Enter** to open a chat.

**Expected:** Chat header shows name, JID, transport, presence. Message history loads from the service.

### Step B — Send a message

1. Press **/** to focus the message input.
2. Type text and press **Enter**.

**Expected:** Optimistic “pending” marker (`…`), then ✓ when the service confirms delivery.

### Step C — Address book screen (`a`)

| Key | Action |
|-----|--------|
| `a` | Open address book modal |
| `n` | New contact form |
| `Delete` | Remove selected contact (with confirmation) |
| `r` | Reload address book from disk |
| `Enter` | Open chat for selected row |
| `Esc` / `q` | Close modal |

**Status panel shows:** OK/issues icon, version, contact count, outbox, uptime, transports, file path, warnings, hash grid.

### Step D — Refresh (`r`)

Reloads contacts and hash from the service without opening the address book modal.

---

## 3. Display states reference

| State | Where shown | Trigger |
|-------|-------------|---------|
| `v{N} · contacts · online` | Sidebar summary | `addressbook.list` success |
| Hash grid | Sidebar + address book | `status.content_hash` present |
| `[red]Error: …` | Status bar | API call failure on load |
| `Service unavailable — retrying…` | Status bar | Periodic status refresh failed |
| `Transport: {state}` | Status bar | `connection.changed` push event |
| `⚠ Issues` + bullet warnings | Address book status | Fragment/health warnings |
| Pending `…` on message | Chat log | Outbound before ACK |
| Green `✓` | Chat log | `sent` / `delivered` status |

---

## 4. Failure scenarios (what you should see)

These are covered by `tests/test_text_ui_failures.py`:

| Scenario | User-visible result | Log hint |
|----------|---------------------|----------|
| Service not running | `Error: …` / `Service unavailable` | `@ebk event=ui.api.disconnected` |
| Send while transport down | Notify: “Send failed: …”, message stays pending | `@ebk event=rpc.error method=chat.send_message` |
| Corrupt address book fragment | Yellow warning count in summary | `addressbook` warnings in health |
| 100+ messages in history | Chat log renders all lines (scroll) | — |
| Connection drop mid-session | Status bar shows `disconnected` | `connection.changed` push |

---

## 5. Automated display tests

```bash
pytest tests/test_text_ui_display.py tests/test_text_ui_failures.py -v
```

Tests use **Textual Pilot** with a **MockAPIClient** — no live service required for UI unit tests.

---

## 6. Logging for troubleshooting

Configure structured logs in `config.toml`:

```toml
[logging]
level = "INFO"
file = "~/.local/share/xmpp-p2p-chat/service.log"
json_file = "~/.local/share/xmpp-p2p-chat/service.json.log"
ebk_stderr = true
```

- **JSON file** — ship to SigNoz / OTLP collectors (`event`, `method`, `contact_count`, etc.).
- **@ebk lines on stderr** — parsed by Chaterm-style AI terminals and OpenClaw agents alongside the TUI.

Example EBK line:

```
@ebk ts=2026-07-03T12:00:00+00:00 level=warning event=ui.api.disconnected error="Connection refused" url=ws://127.0.0.1:8765/rpc
```
