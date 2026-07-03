# serverless-xmpp

**A privacy-first, serverless XMPP chat client with a decoupled connection service and multiple user interfaces (text TUI + modern web SPA).**

Uses pre-placed local address books to start peer-to-peer style chats (server-mediated XMPP for MVP, with architecture ready for direct P2P streams). Built for trusted circles who want control over their data and infrastructure.

> **Status**: MVP with **direct P2P (serverless) transport** — peers connect over TLS without a central XMPP server. XMPP server mode remains available as fallback.

## Key Features

- **Pre-placed Address Books** — Local JSON files (human-editable) define your contacts. No reliance on server rosters.
- **Decoupled Architecture** — Connection Service handles all XMPP logic, transports, sessions, and persistence. UIs are thin clients.
- **Multiple UIs**:
  - Keyboard-first **Text TUI** (Textual) — perfect for terminals, SSH, low-resource devices.
  - Modern **Web SPA** (Svelte + Vite + Tailwind) — rich chat experience, works in any browser.
- **Serverless Operation** — Zero hosted backend required. Connect to public/self-hosted XMPP servers or (future) direct P2P.
- **Offline Resilience** — Message queuing, local history (SQLite), automatic retry.
- **Privacy & Security** — Local data only, TLS enforced, localhost-only API, no telemetry.
- **Extensible** — Pluggable transports; easy to add direct P2P, E2EE, new UIs.

## Quick Start

```bash
git clone https://github.com/mowgli42/serverless-xmpp.git
cd serverless-xmpp

python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

mkdir -p ~/.config/xmpp-p2p-chat ~/.local/share/xmpp-p2p-chat
cp examples/config.sample.toml ~/.config/xmpp-p2p-chat/config.toml
cp examples/addressbook.sample.json ~/.local/share/xmpp-p2p-chat/addressbook.json
# Edit config.toml with your XMPP jid/password/server

# Terminal 1: Connection Service
python -m xmpp_p2p_chat.connection_service

# Terminal 2: Text TUI
python -m xmpp_p2p_chat.text_ui

# Terminal 3: Web UI (built into service at http://127.0.0.1:8767 after npm run build)
cd web_ui && npm install && npm run build
# Service auto-serves web_ui/dist when [ui] serve_web = true
```

Full details: [docs/quick-start.md](docs/quick-start.md) · **Serverless P2P**: [docs/p2p-serverless.md](docs/p2p-serverless.md)

## Serverless P2P (No XMPP Server)

The default transport is **direct peer-to-peer** — each client listens for inbound TLS connections and connects outbound to contacts listed in the address book:

```bash
cp examples/config.p2p-alice.toml ~/.config/xmpp-p2p-chat/config.toml
cp examples/addressbook.p2p-alice.json ~/.local/share/xmpp-p2p-chat/addressbook.json
# Share TLS fingerprints out-of-band, update addressbook direct.public_key_fingerprint

python -m xmpp_p2p_chat.connection_service
```

See [docs/p2p-serverless.md](docs/p2p-serverless.md) for the full two-peer setup.

## Multi-Client Testing

Test two users (alice ↔ bob) with a local Prosody server:

```bash
./scripts/test-multi-client.sh setup      # Start Docker Prosody + test accounts
./scripts/test-multi-client.sh init-alice # Write alice config
./scripts/test-multi-client.sh init-bob   # Write bob config
./scripts/test-multi-client.sh service-alice  # Terminal 1
./scripts/test-multi-client.sh service-bob    # Terminal 2
```

See [docs/multi-client-testing.md](docs/multi-client-testing.md).

## Architecture Overview

```
UIs (Text TUI / Web SPA)
        ↓ WebSocket + JSON-RPC
Connection Service (Python + slixmpp)
        ↓ Pluggable Transports
XMPP Servers  ←→  (Future) Direct P2P Peers
```

Full details in `openspec/changes/serverless-xmpp-p2p-chat-client/design.md`.

## Project Structure

```
serverless-xmpp/
├── src/xmpp_p2p_chat/
│   ├── connection_service/   # Core daemon, XMPP transport, WebSocket API
│   ├── text_ui/              # Textual TUI
│   └── common/               # Config, models, API client
├── web_ui/                   # Svelte 5 SPA
├── tests/                    # pytest unit + API integration tests
├── docker/                   # Prosody for local testing
├── scripts/                  # Multi-client test harness
├── examples/                 # Sample config + addressbook
└── openspec/                 # Spec-driven development artifacts
```

## Development

```bash
pytest tests/ -v
ruff check src tests
```

This project follows the [OpenSpec](https://github.com/Fission-AI/OpenSpec) workflow. See `AGENTS.md` and `openspec/changes/serverless-xmpp-p2p-chat-client/tasks.md`.

### Tech Stack

- **Python 3.12+** + `slixmpp`, `textual`, `websockets`, `aiosqlite`, `pydantic`
- **Web UI**: Vite + Svelte 5 + Tailwind CSS
- **API**: WebSocket + JSON-RPC 2.0 (localhost only)
- **Persistence**: SQLite + JSON/TOML

## Status & Roadmap

- [x] OpenSpec requirements & design
- [x] MVP: Connection Service + Address Book + Persistence + XMPP transport
- [x] MVP: WebSocket JSON-RPC API
- [x] MVP: Text TUI + Web SPA
- [x] Multi-client test harness (Docker Prosody + scripts)
- [x] MVP: Direct P2P transport (TLS + XMPP streams, mutual peer connections)
- [x] mDNS LAN discovery (zeroconf)
- [ ] Packaging & distribution
- [x] Embedded web UI server
- [ ] Per-chat E2EE (stretch)

## License

MIT License — see `LICENSE` file.

---

*Privacy-respecting communication for people who value control.*
