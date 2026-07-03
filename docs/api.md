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

Returns all contacts, last-known presence, and address book version/hash status.

```json
// Request
{"jsonrpc":"2.0","id":"1","method":"addressbook.list","params":{}}

// Response
{
  "result": {
    "contacts": [{"id":"bob","jid":"bob@p2p.local","name":"Bob", "...": "..."}],
    "presence": {"bob": {"show": "available", "status": ""}},
    "status": {
      "version": 1,
      "content_hash": "SHA256:abc123...",
      "hash_blocks": ["#a1b2c3", "..."],
      "contact_count": 1,
      "primary_path": "/path/to/addressbook.json",
      "warnings": []
    }
  }
}
```

### `addressbook.status`

Returns version, content hash, hash visualization blocks, and file paths without listing contacts.

```json
{"jsonrpc":"2.0","id":"1","method":"addressbook.status","params":{}}
```

### `addressbook.reload`

Re-reads the address book from disk (after external edits) and broadcasts `addressbook.updated`.

```json
{"jsonrpc":"2.0","id":"1","method":"addressbook.reload","params":{}}
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

When `[addressbook.sync] enabled = true`, mutations are signed and pushed to XMPP-server contacts.

### Address book sync (XMPP server mode)

Requires `[addressbook.sync] secret` shared out-of-band among trusted peers.

| Method | Purpose |
|--------|---------|
| `addressbook.sync_status` | `{enabled, auto_apply, pending_count, secret_configured}` |
| `addressbook.enable_sync` | `{"enabled": true, "auto_apply": false}` |
| `addressbook.sync_now` | Push announce to XMPP contacts; optional `contact_ids` filter |
| `addressbook.get_pending_updates` | List inbound updates awaiting review |
| `addressbook.apply_pending_update` | `{"id": "<pending-id>"}` |
| `addressbook.reject_pending_update` | `{"id": "<pending-id>"}` |

Push event: `addressbook.sync_pending` — `{id, from_jid, action}`

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

Returns transport states, local JID, structured XMPP errors, and P2P fingerprint when available.

```json
{
  "result": {
    "transports": [
      {
        "transport": "xmpp-server",
        "state": "connected",
        "jid": "alice@example.com",
        "error_condition": null,
        "error_type": null,
        "stream_management": {"enabled": true, "sm_id_present": true}
      }
    ],
    "local_jid": "alice@p2p.local",
    "p2p_fingerprint": "SHA256:...",
    "p2p_listen_port": 5223
  }
}
```

Configure XMPP resilience under `[xmpp]`:

```toml
[xmpp]
ping_interval_seconds = 90
ping_timeout_seconds = 30
stream_management_enabled = true
```

### `connection.reconnect`

Force transport reconnect.

### `discovery.list`

List peers discovered on the local network via mDNS (when `[p2p] mdns_enabled = true`).

```json
{
  "result": {
    "peers": [
      {
        "jid": "bob@p2p.local",
        "host": "192.168.1.50",
        "port": 5224,
        "fingerprint": "SHA256:...",
        "service_name": "bob-p2p-local._xmpp-p2p._tcp.local."
      }
    ]
  }
}
```

### `discovery.apply`

Apply a discovered peer's host/port/fingerprint to an existing address book contact (matched by JID).

```json
{"method":"discovery.apply","params":{"contact_id":"bob"}}
```

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
| `addressbook.updated` | `{contacts, version, content_hash}` |
| `connection.changed` | transport status object |
| `discovery.updated` | `{peers: [...]}` |

## Web UI

When `[ui] serve_web = true`, the service also serves the built SPA at `http://127.0.0.1:8767/` if `web_ui/dist` exists.

Build first: `cd web_ui && npm install && npm run build`
