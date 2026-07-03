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
│ · You: identity│ Message list (bubbles)                   │
│ · Search     │ Composer (Enter / Ctrl+Enter to send)    │
│ · Sort toggle│                                          │
│ · HashGrid*  │                                          │
│ · Contacts   │                                          │
├──────────────┴──────────────────────────────────────────┤
│ Settings panel (optional): full hash grid, reload,      │
│ add contact, discovery peers, health, reconnect         │
└─────────────────────────────────────────────────────────┘

* HashGrid in sidebar only while awaiting transport connection.
  When connected, sidebar shows a compact hash prefix instead.
```

---

## 3. Normal workflow

### Step A — Connect and load

1. Page loads → WebSocket to `ws://127.0.0.1:8765/rpc`.
2. `waitForService()` polls until connected (max ~7.5s).
3. `addressbook.list` populates sidebar + `addressbookStatus` (version, hash).
4. `connection.status` provides `local_jid` for the **You:** identity line.

**Expected status:** transport line from `refreshStatus()` every 5s. Sidebar hash grid appears only while no transport is connected.

### Step B — Select contact

1. Use **Search** to filter contacts by name or JID.
2. Click **Sort: connection status / name** to toggle ordering (presence first by default).
3. Click a contact in the sidebar (mobile: sidebar overlay).
4. `chat.start` + `chat.get_history` load messages.

### Step C — Send message

1. Type in composer; **Enter** or **Ctrl/Cmd+Enter** sends.
2. Optimistic append with delivery marker when confirmed.

### Step D — Settings panel

- **HashGrid** — full 8×8 fingerprint (always available here for verification).
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
| `prepareContactList` | Search + sort (status or name) |
| `sortContacts` | Order by presence or alphabetical name |
| `findLocalContact` / `formatLocalIdentity` | Match `local_jid` in address book |
| `isAwaitingConnection` / `formatHashCompact` | Connection-aware hash display |
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
