# Implementation Tasks: XMPP Resilience & Address Book Sync

**Change ID**: `enhance-xmpp-standards-resilience-addressbook-sync`  
**Issues**: #6, #7, #8, #9

Mark tasks `- [x]` only when implemented and tested.

---

## Phase 1: OpenSpec & Config

- [x] Replace duplicated MVP content in `proposal.md`, `design.md`, `specs/spec.md`, `tasks.md`
- [x] Add `[xmpp]` resilience keys and `[addressbook.sync]` to `common/config.py` + sample config
- [x] Extend `TransportStatus` and add sync models in `common/models.py`

---

## Phase 2: XEP-0198 Stream Management (#6)

- [x] Add `connection_service/xmpp/sm_state.py` — load/save `.xmpp-sm-state.json`
- [x] Register slixmpp `xep_0198` in `XMPPClient` with restored config
- [x] Hook `sm_enabled`, `session_resumed`, `sm_failed`, `disconnected` to persist/clear state
- [x] Include `stream_management` summary in `connection.status` API response
- [x] Unit tests: SM state round-trip, JID mismatch ignores stale state

---

## Phase 3: XEP-0199 Ping & Errors (#8)

- [x] Add `connection_service/xmpp/errors.py` — `parse_xmpp_error()`, `XmppErrorInfo`
- [x] Implement ping keepalive loop in `XMPPServerTransport`
- [x] Populate `error_condition`, `error_type` on `TransportStatus` from caught exceptions
- [x] Unit tests: error parsing for common conditions

---

## Phase 4: Address Book Sync (#7)

- [x] Add `connection_service/addressbook_sync.py` — sign, verify, canonical payload
- [x] Add `addressbook_sync_pending` table to persistence
- [x] Register IQ handler on `XMPPClient` for `urn:serverless-xmpp:addressbook:1`
- [x] Wire `SessionManager` to route inbound sync IQs → pending/auto-apply
- [x] Implement RPC: `sync_status`, `enable_sync`, `sync_now`, `get_pending_updates`, `apply_pending_update`, `reject_pending_update`
- [x] Emit `addressbook.sync_pending` push event
- [x] Unit tests: sign/verify, untrusted JID rejection, timestamp skew, pending apply/reject

---

## Phase 5: Documentation & Validation

- [x] Update `docs/api.md` with new methods and `connection.status` fields
- [x] Update `docs/architecture.md` XEP compliance table (0198, 0199, sync)
- [x] Run `pytest tests/ -v` and `ruff check src tests`

---

## Phase 6: Closeout

- [ ] Merge to `main`, reference issues #6–#9 in commit message
- [ ] Comment on tracking issue #9 with summary

---

## Implementation notes

- slixmpp plugins: `xep_0198`, `xep_0199`, `xep_0030` (already registered)
- SM state must be saved **before** slixmpp `session_end` clears `sm_id`
- Sync secret MUST NOT be logged; reject empty secret when `sync.enabled = true`
- Direct P2P transport: no changes in this change
