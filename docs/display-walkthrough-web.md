# Web UI display walkthrough

Step-by-step tour of the **Svelte Web SPA** layout, interaction flow, and failure displays.

See also: [display-walkthrough-tui.md](display-walkthrough-tui.md) · [troubleshooting-displays.md](troubleshooting-displays.md)

---

## 1. Launch

```bash
python -m xmpp_p2p_chat.connection_service
# Build once: cd web_ui && npm install && npm run build
# Open http://127.0.0.1:8767/
```

---

## 2. Layout regions

```
┌─────────────────────────────────────────────────────────┐
│ Header: status line · settings toggle                    │
├──────────────┬──────────────────────────────────────────┤
│ Sidebar      │ Chat header (selected contact)             │
│ · Search     │ Message list (bubbles)                   │
│ · HashGrid   │ Composer (Enter / Ctrl+Enter to send)    │
│ · Contacts   │                                          │
├──────────────┴──────────────────────────────────────────┤
│ Settings panel (optional): hash, reload, add contact,   │
│ discovery peers, health, reconnect                      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Normal workflow

### Step A — Connect and load

1. Page loads → WebSocket to `ws://127.0.0.1:8765/rpc`.
2. `waitForService()` polls until connected (max ~7.5s).
3. `addressbook.list` populates sidebar + `addressbookStatus` (version, hash).

**Expected status:** `connected` then transport line from `refreshStatus()` every 5s.

### Step B — Select contact

1. Click a contact in the sidebar (mobile: sidebar overlay).
2. `chat.start` + `chat.get_history` load messages.

### Step C — Send message

1. Type in composer; **Enter** or **Ctrl/Cmd+Enter** sends.
2. Optimistic append with delivery marker when confirmed.

### Step D — Settings panel

- **HashGrid** — same 8×8 fingerprint as TUI (`HashGrid.svelte` + `display.js`).
- **Reload from disk** — calls `addressbook.reload`.
- **Add contact** — form → `addressbook.add`.
- **Reconnect** — `connection.reconnect`.
- **Discovery** — lists mDNS peers, apply to matching JID.

---

## 4. Display helpers (unit-tested)

Logic lives in `web_ui/src/lib/display.js`:

| Function | Purpose |
|----------|---------|
| `filterContacts` | Sidebar search |
| `formatTime` | Message timestamps |
| `buildStatusLine` | Header transport + outbox summary |
| `connectionStatusFromError` | `error: …` / `connecting` / `connected` |
| `hashCells` | Colors for `HashGrid` |

`ChatAPI` (`api.js`) handles WebSocket JSON-RPC and push events — tested in `api.test.js`.

---

## 5. Failure scenarios

| Scenario | UI display | Test coverage |
|----------|------------|---------------|
| Service down on load | `error: Service connection timeout` | `connectionStatusFromError` unit test |
| RPC error on loadContacts | `error: {message}` | `display.test.js` |
| Status refresh fails | `disconnected` | manual / integration |
| WebSocket drop mid-call | Pending `call()` rejects | `api.test.js` |
| Invalid contact JID (settings) | API error in status | `test_display_failures.py` (service) |
| Flood of list calls | UI remains responsive | `test_display_failures.py` |

---

## 6. Automated tests

```bash
cd web_ui && npm install && npm test
pytest tests/test_display_failures.py -v
```

---

## 7. Push events → display updates

| Event | UI reaction |
|-------|-------------|
| `addressbook.updated` | Reload contacts + hash |
| `message.received` | Append to active chat |
| `message.updated` | Update delivery marker |
| `presence.updated` | Refresh presence dots |
| `connection.changed` | Status line on next poll |
| `discovery.updated` | Peer list in settings |

---

## 8. Logging correlation

When debugging Web UI issues, correlate browser **Network → WS** frames with service logs:

```toml
[logging]
json_file = "~/.local/share/xmpp-p2p-chat/service.json.log"
ebk_stderr = true
```

Look for:

- `event=rpc.client.connected` / `rpc.client.disconnected`
- `event=rpc.error` with `method=addressbook.list` or `chat.send_message`
- `event=service.start` with `contact_count` and `content_hash`

EBK stderr lines are safe to paste into AI terminal agents for automated triage.
