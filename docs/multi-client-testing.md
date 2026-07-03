# Multi-Client Testing

This guide explains how to test serverless-xmpp with two (or more) clients talking to each other via a local XMPP server.

## Architecture for Testing

```
┌─────────────┐     ws://127.0.0.1:8765      ┌──────────────────┐
│ Alice TUI   │ ───────────────────────────► │ Alice Connection │
│ Alice Web   │                              │ Service          │
└─────────────┘                              └────────┬─────────┘
                                                      │ XMPP
                                                      ▼
                                              ┌───────────────┐
                                              │ Prosody       │
                                              │ localhost:5222│
                                              └───────┬───────┘
                                                      │ XMPP
                                                      ▼
┌─────────────┐     ws://127.0.0.1:8766      ┌──────────────────┐
│ Bob TUI     │ ───────────────────────────► │ Bob Connection   │
│ Bob Web     │                              │ Service          │
└─────────────┘                              └──────────────────┘
```

Each user runs their **own Connection Service** instance with separate config/data directories. Both connect to the same Prosody server. Messages route through XMPP server transport (MVP).

## Quick Start (Automated)

```bash
# 1. Install Python deps
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 2. Run unit + API tests
./scripts/test-multi-client.sh test-rpc

# 3. Start Prosody + test accounts, send a message via RPC
./scripts/test-multi-client.sh test-chat
```

## Manual Two-Client Test

### Terminal 1 — Start XMPP server

```bash
./scripts/test-multi-client.sh setup
```

Creates accounts `alice@localhost` / `alice` and `bob@localhost` / `bob`.

### Terminal 2 — Alice's service

```bash
./scripts/test-multi-client.sh init-alice
./scripts/test-multi-client.sh service-alice
```

### Terminal 3 — Bob's service

```bash
./scripts/test-multi-client.sh init-bob
./scripts/test-multi-client.sh service-bob
```

### Terminal 4 — Alice TUI

```bash
XDG_CONFIG_HOME=.test-data/alice/config .venv/bin/python -m xmpp_p2p_chat.text_ui
```

### Terminal 5 — Bob Web UI

```bash
cd web_ui && npm install && npm run dev
# Open http://localhost:5173 — default API ws://127.0.0.1:8765/rpc
# For Bob's service on port 8766:
VITE_API_URL=ws://127.0.0.1:8766/rpc npm run dev
```

### Verify sync on a single service

Run **both** TUI and Web UI against the **same** service (alice on port 8765):

1. Start alice service
2. Start TUI in one terminal
3. Start `npm run dev` in web_ui
4. Send from TUI → message appears in Web UI via push notification
5. Send from Web UI → message appears in TUI

This validates the spec scenario: *Text TUI and Web UI both attach and stay in sync*.

## Teardown

```bash
./scripts/test-multi-client.sh teardown
```

## Public XMPP Servers (Optional)

For testing without Docker, use a public test server (e.g. jabber.hot-chilli.net) and configure real JIDs in `config.toml` and `addressbook.json`. See `examples/` for sample files.
