# Specification: XMPP Resilience & Address Book Sync

## Purpose

Define required behavior for XEP-0198 stream management, XEP-0199 keepalive, structured XMPP error reporting, and signed address book synchronization on the XMPP server transport.

Requirements use RFC 2119 keywords. Scenarios use Given/When/Then.

---

## Requirement: XEP-0198 Stream Management

The XMPP server transport SHALL negotiate XEP-0198 (Stream Management) when the server supports it and `[xmpp] stream_management_enabled` is true.

#### Scenario: Enable SM on first connect
- **GIVEN** a configured XMPP JID and a server advertising `urn:xmpp:sm:3`
- **WHEN** the transport completes resource binding
- **THEN** it SHALL send `<enable xmlns='urn:xmpp:sm:3' resume='true'/>`
- **AND** store the returned stream management id (`sm_id`) locally

#### Scenario: Persist SM state
- **GIVEN** SM is enabled with a known `sm_id`
- **WHEN** the `sm_enabled` event fires or the stream disconnects unexpectedly
- **THEN** the service SHALL persist `{jid, sm_id, handled, last_ack}` to `{data_dir}/.xmpp-sm-state.json`

#### Scenario: Resume stream after reconnect
- **GIVEN** persisted SM state for the same JID and a server that allows resumption
- **WHEN** the transport reconnects within the server's resumption timeout
- **THEN** it SHALL send `<resume previd='…' h='…'/>` before re-binding
- **AND** unacknowledged outbound stanzas SHALL be resent by the slixmpp plugin

#### Scenario: Fallback when SM unavailable
- **GIVEN** the server returns `<failed/>` for enable or resume
- **WHEN** negotiation fails
- **THEN** the transport SHALL continue with a normal session (no SM)
- **AND** clear invalid persisted `sm_id`

---

## Requirement: XEP-0199 Ping Keepalive

The XMPP server transport SHALL send periodic XMPP pings while connected.

#### Scenario: Successful keepalive
- **GIVEN** transport state is `connected` and `ping_interval_seconds` is 90
- **WHEN** 90 seconds elapse without disconnect
- **THEN** the transport SHALL send `<iq type='get'><ping xmlns='urn:xmpp:ping'/></iq>`
- **AND** remain connected on successful response

#### Scenario: Dead connection detection
- **GIVEN** ping is sent and no response within `ping_timeout_seconds`
- **WHEN** ping fails or times out
- **THEN** the transport SHALL transition to reconnecting
- **AND** attempt reconnection using existing backoff logic

---

## Requirement: Structured XMPP Error Reporting

The Connection Service SHALL parse XMPP error stanzas and expose structured error information via the API.

#### Scenario: Connection failure with XMPP error
- **GIVEN** authentication or bind fails with an XMPP error stanza
- **WHEN** the transport enters `error` state
- **THEN** `connection.status` SHALL include `error_condition` (e.g. `not-authorized`)
- **AND** `error_type` when present (e.g. `auth`)
- **AND** human-readable `error` text for UIs

#### Scenario: Log full error context
- **GIVEN** any XMPP error during connect, send, or ping
- **WHEN** the error is handled
- **THEN** the service SHALL log condition, type, and stanza summary at WARNING or ERROR level

---

## Requirement: Signed Address Book Sync

The Connection Service MAY distribute address book mutations to trusted peers over XMPP when sync is enabled.

#### Scenario: Reject untrusted sender
- **GIVEN** sync is enabled
- **WHEN** an address book update IQ arrives from a JID not in the local address book
- **THEN** the service SHALL reject it without modifying the address book

#### Scenario: Verify signature
- **GIVEN** sync is enabled with a configured shared secret
- **WHEN** a signed update arrives from a trusted JID
- **THEN** the service SHALL verify HMAC-SHA256 over the payload
- **AND** reject updates with invalid signatures or stale timestamps (> `max_timestamp_skew_seconds`)

#### Scenario: Pending review mode (default)
- **GIVEN** `[addressbook.sync] auto_apply = false`
- **WHEN** a valid signed update is received
- **THEN** it SHALL be stored in the pending queue
- **AND** emit `addressbook.sync_pending` to connected UIs

#### Scenario: Auto-apply mode
- **GIVEN** `[addressbook.sync] auto_apply = true`
- **WHEN** a valid signed add/update/remove is received
- **THEN** the service SHALL apply the mutation atomically to `addressbook.json`
- **AND** emit `addressbook.updated`

#### Scenario: Push update to peers
- **GIVEN** sync enabled and at least one XMPP-connected trusted contact
- **WHEN** `addressbook.sync_now` is called after a local add/update/remove
- **THEN** the service SHALL send signed update stanzas to eligible peers

---

## Requirement: API Surface

The WebSocket JSON-RPC API SHALL expose sync and resilience status.

#### Scenario: connection.status includes XMPP details
- **GIVEN** XMPP transport is active
- **WHEN** a UI calls `connection.status`
- **THEN** each transport entry SHALL include `state`, `error`, and when applicable `error_condition`, `error_type`
- **AND** `stream_management` object with `{enabled, sm_id_present}` when SM is active

#### Scenario: Sync API methods
- **GIVEN** the service is running
- **WHEN** UIs call `addressbook.sync_status`, `addressbook.enable_sync`, `addressbook.sync_now`, `addressbook.get_pending_updates`, `addressbook.apply_pending_update`, or `addressbook.reject_pending_update`
- **THEN** the service SHALL behave as documented in `design.md`

---

## Non-Goals (this change)

- Stream Management on direct P2P transports
- Server roster synchronization as source of truth
- End-to-end encryption of sync payloads (transport TLS only; HMAC provides integrity/authenticity among secret holders)
