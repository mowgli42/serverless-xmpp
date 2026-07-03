# Serverless XMPP P2P Chat Client Specification

## Purpose

This specification defines the required behavior of a serverless-capable XMPP-based chat system that uses pre-placed local address books for contact management and supports peer-to-peer style direct chats. The architecture mandates a clean separation between the Connection Service (which owns all protocol logic, transports, sessions, and persistence) and any number of user interface clients (text-based TUI and web SPA). The system enables trusted individuals to communicate without depending on a central application server or dynamic roster synchronization.

All requirements use RFC 2119 keywords (SHALL, MUST, SHOULD, MAY). Scenarios follow the Given/When/Then format for clarity and testability.

## Requirements

### Requirement: Pre-placed Local Address Book as Single Source of Contacts

The Connection Service SHALL treat the local address book file(s) as the authoritative and only source of contact information. It SHALL NOT automatically import, modify, or synchronize with any XMPP server roster unless explicitly directed by user configuration or UI action for a specific contact.

#### Scenario: Successful load of primary address book on service start
- **GIVEN** the configured data directory contains a valid `addressbook.json` file with one or more well-formed contact entries
- **WHEN** the Connection Service starts
- **THEN** it SHALL parse the file without error
- **AND** make the full list of contacts available via the `addressbook.list` API method
- **AND** log a summary of loaded contacts (count, any validation warnings)

#### Scenario: Add a new contact via API
- **GIVEN** the Connection Service is running and at least one UI is connected
- **WHEN** a UI calls `addressbook.add` with a valid contact object containing at minimum a unique `id`, `jid` (valid JID format), and `name`
- **THEN** the service SHALL validate the JID syntax and uniqueness of `id`
- **AND** atomically append the contact to the address book file
- **AND** emit an `addressbook.updated` notification to all connected UIs
- **AND** return success with the new contact's `id`

#### Scenario: Handle malformed address book on load (resilience)
- **GIVEN** the address book file exists but contains invalid JSON or entries missing required fields
- **WHEN** the Connection Service starts or reloads the address book
- **THEN** it SHALL log clear errors/warnings identifying the problematic entries
- **AND** load only the valid contacts
- **AND** quarantine or rename the bad file for manual inspection (never silently delete user data)
- **AND** expose a `system.health` or error status via API indicating partial load

#### Scenario: Support for additional address book fragments
- **GIVEN** the data directory contains `addressbooks.d/family.json` and `addressbooks.d/work.json` with valid contact arrays
- **WHEN** the service loads the address book
- **THEN** it SHALL merge all contacts from primary + fragment files
- **AND** treat `id` collisions as errors (or apply last-modified-wins policy documented in config)
- **AND** expose a unified list via API

### Requirement: Pluggable Transports with Server-Mode XMPP as MVP Primary Path

The Connection Service SHALL provide a pluggable transport abstraction. For the MVP it SHALL fully implement and prefer an XMPP server-mediated transport using the `slixmpp` library. Direct P2P transport MAY be implemented in a subsequent phase but the architecture SHALL support adding it without core changes.

#### Scenario: Initiate chat using XMPP server transport (happy path)
- **GIVEN** a contact exists in the address book with a valid `jid` and no overriding `preferred_transport=direct-p2p`
- **WHEN** any connected UI calls `chat.start(contact_id)`
- **THEN** the service SHALL resolve the target XMPP server (DNS SRV `_xmpp-client._tcp` or explicit `xmpp_server` field or default to jid domain)
- **AND** establish a TLS 1.3 connection (enforce minimum TLS version and strong ciphers)
- **AND** authenticate using credentials referenced in the contact entry (keyring or config)
- **AND** bind a resource and send initial presence
- **AND** mark the chat as active and return a `chat_id` to the calling UI
- **AND** push a `connection.changed` event with state `connected`

#### Scenario: Send and receive a chat message over XMPP server transport
- **GIVEN** an active chat session exists for a contact via XMPP server transport
- **WHEN** the UI calls `chat.send_message(chat_id, body="Hello from the other side")`
- **THEN** the service SHALL construct a proper `<message type="chat">` stanza with the contact's JID as `to`, the body, and a unique `id`
- **AND** send it via the active slixmpp stream
- **AND** persist a copy to local message history as `direction=out`, `delivered=false` initially
- **WHEN** the remote peer replies with a message stanza
- **THEN** the service SHALL receive it via registered handler
- **AND** persist it as `direction=in`
- **AND** push a `message.received` notification containing the normalized message to all connected UIs
- **AND** mark any matching outgoing message as delivered if stanza `id` matches

#### Scenario: Automatic reconnection and offline queuing
- **GIVEN** the XMPP connection drops (network change, server restart)
- **WHEN** the service detects the disconnect
- **THEN** it SHALL update connection state and notify UIs
- **AND** enter a reconnection loop with exponential backoff (max 5 minutes) and jitter
- **WHEN** a UI sends a message while disconnected
- **THEN** the service SHALL persist it to the outbox and local history with `delivered=false`
- **AND** automatically transmit queued messages for that chat upon successful reconnection
- **AND** update delivery status and notify UIs of state changes

### Requirement: Strict Separation of Connection Service from User Interfaces

The Connection Service SHALL expose all functionality exclusively through a local, well-defined API. No UI code SHALL contain XMPP protocol logic, stanza construction, or direct socket handling. Multiple independent UIs SHALL be able to attach to a single running service instance and remain synchronized.

#### Scenario: Text TUI and Web UI both attach and stay in sync
- **GIVEN** the Connection Service is running and listening on `ws://127.0.0.1:8765`
- **WHEN** the Textual TUI starts and connects to the WebSocket endpoint
- **AND** the Svelte Web UI (in a browser tab) also connects to the same endpoint
- **THEN** both UIs SHALL be able to call methods such as `addressbook.list` and `chat.start`
- **WHEN** the TUI initiates a chat and sends a message
- **THEN** the Web UI SHALL receive a real-time `message.received` push notification and update its UI without user action
- **AND** vice-versa: actions performed in the Web UI are immediately visible in the TUI
- **AND** connection state changes (connect/disconnect/reconnect) are reflected in both UIs

#### Scenario: UI can detach and re-attach without losing service state
- **GIVEN** a chat is active and message history exists
- **WHEN** one UI (e.g. Web) disconnects from the WS (browser close or network flap)
- **THEN** the Connection Service SHALL continue operating normally and maintain all sessions/transports
- **WHEN** the same or another UI re-connects and authenticates (if token required)
- **THEN** it SHALL be able to immediately call `chat.get_history(chat_id)` and receive the full persisted history
- **AND** resume receiving live push events for new messages

#### Scenario: Simple local API authentication (optional but recommended)
- **GIVEN** `api_token` is set in config.toml
- **WHEN** any UI connects to the WebSocket
- **THEN** the service SHALL require the first message to be an `auth` request containing the token (or HTTP Authorization header equivalent)
- **AND** reject connections with invalid/missing token with a clear error
- **AND** log the successful auth with client identifier (TUI vs web)

### Requirement: Full-Featured Text-Based User Interface (TUI)

A keyboard-centric Textual TUI client SHALL be provided that delivers complete functionality for address book management and real-time chatting. It SHALL feel native to the terminal and be usable over SSH or on resource-constrained devices.

#### Scenario: Browse contacts and start a chat from TUI
- **GIVEN** the TUI is running and connected to the service, address book contains several contacts
- **WHEN** the user opens the contacts screen (default or via keybinding `c`)
- **THEN** it SHALL display a searchable, filterable list of contacts showing name, JID, tags, last-seen presence, and unread message count
- **WHEN** the user navigates (arrow keys or vim keys) to a contact and presses `Enter` or `o` (open chat)
- **THEN** the TUI SHALL switch to or open a dedicated chat pane/screen for that contact
- **AND** load and render recent message history (with timestamps, sender name, visual distinction for in/out)
- **AND** place focus in the message input field

#### Scenario: Send and receive messages in TUI chat pane
- **GIVEN** a chat pane is open for an active contact
- **WHEN** the user types a message and presses `Enter`
- **THEN** the TUI SHALL immediately display the message in the history (optimistic) with "sending..." or pending style
- **AND** call the service `chat.send_message` API
- **WHEN** the service confirms delivery or a reply arrives
- **THEN** the TUI SHALL update the message status (e.g., checkmark) or append the incoming message in real time
- **AND** scroll the history view appropriately (auto-scroll to bottom unless user scrolled up)
- **AND** provide visual/audible notification (configurable) for new messages when the chat is not focused

#### Scenario: TUI supports multiple concurrent chats and graceful exit
- **GIVEN** the TUI supports tabbed or split layout (Textual `TabPane` or `Dock`)
- **WHEN** the user opens chats with 2–3 contacts
- **THEN** they can switch between tabs with keybindings (e.g., `Ctrl+PgUp/Down` or numbers)
- **WHEN** the user presses `Ctrl+C` or `q` (quit)
- **THEN** the TUI SHALL cleanly disconnect from the service, flush any pending state if needed, and exit with code 0
- **AND** leave the Connection Service running for other UIs or future re-attachment

### Requirement: Modern Web-Based User Interface (SPA)

A responsive web single-page application SHALL be provided that implements equivalent (or richer) functionality to the TUI by consuming the exact same Connection Service WebSocket API. It SHALL run in any modern browser and be easy to host or serve locally.

#### Scenario: Contact list and chat in Web UI
- **GIVEN** the Web UI is loaded in a browser and connected to `ws://127.0.0.1:8765`
- **WHEN** the main screen renders
- **THEN** it SHALL show a sidebar with the contact list (searchable, grouped by tags if present, presence indicators, unread badges)
- **WHEN** the user clicks a contact
- **THEN** the main pane SHALL open a chat interface showing message history (virtualized list for performance), message bubbles (outgoing right-aligned, incoming left), timestamps, and delivery status
- **AND** focus the composer textarea
- **WHEN** the user types and clicks Send (or presses Ctrl+Enter)
- **THEN** the message appears optimistically in the UI and is sent via the API
- **AND** incoming messages from the service push notification render instantly as new bubbles without refresh

#### Scenario: Web UI settings and service management
- **GIVEN** the Web UI has a settings or "Service" modal/page
- **WHEN** the user opens it
- **THEN** it SHALL display current connection status per transport, allow manual connect/disconnect/reconnect buttons
- **AND** provide forms to add/edit/remove contacts (with validation feedback)
- **AND** show basic service health (uptime, message queue depth, log level)
- **AND** allow changing simple config values that the service supports via API (e.g., presence, default transport preference)

#### Scenario: Web UI works offline from browser perspective but connected to local service
- **GIVEN** the browser has no internet access (air-gapped or VPN down) but can reach localhost
- **WHEN** the Web UI is loaded from a local file or served by the Connection Service itself
- **THEN** it SHALL fully function for all chat and address book operations because the service handles all external network I/O
- **AND** display a subtle indicator that it is running in "local service mode"

### Requirement: Local Persistence, History, and Offline Resilience

The Connection Service SHALL persist all address book data, chat history, and outbound message queues locally using durable storage. It SHALL support full operation while transports are offline and gracefully recover state on restart.

#### Scenario: Retrieve chat history after service restart
- **GIVEN** multiple messages have been exchanged in a chat and persisted
- **WHEN** the Connection Service is stopped and restarted
- **THEN** on UI re-connection and `chat.get_history(chat_id, limit=50)`
- **THEN** it SHALL return the most recent messages in chronological order with correct direction, timestamps, and delivery status
- **AND** not lose any messages that were successfully sent before the restart

#### Scenario: Outbox drains automatically on reconnect
- **GIVEN** several messages were queued while the XMPP transport was disconnected
- **WHEN** the transport successfully reconnects
- **THEN** the service SHALL drain the outbox for affected chats in order
- **AND** update each message's `delivered` status in the database
- **AND** push `message.updated` or `message.delivered` events to UIs so they can update checkmarks/status

### Requirement: Security, Privacy, and Local-Only Operation

The system SHALL prioritize user privacy and data sovereignty. All external communication SHALL use strong encryption. The Connection Service and UIs SHALL NOT initiate any network connections except those explicitly required for user-configured XMPP servers or direct peer endpoints listed in the address book. No telemetry or analytics SHALL be collected or transmitted.

#### Scenario: Enforced TLS and certificate validation for XMPP server connections
- **GIVEN** a contact with a JID whose server supports TLS
- **WHEN** the service establishes the XMPP connection
- **THEN** it SHALL require and verify a valid TLS 1.3 (or minimum configured version) certificate using system trust store + optional per-contact pinning
- **AND** refuse to send credentials or messages over plaintext or weak TLS
- **AND** surface certificate errors clearly to the UI for user decision (e.g., TOFU prompt or reject)

#### Scenario: Local API is not exposed to the network
- **GIVEN** default configuration
- **WHEN** the Connection Service starts its WebSocket API server
- **THEN** it SHALL bind exclusively to `127.0.0.1` (or configurable but default localhost-only)
- **AND** reject any connection attempts from remote IPs at the socket level
- **AND** document in README/config comments how to safely expose via SSH tunnel or VPN if multi-machine access is desired

#### Scenario: Sensitive credential handling
- **GIVEN** a contact entry references credentials stored in the OS keyring
- **WHEN** the service needs to authenticate
- **THEN** it SHALL retrieve the password via the `keyring` library (or equivalent secure store)
- **AND** never log the password
- **AND** fall back gracefully to a one-time prompt via UI callback if keyring is unavailable or entry missing

### Requirement: Extensibility and Maintainability

The Connection Service SHALL be architected with clear internal boundaries (address book, transports, sessions, persistence, API) so that new features (additional transports, E2EE plugins, new UIs) can be added by modifying or extending specific modules without widespread changes. All public behavior SHALL be captured in this specification and updated when behavior changes.

#### Scenario: Adding a new transport implementation
- **GIVEN** the `transports/base.py` defines an abstract `BaseTransport` with required methods (`connect`, `disconnect`, `send_message`, `register_stanza_handler`, etc.)
- **WHEN** a developer (or future Cursor task) implements `DirectP2PTransport` conforming to the interface
- **THEN** the SessionManager SHALL be able to register and select it based on contact `preferred_transport` or availability
- **AND** existing server-mode functionality and all UIs continue to work unchanged
- **AND** the new transport's behavior for message send/receive is exercised via the same `chat.send_message` / push paths

## Non-Functional Requirements

- **Performance**: Message send-to-receive latency via local XMPP server or direct P2P on same LAN SHALL be under 500 ms perceived in UI for typical text messages. History queries for last 100 messages SHALL return in < 200 ms.
- **Resource Usage**: Connection Service idle SHALL use < 50 MB RAM. TUI SHALL run comfortably on 512 MB total system RAM. Web UI bundle SHALL be < 500 kB gzipped.
- **Reliability**: Service SHALL survive at least 10 000 message exchanges and multiple reconnect cycles without memory leaks or state corruption (verified via long-running test or soak).
- **Usability**: Both UIs SHALL provide discoverable help ( `?` key or help button), sensible defaults, and clear error messages with suggested actions.
- **Portability**: Connection Service + TUI SHALL run on Linux, macOS, and Windows (Python 3.11+). Web UI SHALL work in current Chrome, Firefox, Edge, Safari.
- **Maintainability**: Code SHALL follow PEP 8 / modern Python conventions, include type hints (where practical with slixmpp), and have docstrings on public classes/methods. Cursor-generated code must pass `ruff check` and basic pytest smoke tests.

## Open Questions & Future Considerations (Not Binding for MVP)

- Exact wire format and versioning strategy for the JSON-RPC API (consider simple versioned method names or a small OpenAPI-inspired registry).
- Whether to include a minimal static file server in the Connection Service to serve the built Web UI assets for true single-command launch.
- Integration points for optional E2EE (e.g., a `MessageEncryptor` plugin interface).
- Support for XEP-0184 delivery receipts and XEP-0308 message correction in the core message model.
- Internationalization (i18n) strategy for future non-English UIs.

This specification, together with the proposal and design documents, provides a complete, testable contract for implementing the serverless XMPP P2P chat client using Cursor and the OpenSpec workflow.
