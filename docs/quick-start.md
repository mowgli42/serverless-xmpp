# Quick Start

## Prerequisites

- Python 3.12+
- Node.js 18+ (for web UI)
- Optional: Docker (for local Prosody XMPP server during multi-client testing)

## Install

```bash
git clone https://github.com/mowgli42/serverless-xmpp.git
cd serverless-xmpp

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure

```bash
mkdir -p ~/.config/xmpp-p2p-chat ~/.local/share/xmpp-p2p-chat
cp examples/config.sample.toml ~/.config/xmpp-p2p-chat/config.toml
cp examples/addressbook.sample.json ~/.local/share/xmpp-p2p-chat/addressbook.json
```

Edit `config.toml` for **serverless P2P** (default) or XMPP server fallback — see [p2p-serverless.md](./p2p-serverless.md).

## Run

**Terminal 1 — Connection Service**

```bash
cd web_ui && npm install && npm run build   # once, enables embedded UI
python -m xmpp_p2p_chat.connection_service
```

The API listens on `ws://127.0.0.1:8765/rpc`. If `web_ui/dist` exists, the SPA is also served at `http://127.0.0.1:8767/`.

**Terminal 2 — Text TUI**

```bash
python -m xmpp_p2p_chat.text_ui
```

| Key | Action |
|-----|--------|
| `a` | Open **Address Book** — status, warnings, browse/add/remove contacts |
| `n` | Create new contact (quick form) |
| `c` | Focus contact list |
| `/` | Focus message input |
| `r` | Refresh contacts |
| `?` | Show all shortcuts |

Inside the address book screen: `n` new · `delete` remove · `Enter` open chat · `r` refresh · `Esc` close.

**Terminal 3 — Web UI (dev mode alternative)**

```bash
cd web_ui && npm run dev
```

Open http://localhost:5173 for hot reload, or http://127.0.0.1:8767/ when using the embedded server.

## Multi-Client Testing

See [multi-client-testing.md](./multi-client-testing.md) for Docker Prosody setup and two-user test flows.

Quick automated check:

```bash
./scripts/test-multi-client.sh test-rpc
```

## Run Tests

```bash
pytest tests/ -v
ruff check src tests
```
