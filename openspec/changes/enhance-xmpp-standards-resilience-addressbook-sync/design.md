# Design: Serverless XMPP P2P Chat Client - Architecture and Technical Approach

## High-Level Architecture

The system follows a **strict layered, decoupled architecture** centered on a single **Connection Service** that owns all protocol logic, state, and persistence. User Interfaces (text and web) are thin clients that consume a well-defined local API.

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interfaces                         │
│  ┌──────────────────┐          ┌──────────────────────┐    │
│  │   Text TUI       │          │      Web SPA         │    │
│  │  (Textual)       │◄────────►│  (Svelte + Vite)     │    │
│  │  Terminal        │  WS/JSON │  Browser / Webview   │    │
│  └──────────────────┘          └──────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Localhost only (127.0.0.1)
┌─────────────────────────────────────────────────────────────┐
│                 Connection Service (Python)                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Layer (WebSocket server + JSON-RPC dispatcher)  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────┐  ┌──────────────────────────────┐    │
│  │ Address Book     │  │   Session & Message Manager  │    │
│  │ Manager          │  │   (queues, history, routing) │    │
│  └──────────────────┘  └──────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Transport Layer (Pluggable)                   │   │
│  │  ┌──────────────┐      ┌────────────────────────┐    │   │
│  │  │ XMPP Server  │      │ Direct P2P Stream      │    │   │
│  │  │ (slixmpp)    │      │ (custom asyncio TLS+XML)│    │   │
│  │  └──────────────┘      └────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Persistence (aiosqlite + JSON files)                  │   │
│  │  - messages.db (per-chat history)                     │   │
│  │  - addressbook.json (primary) + *.d/ (additional)     │   │
│  │  - config.toml                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   XMPP Servers      Direct Peer Clients     (Future: WebRTC / QUIC)
   (public/self-hosted)  (preplaced endpoints)
```

**Key Design Decisions**:
- **Single source of truth & state**: Connection Service is the only component that speaks XMPP or manages sockets/streams. UIs never parse stanzas or handle reconnections.
- **Event-driven push**: UIs subscribe to notifications (new message, presence change, connection status, errors) via WebSocket. No polling.
- **Local-only by default**: API server binds exclusively to 127.0.0.1. Optional auth token for extra safety on multi-user machines.
- **Pluggable transports**: Interface `ITransport` with `connect()`, `disconnect()`, `send_stanza()`, `on_stanza_received` callback. Allows adding direct P2P, WebRTC data channels, or even Matrix bridge later with minimal core changes.
- **Async everything**: Python asyncio event loop unifies slixmpp (already async), WebSocket server, DB operations, and TUI (Textual is async-friendly).

## Technology Stack & Rationale

| Component              | Choice                          | Why |
|------------------------|---------------------------------|-----|
| Language / Runtime    | Python 3.12+                   | Best-in-class XMPP support via slixmpp; excellent asyncio; Textual TUI is modern and productive; easy local scripting & debugging. Cursor handles Python very well. |
| XMPP Library (Server Mode) | slixmpp                       | Mature, actively maintained, full XEP support, asyncio native, high-level ClientXMPP + low-level XML stream access when needed. |
| TUI Framework         | Textual (by Textualize)        | Beautiful out-of-the-box, CSS-like styling, async, keyboard/mouse, splits/tabs/modals, reactive. Far superior to urwid for rapid development. |
| Web UI                | Vite + Svelte 5 + Tailwind CSS + daisyUI | Extremely fast dev/build, tiny bundle, excellent DX, reactive stores perfect for real-time WS data. Easy to theme and make accessible. |
| API / IPC             | WebSocket + JSON-RPC 2.0       | Universal (browser + Python clients), bidirectional, low overhead, easy to debug with browser devtools or `wscat`. Standard enough for future UIs. |
| Persistence           | aiosqlite (SQLite) + JSON/TOML | Zero-config, ACID, great Python support, sufficient for single-user local history. JSON for address book (human-editable). |
| Config                | tomli / tomli-w (TOML)         | Human-friendly, supports comments, standard for modern Python tools. |
| Security / Crypto     | cryptography + pyca/cryptography or keyring | TLS enforcement, optional message encryption, OS keyring for passwords where available. |
| Packaging (future)    | PyInstaller or `briefcase` / `py2app` | Single-file executables for service+TUI; web assets can be served by service or standalone. |

**Alternative considered**: Node.js + xmpp.js for connection service (great for web parity). Rejected for MVP because slixmpp + Textual gives a more cohesive Python-only core that is easier to reason about and debug for a pragmatic single-dev (or AI-assisted) workflow. Web UI remains fully independent.

## Data Models (Core)

### Address Book Contact (JSON)
```json
{
  "id": "uuid-or-slug",
  "jid": "alice@jabber.example.com",
  "name": "Alice Example",
  "avatar": "local/path/or/base64/thumb.jpg",  // optional
  "tags": ["family", "trusted"],
  "notes": "Sister - use Signal fallback if needed",
  "preferred_transport": "xmpp-server",  // or "direct-p2p"
  "xmpp_server": null,                   // null = auto SRV lookup
  "direct": {
    "host": "203.0.113.45",
    "port": 5222,
    "public_key_fingerprint": "SHA256:xxxx..."
  },
  "credentials": {                       // sensitive - handled via keyring or encrypted
    "username": "alice@jabber.example.com",
    "password_ref": "keyring:entry-id"   // or inline for dev (not recommended)
  },
  "created_at": "2026-07-02T...",
  "updated_at": "..."
}
```

Address book stored as `addressbook.json` (array of contacts) + support for `addressbooks.d/*.json` for splitting (e.g., family.json, work.json). Service merges on load with conflict rules (last-write-wins or manual).

### Message Record (SQLite)
Table `messages`:
- id (PK), chat_id (contact_id or JID), direction (in/out), body (text), timestamp, stanza_id (for dedup), delivered (bool), read (bool), raw_stanza (optional JSON for debugging)

Additional tables: `chats` (metadata per contact), `presence` (last known status per contact), `outbox` (queued messages for offline).

### Config (TOML)
```toml
[data]
directory = "~/.local/share/xmpp-p2p-chat"

[connection]
default_transport = "xmpp-server"
api_host = "127.0.0.1"
api_port = 8765
api_token = ""  # optional simple bearer for local use

[logging]
level = "INFO"
file = "logs/app.log"

[security]
enforce_tls = true
allow_self_signed_direct = false  # for direct P2P
```

## API Specification (Connection Service ↔ UIs)

**Transport**: WebSocket to `ws://127.0.0.1:8765/rpc`

**Protocol**: JSON-RPC 2.0 over WS (requests, responses, notifications for server→client push).

**Core Methods** (examples):

- `addressbook.list` → {contacts: [...]}
- `addressbook.add` (contact_obj) → {id}
- `addressbook.update` (id, partial)
- `addressbook.remove` (id)
- `chat.start` (contact_id) → {chat_id, status}
- `chat.send_message` (chat_id, body, [options]) → {message_id, timestamp}
- `chat.get_history` (chat_id, [limit, before]) → {messages: [...]}
- `presence.set` (show, status) 
- `connection.status` → current transports state
- `system.shutdown`

**Push Notifications** (server → connected clients):
- `message.received` {chat_id, message}
- `presence.updated` {contact_id, show, status}
- `connection.changed` {transport, state, error?}
- `addressbook.updated`

UIs implement a thin client library (Python for TUI, JS for web) that handles reconnection, request queuing, and event subscription.

**Auth for API**: For local single-user use, optional simple token in config or none (rely on localhost binding). Future: mTLS or OS user auth.

## Transport Layer Details (MVP + Future)

**MVP Primary: XMPP Server Transport**
- Uses `slixmpp.ClientXMPP`
- On `chat.start(contact_id)`: lookup JID → discover server (or use explicit), connect, authenticate (from address book or prompt via UI callback), send presence, ready for messages.
- Outgoing messages → `send_message(mto=jid, mbody=body, mtype='chat')`
- Incoming via registered handlers → normalize to internal Message model → persist → push to UIs.
- Auto-reconnect with exponential backoff + jitter.

**Future: Direct P2P Transport**
- Implement `DirectP2PTransport` class.
- On connect to a contact with `direct` info: open TLS socket to host:port (verify cert/fingerprint from address book).
- Perform minimal XMPP stream negotiation (open stream with from/to, optional simple auth IQ or first message contains shared secret).
- Both ends act symmetrically (can send/receive stanzas).
- Fallback or parallel use with server transport if both available.
- For local LAN: optional mDNS advertiser/listener using `zeroconf` or `pybonjour` (bonus).

Transport selection logic: Preferred from contact → available → policy (e.g., direct only if pinned key matches).

## Persistence & Offline Strategy

- Every outgoing message is immediately written to `outbox` + `messages` (pending).
- On successful send (ack or timeout policy), mark delivered.
- Background task: on any transport connected, drain outbox for that peer.
- History: on `chat.get_history`, query SQLite (optionally with full-text search via FTS5 later).
- On shutdown: graceful close streams, flush DB.

## Security Design

- **Transport**: Mandatory TLS 1.3 for XMPP server connections (slixmpp enforces). Certificate validation with TOFU or system CA + optional pinning per contact.
- **Direct P2P**: Strict public key / cert fingerprint check against address book entry. Reject on mismatch.
- **Local API**: Bind 127.0.0.1 only. Optional bearer token. All sensitive operations (add contact with creds) require confirmation in UI.
- **Credentials at rest**: Prefer `keyring` library (integrates with macOS Keychain, Windows Credential Manager, Linux Secret Service). Fallback to encrypted file with user passphrase (prompt on start).
- **Message content**: For v1, rely on TLS. Later: optional envelope encryption before sending (key derived from contact's pre-shared secret in address book).
- **Input handling**: Use `defusedxml` or slixmpp's safe parsers. Never eval or exec stanza content. Sanitize for display in UIs (escape HTML in web, strip control chars in TUI).
- **Logging**: Configurable redaction of JIDs/bodies in production logs. No PII leakage.

## Error Handling & Resilience

- Connection failures → UI notification + automatic retry schedule. User can force reconnect.
- Invalid address book entries → load with warnings, quarantine bad entries.
- Message send failure → keep in outbox, expose "pending / failed" status in UI, manual retry button.
- UI disconnect from service → TUI/web shows "service unavailable" banner, auto-reconnect attempts.
- Corrupt DB → backup on start, offer recovery or reset (with user confirmation).

## Implementation Phases & File Organization (High-Level)

```
src/xmpp_p2p_chat/
├── __init__.py
├── connection_service/
│   ├── __main__.py          # entrypoint to run service
│   ├── service.py           # main Service class, event loop, API server
│   ├── addressbook.py       # manager + schema (pydantic?)
│   ├── transports/
│   │   ├── base.py
│   │   ├── xmpp_server.py   # slixmpp wrapper
│   │   └── direct_p2p.py    # future
│   ├── session.py
│   ├── persistence.py
│   └── api.py               # WS + JSON-RPC handlers
├── text_ui/
│   ├── app.py               # Textual App subclass
│   ├── screens/             # contacts.py, chat.py, settings.py
│   └── widgets/
├── web_ui/                  # separate Vite project or src/web/
│   ├── src/
│   │   ├── App.svelte
│   │   ├── lib/api.ts       # WS client + RPC wrapper
│   │   └── components/
└── common/
    ├── models.py
    ├── config.py
    └── utils.py
```

Shared `pyproject.toml` with optional deps for `textual`, `websockets`, `slixmpp`, etc. Web UI as separate `web/` folder with its own `package.json`.

## Open Questions (to be resolved during implementation or first iteration)

1. Exact JSON-RPC method names and error codes — finalize in `api.py` with OpenAPI-like docs if possible.
2. How to handle multi-resource / resource binding in server mode (simple: use fixed resource or let slixmpp default).
3. Should address book support groups/folders visually in UIs? (Yes, via tags + virtual folders.)
4. Default data directory following XDG spec on Linux/macOS/Windows.
5. Whether to embed a minimal HTTP server in service to serve the web UI static files (convenience) or require separate `npm run dev`.

These will be clarified in tasks or early spikes.

This design keeps the core simple and testable while providing clear extension points for P2P and advanced features. It is optimized for rapid, high-quality implementation with AI assistance (Cursor) following the accompanying spec and tasks.