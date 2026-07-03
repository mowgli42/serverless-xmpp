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

Edit `config.toml` and set your XMPP credentials:

```toml
[xmpp]
jid = "you@your-server.example"
password = "your-password"
server = "your-server.example"
port = 5222
```

## Run

**Terminal 1 — Connection Service**

```bash
python -m xmpp_p2p_chat.connection_service
```

The API listens on `ws://127.0.0.1:8765/rpc` (localhost only).

**Terminal 2 — Text TUI**

```bash
python -m xmpp_p2p_chat.text_ui
```

**Terminal 3 — Web UI**

```bash
cd web_ui
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

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
