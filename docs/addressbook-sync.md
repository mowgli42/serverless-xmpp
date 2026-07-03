# Address Book Sync

Optional feature for **trusted groups** using XMPP server transport. Peers push signed contact add/update/remove operations; receivers verify the sender is already in their local address book.

Direct P2P transport does not carry sync IQs — both peers need XMPP server connectivity for sync (or use manual file sharing).

## Setup

1. Configure XMPP server credentials in `config.toml` (`[xmpp] jid`, `password`, `server`).
2. Add a shared secret (out-of-band — Signal, in person, etc.):

```toml
[addressbook.sync]
enabled = true
secret = "your-shared-group-secret"
auto_apply = false   # true = apply immediately; false = pending review queue
max_timestamp_skew_seconds = 300
```

3. Enable via API or set `enabled = true` before starting the service:

```json
{"method":"addressbook.enable_sync","params":{"enabled":true,"auto_apply":false}}
```

## Workflow

| Action | RPC |
|--------|-----|
| Check status | `addressbook.sync_status` |
| Push book version to XMPP contacts | `addressbook.sync_now` |
| List inbound pending updates | `addressbook.get_pending_updates` |
| Apply one pending update | `addressbook.apply_pending_update` `{"id":"..."}` |
| Reject one | `addressbook.reject_pending_update` `{"id":"..."}` |

Local mutations (`addressbook.add` / `update` / `remove`) automatically broadcast signed updates to XMPP-server contacts when sync is enabled.

## Push events

- `addressbook.sync_pending` — `{id, from_jid, action}` when a verified update awaits review
- `addressbook.updated` — after apply (same as manual edits)

## Security model

- Updates accepted **only** from JIDs already in the local address book
- HMAC-SHA256 signature over canonical JSON payload
- Timestamps must be within `max_timestamp_skew_seconds`
- Secret is never logged; enabling sync without a secret returns an error

## See also

- [api.md](./api.md) — full RPC reference
- [architecture.md](./architecture.md) — protocol namespace `urn:serverless-xmpp:addressbook:1`
