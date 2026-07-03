# Proposal: Serverless XMPP P2P Chat Client with Decoupled Connection Service and Multiple UIs

**Change ID**: serverless-xmpp-p2p-chat-client  
**Created**: 2026-07-02  
**Status**: Proposed for implementation with Cursor / OpenSpec workflow

## Why This Change?

Current instant messaging options force users into centralized platforms (Signal, WhatsApp, Discord, Slack) or require running/maintaining full XMPP servers with dynamic rosters. For small, trusted groups (family, close friends, professional circles), a simpler model is desirable:

- **Preplaced address books**: Contacts are explicitly defined locally in files (JSON/YAML). No reliance on server-side contact discovery or roster synchronization as the source of truth.
- **Serverless operation**: The chat application itself requires zero hosted infrastructure. Users can communicate via:
  - Chosen public or self-hosted XMPP servers (using standard client-server XMPP).
  - Direct peer-to-peer XML streams (inspired by XEP-0174 Serverless Messaging and direct TCP/TLS connections) when peers provide connection hints in the address book.
- **Decoupled architecture**: The "connection service" (XMPP protocol handling, transport negotiation, session state, persistence) is completely separate from any user interface. This allows independent development and use of:
  - A lightweight **text-based / TUI client** (ideal for terminals, SSH sessions, low-resource devices, quick scripting).
  - A **web-based client** (rich UI, theming, multi-window, accessible from browser on LAN or via reverse proxy/VPN).
  - Future UIs (desktop GUI, mobile webview, voice assistant integration) without code duplication.

This design promotes extreme ownership, privacy (local data only, no telemetry), and pragmatism: start simple with server-mediated XMPP + local contacts, then layer direct P2P transports.

## What We Are Building

A complete, self-contained chat system consisting of:

1. **Connection Service** (core): Python (slixmpp + asyncio) daemon/process exposing a local WebSocket + JSON-RPC API. Handles address book, multiple transports (XMPP server + direct P2P), message routing, presence, offline queuing, local persistence (SQLite).
2. **Text-based UI**: Modern TUI built with Textual framework. Keyboard-first, splits or tabs for contacts + active chats, real-time updates.
3. **Web UI**: Lightweight SPA (Vite + Svelte + Tailwind) that connects to the same local WS API. Sidebar contacts, chat bubbles, settings modal.

All components run locally on the user's machine. No cloud components unless the user explicitly configures an XMPP server or STUN relay.

## Scope

### In Scope for MVP (v0.1 - usable chat)
- Local address book (single primary JSON file + support for additional files/directories).
- CRUD operations on contacts via API (and thus via UIs).
- Connection to XMPP servers using JIDs from address book (SRV lookup or explicit server, TLS mandatory, credentials stored securely or prompted).
- Basic 1:1 messaging: send/receive `<message type="chat">` stanzas, plain text body, timestamps.
- Local message history persistence and retrieval.
- Offline message queuing and automatic retry on reconnect.
- Simple presence (online/away) broadcast and display for connected contacts.
- Connection Service with stable local WebSocket API (JSON-RPC 2.0 style for requests + server-push notifications for events).
- Text TUI: list/search contacts, open chat, send/receive, basic commands, theming.
- Web UI: equivalent core functionality + nicer visuals (bubbles, unread indicators, responsive).
- Configuration via TOML (data dir, log level, default transport preference, API bind address/port).
- Security baseline: TLS 1.3 enforced for all XMPP connections, local API bound to 127.0.0.1, input sanitization, no external network calls except user-initiated XMPP/direct.

### Stretch / Phase 2 (after MVP validated)
- Direct P2P transport implementation (custom asyncio TLS XML stream handler + minimal XMPP core for direct client-client streams; support pre-placed host:port + public key pinning or PSK).
- Optional mDNS/DNS-SD advertisement and discovery (XEP-0174 style) for local network peers.
- Basic E2EE for messages (e.g., per-chat AES-GCM with key from address book entry or libsodium).
- File transfer (Jingle or simple HTTP upload + direct).
- Multiple simultaneous accounts/connections.
- Typing indicators, read receipts (XEP-0184), message correction (XEP-0308).
- Theming engine shared or per-UI.
- Packaging: single-binary distribution for service + TUI, static web assets served optionally by service.

### Explicitly Out of Scope (v1)
- Multi-User Chat (MUC / XEP-0045) rooms.
- Voice, video, or screen sharing (Jingle media sessions).
- OMEMO or full XEP-0384 E2EE (too complex for initial; transport security is primary).
- Public/untrusted peer discovery or federation beyond explicit address book entries.
- Mobile native apps or push notifications.
- Any telemetry, analytics, or "phone home" behavior.
- Production-grade high availability or clustering (single-user local tool).

## Success Criteria

- A user can create/edit an address book entry with a JID (e.g., `friend@jabber.example.com`), optional display name, and notes.
- From either the TUI or Web UI, select the contact, initiate a chat, and exchange real-time messages successfully over a standard XMPP server connection.
- The Connection Service can run standalone (headless) while one or both UIs attach/detach dynamically; all UIs stay in sync via push events.
- All data (address book, chat history, config) remains in a user-controlled local directory with no external dependencies beyond optional XMPP servers chosen by the user.
- Cursor (or equivalent AI assistant) can implement the full MVP by following the `tasks.md` checklist and referencing this spec + design without major deviations or hallucinations.
- The system feels responsive (<200ms perceived latency for local messages) and stable on reconnects/offline scenarios.

## Risks & Mitigations

- **Direct P2P complexity / NAT traversal**: Mitigated by making server-mode the primary MVP path; direct P2P is designed as a pluggable transport with clear interface. Use STUN/TURN only if added later as optional.
- **XMPP library learning curve / stanza handling**: Use mature `slixmpp` (well-documented, asyncio-native). Start with high-level client API before custom low-level streams.
- **State synchronization between UIs**: Solved by single source of truth in Connection Service + event-driven push model (no polling).
- **Security of pre-placed keys / credentials**: Store sensitive fields (passwords, private keys) in OS keyring where possible (keyring lib) or encrypted at rest with user passphrase; document clearly.
- **Scope creep**: Strict MVP definition + phased tasks. Any new feature must update this proposal/spec first.

## Next Steps (OpenSpec Workflow)

1. Review and refine this proposal + design + spec with human feedback.
2. Cursor runs implementation via `/opsx:apply` or step-by-step following `tasks.md`.
3. Validate against scenarios in `specs/spec.md`.
4. Archive upon completion.

This change establishes the foundational architecture for a long-lived, extensible personal communication tool aligned with pragmatic, local-first, and privacy-respecting principles.
