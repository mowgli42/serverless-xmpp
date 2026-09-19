#!/usr/bin/env bash
# Multi-client local testing harness for serverless-xmpp
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATA_ROOT="${DATA_ROOT:-$ROOT/.test-data}"
COMPOSE_FILE="$ROOT/docker/docker-compose.yml"

config_home_for() {
  local name="$1"
  echo "$DATA_ROOT/$name/config"
}

config_path_for() {
  local name="$1"
  echo "$(config_home_for "$name")/xmpp-p2p-chat/config.toml"
}

usage() {
  cat <<EOF
Usage: $0 <command>

Prosody / XMPP server mode:
  setup           Start Prosody and create alice/bob test accounts
  teardown        Stop Prosody container
  init-alice      Write alice config (API :8765, talks to bob@localhost)
  init-bob        Write bob config (API :8766, talks to alice@localhost)
  service-alice   Run connection service as alice
  service-bob     Run connection service as bob
  test-chat       Start Prosody + alice service, send test message via RPC

Serverless P2P mode:
  init-p2p-alice  Write serverless P2P alice config (API :8765, listen :5223)
  init-p2p-bob    Write serverless P2P bob config (API :8766, listen :5224)
  service-p2p-alice  Run connection service as P2P alice
  service-p2p-bob    Run connection service as P2P bob
  p2p-fingerprints  Print TLS cert fingerprints (run after both services started once)
  test-p2p        Run direct P2P pytest suite
  test-p2p-live   Start both P2P services and run live bidirectional messaging test

General:
  test-rpc        Run API integration tests

Environment:
  DATA_ROOT   Base directory for test data (default: $DATA_ROOT)
  FRESH       Set to 1 for test-p2p-live to remove existing P2P test dirs first
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
  local config_path
  config_path="$(config_path_for "$name")"
  mkdir -p "$(dirname "$config_path")" "$dir/data"
  cat >"$config_path" <<CFG
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

cmd_init_p2p_alice() {
  local name="p2p-alice"
  local dir="$DATA_ROOT/$name"
  local config_path
  config_path="$(config_path_for "$name")"
  mkdir -p "$(dirname "$config_path")" "$dir/data"
  cp "$ROOT/examples/config.p2p-alice.toml" "$config_path"
  sed -i "s|~/.local/share/xmpp-p2p-alice|$dir/data|g" "$config_path"
  cp "$ROOT/examples/addressbook.p2p-alice.json" "$dir/data/addressbook.json"
  echo "P2P alice config: $dir"
}

cmd_init_p2p_bob() {
  local name="p2p-bob"
  local dir="$DATA_ROOT/$name"
  local config_path
  config_path="$(config_path_for "$name")"
  mkdir -p "$(dirname "$config_path")" "$dir/data"
  cp "$ROOT/examples/config.p2p-bob.toml" "$config_path"
  sed -i "s|~/.local/share/xmpp-p2p-bob|$dir/data|g" "$config_path"
  cp "$ROOT/examples/addressbook.p2p-bob.json" "$dir/data/addressbook.json"
  echo "P2P bob config: $dir"
}

cmd_p2p_fingerprints() {
  ensure_venv
  DATA_ROOT="$DATA_ROOT" "$ROOT/.venv/bin/python" <<PY
from pathlib import Path
import os
root = Path(os.environ["DATA_ROOT"])
for name in ("p2p-alice", "p2p-bob"):
    data = root / name / "data" / "p2p"
    if not data.exists():
        print(f"{name}: not initialized (run init-p2p-{name.split('-')[1]})")
        continue
    from xmpp_p2p_chat.common.certs import ensure_p2p_certificates
    _, _, fp = ensure_p2p_certificates(data, name.split("-")[1])
    print(f"{name}: {fp}")
PY
}

cmd_test_p2p() {
  ensure_venv
  cd "$ROOT"
  "$ROOT/.venv/bin/pytest" tests/test_direct_p2p.py -v
}

cmd_init_alice() { write_config alice 8765 bob; }
cmd_init_bob() { write_config bob 8766 alice; }

run_service() {
  local name="$1"
  ensure_venv
  export XDG_CONFIG_HOME="$(config_home_for "$name")"
  export XDG_DATA_HOME="$DATA_ROOT/$name/data"
  exec "$ROOT/.venv/bin/python" -m xmpp_p2p_chat.connection_service
}

run_p2p_service() {
  local name="$1"
  ensure_venv
  export XDG_CONFIG_HOME="$(config_home_for "$name")"
  export XDG_DATA_HOME="$DATA_ROOT/$name/data"
  exec "$ROOT/.venv/bin/python" -m xmpp_p2p_chat.connection_service
}

cmd_service_alice() { run_service alice; }
cmd_service_bob() { run_service bob; }
cmd_service_p2p_alice() { run_p2p_service p2p-alice; }
cmd_service_p2p_bob() { run_p2p_service p2p-bob; }

cmd_test_rpc() {
  ensure_venv
  cd "$ROOT"
  "$ROOT/.venv/bin/pytest" tests/test_api.py tests/test_addressbook.py tests/test_config.py -v
}

P2P_ALICE_PID=""
P2P_BOB_PID=""

cleanup_p2p_live() {
  [[ -n "$P2P_ALICE_PID" ]] && kill "$P2P_ALICE_PID" 2>/dev/null || true
  [[ -n "$P2P_BOB_PID" ]] && kill "$P2P_BOB_PID" 2>/dev/null || true
  wait "$P2P_ALICE_PID" 2>/dev/null || true
  wait "$P2P_BOB_PID" 2>/dev/null || true
}

cmd_test_p2p_live() {
  ensure_venv

  if [[ "${FRESH:-}" == "1" ]]; then
    rm -rf "$DATA_ROOT/p2p-alice" "$DATA_ROOT/p2p-bob"
  fi

  cmd_init_p2p_alice
  cmd_init_p2p_bob

  trap cleanup_p2p_live EXIT

  mkdir -p "$DATA_ROOT/p2p-alice" "$DATA_ROOT/p2p-bob"

  export XDG_CONFIG_HOME="$(config_home_for p2p-alice)"
  export XDG_DATA_HOME="$DATA_ROOT/p2p-alice/data"
  "$ROOT/.venv/bin/python" -m xmpp_p2p_chat.connection_service \
    >"$DATA_ROOT/p2p-alice/service.log" 2>&1 &
  P2P_ALICE_PID=$!

  export XDG_CONFIG_HOME="$(config_home_for p2p-bob)"
  export XDG_DATA_HOME="$DATA_ROOT/p2p-bob/data"
  "$ROOT/.venv/bin/python" -m xmpp_p2p_chat.connection_service \
    >"$DATA_ROOT/p2p-bob/service.log" 2>&1 &
  P2P_BOB_PID=$!

  sleep 3

  "$ROOT/.venv/bin/python" "$ROOT/scripts/test-p2p-live.py"
}

cmd_test_chat() {
  ensure_venv
  cmd_init_alice
  cmd_init_bob
  cmd_setup

  export XDG_CONFIG_HOME="$(config_home_for alice)"
  export XDG_DATA_HOME="$DATA_ROOT/alice/data"
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
  init-p2p-alice) cmd_init_p2p_alice ;;
  init-p2p-bob) cmd_init_p2p_bob ;;
  p2p-fingerprints) cmd_p2p_fingerprints ;;
  test-p2p) cmd_test_p2p ;;
  service-alice) cmd_service_alice ;;
  service-bob) cmd_service_bob ;;
  service-p2p-alice) cmd_service_p2p_alice ;;
  service-p2p-bob) cmd_service_p2p_bob ;;
  test-rpc) cmd_test_rpc ;;
  test-chat) cmd_test_chat ;;
  test-p2p-live) cmd_test_p2p_live ;;
  *) usage; exit 1 ;;
esac
