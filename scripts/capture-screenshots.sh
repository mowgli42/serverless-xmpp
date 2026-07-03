#!/usr/bin/env bash
# Capture Text TUI and Web UI screenshots for documentation.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_ROOT="$ROOT/.screenshot-data"
CONFIG_HOME="$DATA_ROOT/config"
CONFIG_DIR="$CONFIG_HOME/xmpp-p2p-chat"
DATA_DIR="$DATA_ROOT/data"
OUT_DIR="$ROOT/docs/screenshots"
API_PORT=8765
WEB_PORT=8767
P2P_PORT=15299

# Release default doc ports if a previous capture left them bound
fuser -k "${API_PORT}/tcp" "${WEB_PORT}/tcp" "${P2P_PORT}/tcp" 2>/dev/null || true
sleep 0.5

mkdir -p "$CONFIG_DIR" "$OUT_DIR"

"$ROOT/.venv/bin/python" "$ROOT/scripts/seed-screenshot-data.py" "$DATA_DIR"

cat >"$CONFIG_DIR/config.toml" <<CFG
[data]
directory = "$DATA_DIR"

[connection]
default_transport = "direct-p2p"
api_host = "127.0.0.1"
api_port = $API_PORT

[p2p]
local_jid = "alice@p2p.local"
listen_host = "127.0.0.1"
listen_port = $P2P_PORT
mdns_enabled = false

[ui]
serve_web = true
web_host = "127.0.0.1"
web_port = $WEB_PORT

[security]
allow_self_signed_direct = true
CFG

echo "Building web UI..."
(cd "$ROOT/web_ui" && npm run build --silent)

SERVICE_PID=""
cleanup() {
  if [[ -n "${SERVICE_PID:-}" ]] && kill -0 "$SERVICE_PID" 2>/dev/null; then
    kill "$SERVICE_PID" 2>/dev/null || true
    wait "$SERVICE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

cd "$ROOT"
source .venv/bin/activate
XDG_CONFIG_HOME="$CONFIG_HOME" python -m xmpp_p2p_chat.connection_service &
SERVICE_PID=$!

echo "Waiting for connection service..."
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$WEB_PORT/" >/dev/null 2>&1; then
    if "$ROOT/.venv/bin/python" -c "import socket; s=socket.create_connection(('127.0.0.1',$API_PORT),1); s.close()" 2>/dev/null; then
      break
    fi
  fi
  sleep 0.5
done
sleep 1

export SCREENSHOT_DIR="$OUT_DIR"
export API_WS_URL="ws://127.0.0.1:$API_PORT/rpc"
"$ROOT/.venv/bin/python" "$ROOT/scripts/capture-tui-screenshot.py"

"$ROOT/.venv/bin/python" "$ROOT/scripts/capture-web-screenshot.py" \
  "http://127.0.0.1:$WEB_PORT/" "$OUT_DIR/web-ui.png"

echo "Screenshots saved to $OUT_DIR/"
ls -la "$OUT_DIR"/*.png
