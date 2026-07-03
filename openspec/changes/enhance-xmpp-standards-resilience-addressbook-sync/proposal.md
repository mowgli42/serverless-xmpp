# Proposal: XMPP Standards, Resilience & Address Book Sync

**Change ID**: `enhance-xmpp-standards-resilience-addressbook-sync`  
**Created**: 2026-07-03  
**Status**: In progress  
**Tracking issue**: [#9](https://github.com/mowgli42/serverless-xmpp/issues/9)

## Why This Change?

The MVP ships working XMPP server-mode and direct P2P transports, but real-world use exposes gaps:

1. **Connection fragility** — WiFi handoffs, laptop sleep, and flaky servers drop streams without stanza recovery. Users lose in-flight messages and see generic errors.
2. **Dead connection detection** — Without periodic keepalives, a half-open TCP session can appear “connected” indefinitely.
3. **Opaque failures** — XMPP `<error>` stanzas are logged but not surfaced to UIs as actionable conditions.
4. **Static address books** — Pre-placed JSON works for bootstrap, but trusted groups need a secure way to propagate contact updates without manual file sharing.

This change hardens the **XMPP server transport** (slixmpp) and adds **signed address book sync** between already-trusted peers. Direct P2P transport is unchanged in this phase.

## What We Are Building

| Workstream | GitHub issue | Summary |
|------------|--------------|---------|
| Stream Management | [#6](https://github.com/mowgli42/serverless-xmpp/issues/6) | XEP-0198 enable/resume, unacked stanza queue, persisted SM state |
| Ping + errors | [#8](https://github.com/mowgli42/serverless-xmpp/issues/8) | XEP-0199 periodic ping, dead-connection detection, structured errors |
| Address book sync | [#7](https://github.com/mowgli42/serverless-xmpp/issues/7) | Signed updates over `urn:serverless-xmpp:addressbook:1` |
| Tracking | [#9](https://github.com/mowgli42/serverless-xmpp/issues/9) | Meta issue for the OpenSpec change |

## Scope

### In scope

- XEP-0198 on `XMPPServerTransport` via slixmpp `xep_0198` plugin (auto-negotiate after bind)
- Persist `sm_id`, `handled`, `last_ack` to `{data_dir}/.xmpp-sm-state.json`; restore on reconnect
- XEP-0199 ping loop (default 90s interval, configurable); failed ping → reconnect
- Parse XMPP error conditions into `TransportStatus` (`error_condition`, `error_type`, `error_text`)
- Address book sync protocol, HMAC signing, pending-update queue, API + session wiring
- Unit tests for SM state, error parsing, sync sign/verify, and transport helpers
- Config keys under `[xmpp]` and `[addressbook.sync]`

### Out of scope

- XEP-0198 on direct P2P XML streams (no resource binding / SM negotiation today)
- OMEMO, MUC, MAM, carbons
- Untrusted peer discovery or roster import from server
- Full CRDT / merge conflict resolution (timestamp + pending review only)

## Success Criteria

- When Prosody (or any SM-capable server) is used, client enables XEP-0198 and resumes after brief disconnect when possible
- Unacknowledged outbound stanzas are resent after resume (slixmpp plugin behavior + persisted state)
- Dead XMPP connections detected within ~2 minutes via ping timeout
- `connection.status` exposes structured XMPP error info when transport is in `error` state
- Trusted peers can push signed contact add/update/remove; receiver verifies sender JID is already in local address book
- `pytest tests/ -v` passes; new tests cover resilience and sync helpers

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| slixmpp SM plugin clears state on `session_end` | Persist SM fields on `sm_enabled` and before disconnect; inject config on new client |
| Sync secret compromise | Document out-of-band secret rotation; strict trusted-JID-only acceptance |
| Server lacks XEP-0198 | Graceful fallback — connect without SM when enable/resume fails |

## References

- [XEP-0198 Stream Management](https://xmpp.org/extensions/xep-0198.html)
- [XEP-0199 XMPP Ping](https://xmpp.org/extensions/xep-0199.html)
- Existing architecture: `docs/architecture.md`
