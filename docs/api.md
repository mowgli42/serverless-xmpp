# Connection Service API

The Connection Service exposes a **WebSocket JSON-RPC 2.0** API on `ws://127.0.0.1:8765/rpc` (localhost only by default).

UIs (Text TUI, Web SPA) are thin clients — all XMPP/P2P logic lives in the service.

## Authentication

When `api_token` is set in config, the first message after connect must be:

```json
{"jsonrpc":"2.0","id":"1","method":"auth","params":{"token":"your-secret"}}
```

## Methods

### `addressbook.list`

Returns all contacts and last-known presence.

```json
// Request
{"jsonrpc":"2.0","id":"1","method":"addressbook.list","params":{}}

// Response
{
  "result": {
    "contacts": [{"id":"bob","jid":"bob@p2p.local","name":"Bob", "...": "..."}],
    "presence": {"bob": {"show": "available", "status": ""}}
  }
}
```

### `addressbook.add`

```json
{"jsonrpc":"2.0","id":"2","method":"addressbook.add","params":{"contact":{"id":"bob","jid":"bob@p2p.local","name":"Bob"}}}
```

### `addressbook.update` / `addressbook.remove`

```json
{"method":"addressbook.update","params":{"id":"bob","partial":{"name":"Robert"}}}
{"method":"addressbook.remove","params":{"id":"bob"}}
```

### `chat.start`

```json
{"method":"chat.start","params":{"contact_id":"bob"}}
```

### `chat.send_message`

```json
{"method":"chat.send_message","params":{"chat_id":"bob","body":"Hello!"}}
```

### `chat.get_history`

```json
{"method":"chat.get_history","params":{"chat_id":"bob","limit":50}}
```

### `presence.set`

```json
{"method":"presence.set","params":{"show":"away","status":"In a meeting"}}
```

### `connection.status`

Returns transport states and P2P fingerprint when available.

```json
{
  "result": {
    "transports": [{"transport":"direct-p2p","state":"connected","jid":"..."}],
    "p2p_fingerprint": "SHA256:...",
    "p2p_listen_port": 5223
  }
}
```

### `connection.reconnect`

Force transport reconnect.

### `system.health`

```json
{
  "result": {
    "ok": true,
    "uptime_seconds": 120.5,
    "contact_count": 3,
    "active_chats": 1,
    "pending_outbox": 0,
    "warnings": []
  }
}
```

### `system.shutdown`

Gracefully stops the service.

## Push Events (server → client)

No `id` field — these are notifications:

| Event | Payload |
|-------|---------|
| `message.received` | `{chat_id, message}` |
| `message.updated` | `{chat_id, message}` |
| `presence.updated` | `{contact_id, show, status}` |
| `addressbook.updated` | `{contacts: N}` |
| `connection.changed` | transport status object |

## Web UI

When `[ui] serve_web = true`, the service also serves the built SPA at `http://127.0.0.1:8767/` if `web_ui/dist` exists.

Build first: `cd web_ui && npm install && npm run build`
