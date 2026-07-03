# Display troubleshooting guide

Reference for diagnosing UI display issues using **automated failure tests**, **structured JSON logs** (SigNoz), and **@ebk status lines** (Chaterm / OpenClaw agents).

---

## Quick diagnosis

| Symptom | Likely cause | Check |
|---------|--------------|-------|
| TUI: `Error: …` on startup | Connection service not running or wrong port | `ss -tlnp \| grep 8765`, service logs |
| TUI: empty hash grid | No address book / empty contacts | `addressbook.status` RPC, data dir |
| Web: `connecting` forever | WebSocket blocked or service down | Browser devtools → WS to `:8765/rpc` |
| Web: `disconnected` in header | Status poll failing | `@ebk event=rpc.client.disconnected` |
| Both: version mismatch | Different address book files | Compare hash grid + `v{N}` |
| Messages stuck pending | Transport offline | `connection.status`, outbox in health |
| Yellow warnings in TUI | Bad JSON fragment or health issue | `system.health` → `warnings` |

---

## Test suites

Run the full display + failure matrix:

```bash
# TUI display + failure paths
pytest tests/test_text_ui_display.py tests/test_text_ui_failures.py -v

# Service RPC failure scenarios
pytest tests/test_display_failures.py -v

# Structured logging
pytest tests/test_structured_logging.py -v

# Web UI unit tests
cd web_ui && npm test
```

### What each suite exercises

| Suite | Scenarios |
|-------|-----------|
| `test_text_ui_display.py` | Helpers, sidebar version/hash, filter, message formatting, address book panel |
| `test_text_ui_failures.py` | API down, send failure, corrupt data warnings, message flood, connection.changed |
| `test_display_failures.py` | Invalid JSON-RPC, bad JID, malformed fragments, RPC flood, unknown methods |
| `test_structured_logging.py` | SigNoz JSON shape, EBK formatter, service.start event in log file |
| `web_ui/src/lib/*.test.js` | filterContacts, status lines, ChatAPI push/reject |

---

## Logging configuration

```toml
[logging]
level = "INFO"
file = "~/.local/share/xmpp-p2p-chat/service.log"          # human-readable
json_file = "~/.local/share/xmpp-p2p-chat/service.json.log"  # SigNoz / OTLP
ebk_stderr = true                                             # AI terminal agents
```

### SigNoz JSON record shape

```json
{
  "timestamp": "2026-07-03T12:00:00.123456+00:00",
  "severity_text": "INFO",
  "severity_number": 20,
  "body": "Connection service listening on ws://127.0.0.1:8765/rpc (2 contacts)",
  "logger": "xmpp_p2p_chat.connection_service.service",
  "attributes": {
    "event": "service.start",
    "api_host": "127.0.0.1",
    "api_port": 8765,
    "contact_count": 2,
    "addressbook_version": 1,
    "content_hash": "SHA256:abc123..."
  }
}
```

Import `json_file` into SigNoz via OTLP filelog receiver or your collector pipeline.

### EBK status lines

Emitted on **stderr** when `ebk_stderr = true` and the log record includes an `event` field:

```
@ebk ts=2026-07-03T12:00:01+00:00 level=info event=service.start api_host=127.0.0.1 api_port=8765 contact_count=2
@ebk ts=2026-07-03T12:00:05+00:00 level=warning event=ui.api.disconnected error="Connection refused" url=ws://127.0.0.1:8765/rpc
@ebk ts=2026-07-03T12:00:06+00:00 level=error event=rpc.error method=chat.send_message error="Transport offline"
```

**Chaterm / OpenClaw agents** can grep stderr for `@ebk` and map `event=` to remediation playbooks.

### Standard events

| event | When |
|-------|------|
| `service.start` | Connection service ready |
| `service.shutdown` | Graceful stop |
| `rpc.client.connected` | UI WebSocket attached |
| `rpc.client.disconnected` | UI WebSocket closed |
| `rpc.error` | RPC handler exception |
| `ui.api.disconnected` | TUI/Web client lost WS to service |

---

## Manual reproduction scripts

### Simulate API loss (TUI)

1. Start TUI with service running.
2. Kill service: `fuser -k 8765/tcp`
3. Press `r` or wait 5s for status poll.

**Expected:** `[red]Service unavailable — retrying…[/]` in status bar.

### Simulate data errors

```bash
echo '{broken' >> ~/.local/share/xmpp-p2p-chat/addressbooks.d/bad.json
# Restart service or RPC: addressbook.reload
```

**Expected:** Warnings in TUI summary and address book status panel.

### Simulate message flood

Use `test_text_ui_failures.test_flood_of_messages_renders_all` as reference — 100 messages should all appear in `#chat-log`.

---

## Walkthroughs

- [Text TUI walkthrough](display-walkthrough-tui.md)
- [Web UI walkthrough](display-walkthrough-web.md)
