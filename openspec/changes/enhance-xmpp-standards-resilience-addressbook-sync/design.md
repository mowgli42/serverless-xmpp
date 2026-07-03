# Design: XMPP Resilience & Address Book Sync

## Overview

Enhancements apply to the **Connection Service** XMPP server transport layer and **AddressBookManager**. UIs consume new API fields and events; no stanza parsing in UIs.

```
┌─────────────────────────────────────────────────────────────┐
│ Connection Service                                           │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │ XMPPServerTransport │    │ AddressBookManager          │ │
│  │ · xep_0198 (SM)     │    │ · local JSON (source of     │ │
│  │ · xep_0199 (ping)   │◄──►│   truth)                    │ │
│  │ · error parser      │    │ · AddressBookSyncService    │ │
│  │ · PingKeepalive     │    │   (sign / verify / pending) │ │
│  └──────────┬──────────┘    └─────────────────────────────┘ │
│             │                          ▲                     │
│             │ IQ / message               │ apply / pending    │
│             ▼                          │                     │
│  ┌─────────────────────┐    ┌──────────┴──────────────────┐  │
│  │ SessionManager      │───►│ PersistenceManager          │  │
│  │ routes sync IQs     │    │ · xmpp_sm_state (optional)  │  │
│  └─────────────────────┘    │ · addressbook_sync_pending  │  │
│                             └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 1. XEP-0198 Stream Management

### Approach

Use slixmpp built-in `xep_0198` plugin (already in slixmpp). Register on `XMPPClient` alongside `xep_0030` and `xep_0199`.

**Plugin config** (injected at client creation):

```python
{
    "allow_resume": True,
    "sm_id": "<restored or None>",
    "handled": <int>,
    "last_ack": <int>,
    "window": 5,
}
```

**Lifecycle hooks**:

| Event | Action |
|-------|--------|
| `sm_enabled` | Persist `{sm_id, handled, last_ack, jid, saved_at}` to `.xmpp-sm-state.json` |
| `session_resumed` | Log + emit transport state; update persisted handled |
| `sm_failed` | Clear persisted SM id; fall back to fresh bind |
| `disconnected` | Save current plugin counters before reconnect task runs |

**Persistence file**: `{data_directory}/.xmpp-sm-state.json`

```json
{
  "jid": "alice@example.com",
  "sm_id": "abc123",
  "handled": 42,
  "last_ack": 40,
  "saved_at": "2026-07-03T12:00:00+00:00"
}
```

On reconnect, load state **only if JID matches** current config JID.

### Service Discovery

slixmpp SM plugin registers stream features automatically after bind. No separate disco#info step required for enable; resume uses stored `sm_id`.

## 2. XEP-0199 Ping Keepalive

### `PingKeepalive` task (in `xmpp_server.py`)

- Interval: `[xmpp] ping_interval_seconds` (default **90**)
- Timeout: `[xmpp] ping_timeout_seconds` (default **30**)
- Calls existing `XMPPServerTransport.ping()` → slixmpp `xep_0199.ping()`
- On `IqTimeout` or `False`: log warning, call `_handle_disconnected()` to trigger reconnect path
- Cancelled on `disconnect()`

## 3. XMPP Error Handling

### `parse_xmpp_error(exc) → XmppErrorInfo`

Maps slixmpp exceptions and error stanzas to:

```python
class XmppErrorInfo(BaseModel):
    condition: str | None = None   # e.g. remote-server-timeout
    error_type: str | None = None  # cancel, continue, modify, auth, wait, payment
    text: str | None = None
    raw: str | None = None
```

**Extended `TransportStatus`**:

```python
error_condition: str | None = None
error_type: str | None = None
```

Populate on connection failure (`IqError`, stream errors) and expose via `connection.status`.

## 4. Address Book Sync Protocol

### Namespace

`urn:serverless-xmpp:addressbook:1`

### Update payload (JSON inside IQ)

Sent as base64-encoded JSON in `<payload>` child element:

```json
{
  "action": "add" | "update" | "remove",
  "version": 5,
  "content_hash": "SHA256:…",
  "contact": { … Contact model … },
  "contact_id": "bob",
  "timestamp": "2026-07-03T12:00:00+00:00",
  "signature": "<base64 HMAC-SHA256>"
}
```

**Signing**: `HMAC-SHA256(sync_secret, canonical_json_without_signature)`

- `sync_secret` from config `[addressbook.sync] secret` (shared out-of-band among group)
- If secret empty, sync is disabled

### Stanza shape (conceptual)

```xml
<iq type="set" id="…" to="peer@server" from="me@server">
  <update xmlns="urn:serverless-xmpp:addressbook:1">
    <payload>BASE64(JSON)</payload>
  </update>
</iq>
```

### Trust model

1. Sender JID (bare) **must** exist in receiver's address book.
2. Signature **must** verify with configured `sync_secret`.
3. `timestamp` skew ≤ 5 minutes (configurable).
4. If `[addressbook.sync] auto_apply = false` (default), store in **pending** table for UI review.

### Conflict handling

- Same `contact_id`, newer `timestamp` wins for auto-apply mode.
- Version/hash mismatch → still apply contact delta but bump local version on persist.
- `remove` ignored if contact_id unknown.

### API methods

| Method | Purpose |
|--------|---------|
| `addressbook.sync_status` | `{enabled, auto_apply, pending_count}` |
| `addressbook.enable_sync` | `{enabled: bool, auto_apply?: bool}` |
| `addressbook.sync_now` | Push pending local changes to all XMPP contacts (or `contact_ids` filter) |
| `addressbook.get_pending_updates` | List pending inbound updates |
| `addressbook.apply_pending_update` | `{id}` apply one pending update |
| `addressbook.reject_pending_update` | `{id}` discard |

### Push events

- `addressbook.sync_pending` — new pending update received
- `addressbook.updated` — unchanged (already emitted on apply)

## 5. Configuration

```toml
[xmpp]
ping_interval_seconds = 90
ping_timeout_seconds = 30
stream_management_enabled = true

[addressbook.sync]
enabled = false
secret = ""           # required when enabled; share OOB with trusted group
auto_apply = false    # true = apply verified updates immediately
max_timestamp_skew_seconds = 300
```

## 6. File layout (new / modified)

| Path | Role |
|------|------|
| `connection_service/xmpp/errors.py` | Error parsing |
| `connection_service/xmpp/sm_state.py` | SM persistence |
| `connection_service/addressbook_sync.py` | Sign, verify, pending queue |
| `connection_service/transports/xmpp_server.py` | SM, ping, IQ handler |
| `connection_service/persistence.py` | Pending sync table |
| `connection_service/api.py` | New RPC methods |
| `common/config.py` | New config fields |
| `common/models.py` | Extended TransportStatus, sync models |

## 7. Testing strategy

- **Unit**: error parser, HMAC sign/verify, SM state load/save, timestamp skew rejection
- **Transport**: mock slixmpp client; verify plugins registered, ping task lifecycle
- **Integration** (optional): Prosody Docker from `scripts/test-multi-client.sh` for manual SM validation
