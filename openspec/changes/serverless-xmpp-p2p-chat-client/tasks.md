# Implementation Tasks: Serverless XMPP P2P Chat Client

**Instructions for Cursor / AI Assistant**:
- Follow this checklist in order. Mark tasks complete (`- [x]`) only after the code is written, basic tests pass (where applicable), and the behavior matches the corresponding requirement/scenario in `specs/spec.md`.
- Before starting a major component, re-read the relevant section of `proposal.md`, `design.md`, and `specs/spec.md`.
- Prefer small, incremental commits or file edits. After each logical group of tasks, run `ruff check`, `pyright` or `mypy` (if configured), and manual smoke test of the service + at least one UI.
- If a task reveals ambiguity in the spec, pause and propose a clarification or update to the spec first (do not guess).
- MVP scope is strictly limited to server-mode XMPP + local address book + decoupled API + both UIs. Direct P2P transport is explicitly Phase 2 (do not implement unless all MVP tasks are complete and validated).

## Phase 0: Project Setup & Tooling (Do First)

- [x] Create project root with `pyproject.toml` (Python 3.12+, hatchling or setuptools, dependencies for slixmpp, textual, websockets, aiosqlite, tomli, keyring, pydantic for models optional but recommended).
- [x] Set up standard src layout: `src/xmpp_p2p_chat/`, `tests/`, `README.md`, `LICENSE` (MIT recommended).
- [x] Configure `ruff` (lint + format), `pyright` or `mypy`, and a basic `pytest` setup with asyncio support.
- [x] Create `.gitignore` (ignore venv, __pycache__, .env, logs/, data/ for user data, node_modules for web_ui).
- [x] Initialize git repo and make initial commit with this OpenSpec change folder copied in (or reference it).
- [x] Create `src/xmpp_p2p_chat/common/config.py` that loads TOML from XDG-compliant paths or `~/.config/xmpp-p2p-chat/config.toml` (or data dir) with sensible defaults matching design.md.
- [x] Create `src/xmpp_p2p_chat/common/models.py` with Pydantic (or dataclass + validation) models for `Contact`, `Message`, `ChatSession`, `AddressBook`.
- [x] Write a small smoke test that loads config and validates a sample Contact.

## Phase 1: Connection Service Core – Address Book & Persistence

- [x] Implement `AddressBookManager` in `connection_service/addressbook.py`:
  - Load from `addressbook.json` + `addressbooks.d/*.json`.
  - Merge logic with clear conflict handling.
  - `list()`, `get(id)`, `add(contact)`, `update(id, partial)`, `remove(id)` methods.
  - Atomic write (temp file + rename) on any mutation.
  - Validation of JID format (use `xmpp` or simple regex + domain validation).
- [x] Implement `PersistenceManager` (or module) using `aiosqlite`:
  - Initialize DB schema on first run (messages, chats, outbox, presence tables).
  - Methods: `save_message()`, `get_history(chat_id, limit, before)`, `queue_outbound()`, `mark_delivered(message_id)`, `get_pending_outbox(contact_id)`.
  - Migration support or simple "if table missing create".
- [x] Add unit tests for AddressBookManager (load, add, update, malformed handling) and basic Persistence (CRUD messages).
- [x] Wire both managers into a central `Service` class that owns the asyncio event loop.

## Phase 2: Connection Service – XMPP Server Transport (MVP)

- [x] Create `transports/base.py` defining abstract `BaseTransport` protocol/interface with methods: `connect(jid, credentials)`, `disconnect()`, `send_message(to_jid, body, message_id?)`, `set_presence(show, status)`, and event callback registration (`on_message`, `on_presence`, `on_disconnect`).
- [x] Implement `XMPPServerTransport` in `transports/xmpp_server.py`:
  - Wrap `slixmpp.ClientXMPP`.
  - Handle connection, authentication, resource binding, initial presence.
  - Register handlers for `<message type="chat">` and presence stanzas.
  - Normalize incoming stanzas to internal `Message` / presence models.
  - Implement auto-reconnect with backoff inside the transport or in SessionManager.
  - Enforce TLS and surface certificate validation results.
- [x] Create `SessionManager` that:
  - Maps `chat_id` ↔ active transport + remote JID.
  - On `start_chat(contact)` selects appropriate transport (server for MVP), calls connect if needed, returns chat metadata.
  - Routes `send_message` to the correct transport.
  - Listens to transport events, persists messages, pushes notifications via API layer, manages outbox drain.
- [x] Test the transport in isolation (mock slixmpp or use a local test XMPP server like Prosody in Docker for integration tests – document how).
- [x] Ensure all external I/O (XMPP) happens only through this transport layer.

## Phase 3: Connection Service – API Layer (WebSocket + JSON-RPC)

- [x] Implement WebSocket server using `websockets` library (or `aiohttp` if preferred) in `api.py` or `service.py`.
  - Bind to `config.api_host:api_port` (default 127.0.0.1:8765).
  - Simple JSON-RPC 2.0 dispatcher: parse incoming messages, route to handler methods, return responses or errors.
  - Support server-initiated push (notifications) to all connected clients or per-subscription.
- [x] Define and implement core RPC methods matching spec scenarios:
  - `addressbook.*` (list, add, update, remove)
  - `chat.start`, `chat.send_message`, `chat.get_history`
  - `presence.set`, `connection.status`, `system.health`, `system.shutdown`
  - Auth handshake if `api_token` configured.
- [x] Implement push events: `message.received`, `message.updated`, `presence.updated`, `addressbook.updated`, `connection.changed`.
- [x] Add connection lifecycle management (on client connect/disconnect, track active clients, clean up on close).
- [x] Write a simple Python test client (or use `wscat` / browser console) that exercises the full RPC surface and verifies push notifications.
- [x] Document the API (even if just in a `docs/api.md` or docstring) with example request/response JSON.

## Phase 4: Text-Based UI (TUI) with Textual

- [x] Create `text_ui/app.py` as the main `App` subclass from `textual.app`.
  - Compose main layout: header (service status, presence), sidebar or tab for contacts, main chat area (or multiple docked panes), footer (input or commands).
  - Use `textual.widgets`, `Header`, `Footer`, `DataTable` or custom `ContactList`, `ChatLog` (virtualized list or Rich renderables), `Input`.
- [x] Implement `APIClient` helper in TUI (or shared `common/`) that wraps WebSocket + JSON-RPC calls with async/await, auto-reconnect, and event subscription (simple pubsub or callback registry).
- [x] Build Contacts screen/widget:
  - Reactive list populated from `addressbook.list`.
  - Search/filter input.
  - Display name, JID, tags, presence dot, unread count.
  - Keyboard navigation and "open chat" action.
- [x] Build Chat screen/pane:
  - Load history on open via `chat.get_history`.
  - Render messages with direction styling, timestamps, status.
  - Composer `Input` that calls `chat.send_message` on submit (optimistic update + server confirmation).
  - Live append of pushed `message.received` events.
  - Auto-scroll logic (only if user is at bottom).
- [x] Add global keybindings (quit, help `?`, switch chats, toggle sidebar).
- [x] Theming: support Textual CSS or built-in themes; make it pleasant in light/dark terminal.
- [x] Handle service disconnect gracefully (banner + retry button or auto).
- [ ] Smoke test: run service in one terminal, TUI in another, add contact, start chat, exchange messages (use a real or test XMPP account).

## Phase 5: Web UI (Svelte SPA)

- [x] Create `web_ui/` as a Vite + Svelte 5 project (`npm create vite@latest web_ui -- --template svelte` or SvelteKit if preferred for future SSR but static is fine).
  - Install `tailwindcss`, `daisyui` (or shadcn-svelte), `svelte-preprocess`.
  - Set up `src/lib/api.ts`: WebSocket client class that handles JSON-RPC requests, responses, and subscriptions (EventTarget or Svelte stores for reactive state).
- [x] Main layout (`App.svelte` or `+layout`): sidebar (contacts), main chat pane, top nav (status, settings button).
- [x] `ContactList.svelte`: searchable list, presence indicators (colored dot + status text), unread badges, click to open chat. Use Svelte 5 runes or stores fed by API pushes.
- [x] `ChatPane.svelte`:
  - Virtual or simple message list (for MVP 50–100 messages is fine; use `{#each}` + auto-scroll div).
  - Different styling for in/out messages (bubbles).
  - Composer with send button + keyboard support.
  - Optimistic messages + live updates from push events.
  - Show connection status and transport info.
- [x] Settings / Service modal or page: form to add/edit contact, manual reconnect buttons, basic health display, presence setter.
- [x] Make it responsive (mobile-friendly sidebar collapse) and accessible (ARIA, keyboard nav, high contrast).
- [x] Build step: `npm run build` produces static assets that can be served by any HTTP server or (future) embedded in the Python service.
- [ ] Test in browser: connect to running service, full happy-path chat flow, multiple tabs/windows staying in sync via pushes.

## Phase 6: Integration, Polish, Security & Documentation

- [x] End-to-end happy path test (manual or scripted): 
  1. Start service.
  2. Add 2–3 contacts via TUI or Web UI (use real test JIDs or public XMPP test accounts like `user@jabber.hot-chilli.net` or local Prosody).
  3. Start chat from TUI, send message.
  4. Receive in Web UI (and vice versa).
  5. Disconnect network or stop XMPP server → verify queuing.
  6. Reconnect → verify delivery and history.
- [x] Implement basic error handling and user-facing messages for common failures (auth fail, network error, invalid JID, service unreachable).
- [x] Security pass:
  - Verify localhost-only binding.
  - Add TODO comments or config for keyring integration (implement simple version if time).
  - Ensure no plaintext passwords in logs or address book JSON.
  - Add input sanitization notes or helpers for message bodies (though XMPP libs handle most).
- [x] Logging: structured or simple with levels; redact sensitive fields in production mode.
- [x] Update `README.md` with:
  - Quick start (install deps, run service, run TUI, open web UI).
  - Example minimal `addressbook.json` and `config.toml`.
  - How to point at a local Prosody or public XMPP server for testing.
  - Architecture diagram (ASCII or link to design.md).
  - Contribution / spec update process (OpenSpec reminder).
- [x] Add `docs/` or inline docs for API, data directory layout, and future direct P2P extension points.
- [x] Create a sample `examples/addressbook.sample.json` and `examples/config.sample.toml`.
- [x] Final lint/format pass across all Python and frontend code.
- [x] Optional but recommended: simple `pytest` integration test that spins up service in background thread/process and exercises API with a mock or real XMPP connection (mark as slow/integration).

## Phase 7: Validation Against Specification & Closeout

- [x] For every major Requirement in `specs/spec.md`, manually or via test verify at least the primary "happy path" scenario works end-to-end.
- [x] Confirm non-functional requirements are met at MVP level (resource usage, localhost binding, no telemetry).
- [x] Update `proposal.md` or `design.md` with any deviations or lessons learned during implementation (keep spec as source of truth).
- [ ] Mark all tasks complete in this file.
- [ ] Run full smoke test one more time after any final polish.
- [ ] Prepare for `/opsx:archive` or next change (e.g., "implement-direct-p2p-transport").

## Stretch Goals / Post-MVP (Only After All Above Are Complete and Validated)

- [x] Implement `DirectP2PTransport` skeleton (socket + TLS + basic XML stream open/close, stanza send/receive). Do not wire into SessionManager until MVP is solid.
- [x] Add optional mDNS discovery using `zeroconf` for local peers (XEP-0174 inspiration).
- [ ] Simple per-chat message encryption helper (AES-GCM with key from address book entry) – behind a feature flag.
- [ ] File attachment support (base64 or HTTP upload + direct).
- [ ] Packaging script / PyInstaller spec for a single executable containing service + TUI.
- [x] Embed a tiny HTTP server in the Python service to serve the built `web_ui/dist/` assets on the same port or `/ui` path for one-command launch experience.

**Completion Criteria**: When every checkbox in Phases 0–6 is marked and the end-to-end flow works reliably for server-mediated XMPP chats using pre-placed address book entries from both UIs, with clean separation of concerns, this change is ready to be archived. The resulting codebase will be a solid foundation for privacy-respecting, local-first, multi-UI XMPP chat tooling.

**Cursor Tip**: Use the structured scenarios in `specs/spec.md` as acceptance criteria. When a task is done, mentally (or actually) run through the relevant Given/When/Then steps with the built software. If behavior diverges, update the spec or the code — keep them in sync.
