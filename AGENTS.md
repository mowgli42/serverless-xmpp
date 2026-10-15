# serverless-xmpp

Privacy-first serverless XMPP chat client: Connection Service (Python) + Text TUI + Svelte Web SPA. Direct P2P TLS default, optional XMPP server. Local data only.
Stack: Python 3.12+ (slixmpp, textual, websockets, aiosqlite, pydantic) + Svelte 5 / Vite / Tailwind. SQLite + JSON/TOML. Localhost WebSocket JSON-RPC.
Posture: ponytail (repo >30 days). Shared health pack in `.cursor/skills/` and `.cursor/rules/`.

## Commands

- Dev (service): `python -m xmpp_p2p_chat.connection_service` (serves API + http://127.0.0.1:8767/)
- Dev (TUI): `python -m xmpp_p2p_chat.text_ui`
- Init config: `python -m xmpp_p2p_chat.connection_service --init-config`
- Build Web UI: `cd web_ui && npm install && npm run build`
- Test: `pytest tests/ -v`
- Web test: `cd web_ui && npm test`
- Lint: `ruff check src tests`
- Demo / multi-client: `./scripts/test-multi-client.sh setup` then init-alice/init-bob + service-*
- Secrets: `bash scripts/scan-secrets.sh .`

## Hard prohibitions

- Do not commit private keys, `*-key.pem`, `*.key`, `.env` secrets, or `BEGIN … PRIVATE KEY`. Generate TLS locally; gitignore keys. Public certs OK.
- Do not bind the Connection Service API outside `127.0.0.1` by default. Do this instead: keep localhost-only; document any intentional change.
- Do not store credentials in plain text in address book JSON. Do this instead: use fingerprint pinning / configured secrets outside the book.
- Do not invent routes, env vars, or CLI flags not present in the tree or OpenSpec.
- Do not rewrite OpenSpec / Gherkin to match aspirational future. Update only after code already implements the change.

## Verify by change type

| Change | Check |
| --- | --- |
| Connection Service / transports / persistence | `pytest tests/` + relevant Gherkin in `features/` |
| Text TUI | Run `python -m xmpp_p2p_chat.text_ui`; confirm address book / chat flows |
| Web SPA | `cd web_ui && npm run build` then load via service at :8767 |
| Spec | Matching `.feature` + OpenSpec capability still true |
| Secrets / TLS | `bash scripts/scan-secrets.sh .` passes |

## Source of truth

- Behavior: `openspec/changes/serverless-xmpp-p2p-chat-client/specs/spec.md` + `features/*.feature`
- Remaining work: OpenSpec `tasks.md` + GitHub issues
- Demo evidence: README screenshots, `docs/p2p-serverless.md`, multi-client scripts
- Health bar: do not duplicate SUCCESS_CRITERIA here

## House vocabulary

- Connection Service — the local daemon that owns XMPP logic, transports, sessions, SQLite. UIs are thin clients.
- Address book — local JSON contacts with version + SHA256 hash + 8×8 fingerprint grid. Do not write "contact list" for the packaged file.
- Direct P2P — default serverless TLS stream transport. Do not write "serverless mode" when you mean the transport.
- Hash grid — visual 8×8 fingerprint shown while awaiting connection.

## Borrowed patterns

- hard-prohibition from apache/airflow via ossrules.md — clear never-do rules (localhost bind, no plain credentials)
- verification-matrix from apache/airflow via ossrules.md — change-type checks
- single-source from browser-use/browser-use via ossrules.md — point at OpenSpec + features
- house-vocabulary from apache/airflow via ossrules.md — Connection Service, address book, Direct P2P, hash grid
