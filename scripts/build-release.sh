#!/usr/bin/env bash
# Build a distributable release: web UI + PyInstaller bundle with bundled address book.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Installing Python deps..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -e ".[dev,packaging]"

echo "==> Building web UI..."
(cd web_ui && npm install --silent && npm run build)

echo "==> Running tests..."
pytest tests/ -q

echo "==> Building PyInstaller bundle..."
pyinstaller packaging/xmpp-p2p-chat.spec --noconfirm --clean

echo ""
echo "Release artifacts:"
echo "  dist/xmpp-p2p-chat          — single-file launcher (service + bundled address book + web UI)"
echo "  src/xmpp_p2p_chat/share/addressbook.json — default contacts shipped in wheel"
echo ""
echo "Run: ./dist/xmpp-p2p-chat both"
