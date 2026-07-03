# serverless-xmpp

**A privacy-first, serverless XMPP chat client with a decoupled connection service and multiple user interfaces (text TUI + modern web SPA).**

Uses pre-placed local address books to start peer-to-peer style chats (server-mediated XMPP for MVP, with architecture ready for direct P2P streams). Built for trusted circles who want control over their data and infrastructure.

> **Status**: Early development. OpenSpec-driven specification complete. Ready for implementation with Cursor or other AI coding assistants.

## Key Features (MVP Target)

- **Pre-placed Address Books** — Local JSON files (human-editable) define your contacts. No reliance on server rosters.
- **Decoupled Architecture** — Connection Service handles all XMPP logic, transports, sessions, and persistence. UIs are thin clients.
- **Multiple UIs**:
  - Keyboard-first **Text TUI** (Textual) — perfect for terminals, SSH, low-resource devices.
  - Modern **Web SPA** (Svelte + Vite + Tailwind) — rich chat experience, works in any browser.
- **Serverless Operation** — Zero hosted backend required. Connect to public/self-hosted XMPP servers or (future) direct P2P.
- **Offline Resilience** — Message queuing, local history (SQLite), automatic retry.
- **Privacy & Security** — Local data only, TLS 1.3 enforced, localhost-only API, no telemetry.
- **Extensible** — Pluggable transports; easy to add direct P2P, E2EE, new UIs.

## Quick Start (Once Implemented)

```bash
# 1. Clone
git clone https://github.com/mowgli42/serverless-xmpp.git
cd serverless-xmpp

# 2. Set up Python environment (uv or venv + pip)
uv sync   # or pip install -e ".[dev]"

# 3. Configure (copy samples)
cp examples/config.sample.toml ~/.config/xmpp-p2p-chat/config.toml
cp examples/addressbook.sample.json ~/.local/share/xmpp-p2p-chat/addressbook.json

# 4. Run the Connection Service (in one terminal)
python -m xmpp_p2p_chat.connection_service

# 5. Run the Text TUI (in another terminal)
python -m xmpp_p2p_chat.text_ui

# 6. Open the Web UI
# (served at http://localhost:8765/ui or run `npm run dev` in web_ui/)
```

See `docs/quick-start.md` (to be added) for detailed instructions and test XMPP account recommendations.

## Architecture Overview

```
UIs (Text TUI / Web SPA)
        ↓ WebSocket + JSON-RPC
Connection Service (Python + slixmpp)
        ↓ Pluggable Transports
XMPP Servers  ←→  (Future) Direct P2P Peers
```

Full details in `openspec/changes/serverless-xmpp-p2p-chat-client/design.md`.

**Core Principles**:
- Local-first & serverless
- Strict separation of concerns (service vs UI)
- Spec-driven development (OpenSpec)
- Pragmatic, secure, and maintainable

## Project Structure (Planned)

```
serverless-xmpp/
├── openspec/                          # Spec-driven development artifacts
│   └── changes/serverless-xmpp-p2p-chat-client/
│       ├── proposal.md
│       ├── design.md
│       ├── tasks.md
│       └── specs/spec.md
├── src/xmpp_p2p_chat/
│   ├── connection_service/            # Core daemon + API
│   ├── text_ui/                       # Textual TUI
│   └── common/
├── web_ui/                            # Svelte + Vite SPA
├── examples/
│   ├── addressbook.sample.json
│   └── config.sample.toml
├── docs/
├── pyproject.toml
├── README.md
└── AGENTS.md
```

## Development

This project is designed to be built with **Cursor** (or Claude/Codex) using the OpenSpec workflow.

1. Read the current spec: `openspec/changes/serverless-xmpp-p2p-chat-client/specs/spec.md`
2. Follow the checklist in `tasks.md`
3. Implement incrementally, validating against Given/When/Then scenarios.

See `AGENTS.md` for detailed instructions for AI coding assistants.

### Tech Stack (MVP)

- **Python 3.12+** + `slixmpp`, `textual`, `websockets`, `aiosqlite`
- **Web UI**: Vite + Svelte 5 + Tailwind + daisyUI
- **API**: WebSocket + JSON-RPC 2.0 (localhost only)
- **Persistence**: SQLite + JSON/TOML

## OpenSpec

This repository uses **[OpenSpec](https://github.com/Fission-AI/OpenSpec)** for spec-driven development.

All significant changes start with a proposal + detailed behavioral spec (requirements + scenarios) before any code is written. This keeps AI assistants (and humans) aligned and dramatically reduces rework.

Current active change: `serverless-xmpp-p2p-chat-client`

## Contributing

Contributions are welcome! Please:

1. Open an issue or discussion first for larger changes.
2. For code changes, create a new OpenSpec change folder or update an existing one.
3. Follow the coding standards in `AGENTS.md`.
4. Ensure new behavior is captured in specs with testable scenarios.

## License

MIT License — see `LICENSE` file.

## Acknowledgments

- Built with heavy inspiration from the XMPP ecosystem and XEP-0174 (Serverless Messaging).
- UI/UX guidance drawn from Interaction Design Foundation (IxDF) patterns for chat interfaces (clear feedback, presence visibility, efficient message composition, error prevention, etc.).

## Status & Roadmap

- [x] Thorough OpenSpec requirements & design (July 2026)
- [ ] MVP Implementation (Connection Service + Text TUI + Web UI)
- [ ] Direct P2P transport
- [ ] Packaging & distribution
- [ ] Polish, testing, documentation

**Want to help build it?** Star the repo, open an issue, or reach out.

---

*Privacy-respecting communication for people who value control.*