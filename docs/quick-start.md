# Quick Start

## Prerequisites

- Python 3.12+
- Node.js 18+ (required to build the Web UI on a fresh clone)
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

**Recommended** — generate a complete config with all current keys:

```bash
python -m xmpp_p2p_chat.connection_service --init-config
# writes ~/.config/xmpp-p2p-chat/config.toml
```

Or copy the annotated sample:

```bash
mkdir -p ~/.config/xmpp-p2p-chat
cp examples/config.sample.toml ~/.config/xmpp-p2p-chat/config.toml
```

### Address book (first run)

| Path | When to use |
|------|-------------|
| **Do nothing** (recommended) | Leave data dir empty — bundled contacts import automatically (`import_bundled_if_empty = true`) |
| Copy `examples/addressbook.sample.json` | Custom single-contact book; you must set P2P fingerprints yourself |
| Use P2P test harness | `./scripts/test-multi-client.sh init-p2p-alice` (see [p2p-serverless.md](./p2p-serverless.md)) |

### P2P fingerprint checklist

Direct P2P contacts **will not connect** until each peer trusts the other's certificate fingerprint:

1. Start the connection service once (generates certs in `{data_dir}/p2p/`).
2. Read your fingerprint: `connection.status` → `p2p_fingerprint`, or `./scripts/test-multi-client.sh p2p-fingerprints` in test harness.
3. Share fingerprints out-of-band with your peer.
4. Set `direct.public_key_fingerprint` on each contact in `addressbook.json`.
5. Restart the service (or press `r` in TUI / reload in Web UI).

Missing fingerprints appear as **warnings** in the address book status panel and `system.health`.

## Build Web UI (required on fresh clone)

`web_ui/dist/` is not committed. Build before starting the service:

```bash
cd web_ui && npm install && npm run build && cd ..
```

Without this step, the API still works but `http://127.0.0.1:8767/` will not load.

## Run

**Terminal 1 — Connection Service**

```bash
python -m xmpp_p2p_chat.connection_service
```

- API: `ws://127.0.0.1:8765/rpc`
- Embedded Web UI (after build): `http://127.0.0.1:8767/`

**Terminal 2 — Text TUI**

```bash
python -m xmpp_p2p_chat.text_ui
```

| Key | Action |
|-----|--------|
| `a` | Open **Address Book** — status, warnings, browse/add/remove contacts |
| `n` | Create new contact |
| `s` | Toggle contact sort (presence ↔ name) |
| `c` | Focus contact list |
| `/` | Focus message input |
| `r` | Refresh contacts |
| `?` | Show all shortcuts |

**Terminal 3 — Web UI dev mode (optional)**

```bash
cd web_ui && npm run dev
```

Open http://localhost:5173 for hot reload. Default API: `ws://127.0.0.1:8765/rpc`. For a second peer on port 8766:

```bash
VITE_API_URL=ws://127.0.0.1:8766/rpc npm run dev
```

## Optional: XMPP server mode

Set credentials in config and use server transport on contacts:

```toml
[xmpp]
jid = "alice@localhost"
password = "alice"
server = "localhost"
port = 5222
```

See [multi-client-testing.md](./multi-client-testing.md) for Docker Prosody setup.

## Optional: Address book sync

Trusted groups can push signed contact updates over XMPP server transport. See [addressbook-sync.md](./addressbook-sync.md).

## Multi-Client Testing

```bash
./scripts/test-multi-client.sh test-rpc       # API tests
./scripts/test-multi-client.sh test-p2p       # direct P2P unit tests
FRESH=1 ./scripts/test-multi-client.sh test-p2p-live  # live two-peer P2P messaging
./scripts/test-multi-client.sh setup          # Prosody + accounts
./scripts/test-multi-client.sh init-alice     # XMPP server two-user flow
```

Full guide: [multi-client-testing.md](./multi-client-testing.md) · P2P: [p2p-serverless.md](./p2p-serverless.md)

## Run Tests

```bash
pytest tests/ -v
cd web_ui && npm test
ruff check src tests
```
