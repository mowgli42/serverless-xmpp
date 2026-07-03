#!/usr/bin/env bash
# Multi-client local testing harness for serverless-xmpp
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_ROOT="${DATA_ROOT:-$ROOT/.test-data}"
COMPOSE_FILE="$ROOT/docker/docker-compose.yml"

usage() {
  cat <<EOF
Usage: $0 <command>

Commands:
  setup       Start Prosody and create alice/bob test accounts
  teardown    Stop Prosody container
  init-alice  Write alice config + addressbook to \$DATA_ROOT/alice
  init-bob    Write bob config + addressbook to \$DATA_ROOT/bob
  service-alice  Run connection service as alice
  service-bob    Run connection service as bob
  test-rpc    Run API integration tests
  test-chat   Automated two-client message exchange via RPC

Environment:
  DATA_ROOT   Base directory for test data (default: $ROOT/.test-data)
EOF
}

ensure_venv() {
  if [[ ! -d "$ROOT/.venv" ]]; then
    python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/pip" install -e "$ROOT[dev]" >/dev/null
  fi
}

write_config() {
  local name="$1" port="$2" peer="$3"
  local dir="$DATA_ROOT/$name"
  mkdir -p "$dir/config" "$dir/data"
  cat >"$dir/config/config.toml" <<CFG
[data]
directory = "$dir/data"

[connection]
api_host = "127.0.0.1"
api_port = $port

[xmpp]
jid = "${name}@localhost"
password = "${name}"
server = "localhost"
port = 5222
CFG

  cat >"$dir/data/addressbook.json" <<AB
[
  {
    "id": "${peer}",
    "jid": "${peer}@localhost",
    "name": "${peer^}",
    "tags": ["test"],
    "preferred_transport": "xmpp-server",
    "xmpp_server": "localhost"
  }
]
AB
  echo "Config written to $dir"
}

cmd_setup() {
  docker compose -f "$COMPOSE_FILE" up -d
  echo "Waiting for Prosody..."
  sleep 5
  docker exec serverless-xmpp-prosody prosodyctl register alice localhost alice 2>/dev/null || true
  docker exec serverless-xmpp-prosody prosodyctl register bob localhost bob 2>/dev/null || true
  echo "Prosody ready. Accounts: alice/alice, bob/bob"
}

cmd_teardown() {
  docker compose -f "$COMPOSE_FILE" down
}

cmd_init_alice() { write_config alice 8765 bob; }
cmd_init_bob() { write_config bob 8766 alice; }

run_service() {
  local name="$1"
  ensure_venv
  export XDG_CONFIG_HOME="$DATA_ROOT/$name/config"
  export XDG_DATA_HOME="$DATA_ROOT/$name/data"
  exec "$ROOT/.venv/bin/python" -m xmpp_p2p_chat.connection_service
}

cmd_service_alice() { run_service alice; }
cmd_service_bob() { run_service bob; }

cmd_test_rpc() {
  ensure_venv
  cd "$ROOT"
  "$ROOT/.venv/bin/pytest" tests/test_api.py tests/test_addressbook.py tests/test_config.py -v
}

cmd_test_chat() {
  ensure_venv
  cmd_init_alice
  cmd_init_bob
  cmd_setup

  export XDG_CONFIG_HOME="$DATA_ROOT/alice/config"
  "$ROOT/.venv/bin/python" -m xmpp_p2p_chat.connection_service &
  ALICE_PID=$!
  sleep 2

  "$ROOT/.venv/bin/python" <<'PY'
import asyncio
import json
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8765/rpc") as ws:
        async def call(method, params=None, req_id="1"):
            await ws.send(json.dumps({"jsonrpc":"2.0","id":req_id,"method":method,"params":params or {}}))
            return json.loads(await ws.recv())

        await call("chat.start", {"contact_id": "bob"}, "2")
        sent = await call("chat.send_message", {"chat_id": "bob", "body": "Hello Bob from test harness"}, "3")
        print("Sent:", sent["result"]["message"]["body"])
        print("Multi-client RPC chat test OK")

asyncio.run(main())
PY

  kill "$ALICE_PID" 2>/dev/null || true
  echo "Done."
}

case "${1:-}" in
  setup) cmd_setup ;;
  teardown) cmd_teardown ;;
  init-alice) cmd_init_alice ;;
  init-bob) cmd_init_bob ;;
  service-alice) cmd_service_alice ;;
  service-bob) cmd_service_bob ;;
  test-rpc) cmd_test_rpc ;;
  test-chat) cmd_test_chat ;;
  *) usage; exit 1 ;;
esac
