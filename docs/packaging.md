# Packaging & Distribution

Serverless XMPP ships as a Python package with an optional **PyInstaller** bundle that includes:

- Connection Service (WebSocket API + P2P transport)
- Bundled default `addressbook.json` (imported on first run if user data is empty)
- Built Web SPA (`web_ui/dist`) served at `http://127.0.0.1:8767/`
- Text TUI (`python -m xmpp_p2p_chat.text_ui`)

## Address book on startup

On every service start the Connection Service:

1. **Loads** `addressbook.json` and `addressbooks.d/*.json` from the configured data directory
2. **Imports** the bundled address book if the user book is empty (`[data] import_bundled_if_empty = true`)
3. **Computes** a canonical SHA256 content hash and tracks a monotonic **version**
4. **Persists** metadata to `.addressbook-meta.json` beside the address book

Both UIs display the current **version** and a **visual hash grid** (8×8 color fingerprint) so you can verify you are on the latest address book at a glance.

### API

```json
{"method":"addressbook.status"}
{"method":"addressbook.reload"}
```

`addressbook.list` also includes a `status` object with `version`, `content_hash`, and `hash_blocks`.

### Config

```toml
[data]
directory = "~/.local/share/xmpp-p2p-chat"
bundled_addressbook = ""
import_bundled_if_empty = true
```

Environment overrides:

- `XMPP_P2P_BUNDLED_ADDRESSBOOK` — path to seed contacts
- `XMPP_P2P_WEB_ROOT` — path to built web UI static files

## pip install (development)

```bash
pip install -e ".[dev]"
cd web_ui && npm install && npm run build
python -m xmpp_p2p_chat.connection_service
python -m xmpp_p2p_chat.text_ui
```

Bundled contacts live at `src/xmpp_p2p_chat/share/addressbook.json`.

## Release bundle (PyInstaller)

```bash
chmod +x scripts/build-release.sh
./scripts/build-release.sh
```

Produces `dist/xmpp-p2p-chat`:

```bash
./dist/xmpp-p2p-chat service   # API + embedded web UI only
./dist/xmpp-p2p-chat tui       # TUI only (service must be running)
./dist/xmpp-p2p-chat both      # start service then TUI
```

## Distributing a custom address book

1. Edit `src/xmpp_p2p_chat/share/addressbook.json` before building, **or**
2. Ship a separate `addressbook.json` and set `XMPP_P2P_BUNDLED_ADDRESSBOOK`, **or**
3. Point users at `~/.local/share/xmpp-p2p-chat/addressbook.json` after first run

Share the **content hash** (`addressbook.status` → `content_hash`) out-of-band so peers can confirm they imported the same contact list.

## TUI address book keys

| Key | Action |
|-----|--------|
| `a` | Open address book (status, hash grid, table) |
| `n` | New contact |
| `r` | Reload from disk |
| `delete` | Remove selected contact |
