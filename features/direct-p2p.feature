# Mapped from OpenSpec: serverless-xmpp-p2p-chat-client
#   Requirement: Pluggable Transports / Extensibility (DirectP2PTransport)
# Covered by: tests/test_direct_p2p.py, docs/p2p-serverless.md

Feature: Direct P2P session over TLS
  As a member of a trusted circle
  I want peer-to-peer chats without a central XMPP server
  So that messages travel over direct TLS XML streams between known endpoints

  Scenario: Generate local P2P certificate and fingerprint
    Given a local data directory for P2P certificates
    When the service ensures P2P certificates for the local identity
    Then a certificate and private key exist on disk
    And the fingerprint is reported as a SHA256 value
    And fingerprint verification succeeds against the generated certificate

  Scenario: Establish direct P2P session and exchange a message
    Given two peers Alice and Bob with mutual address book endpoints and fingerprints
    And each peer listens on a local TLS port for direct-p2p
    When Alice connects outbound to Bob's direct endpoint
    And Alice sends a chat message body to Bob over the P2P transport
    Then Bob receives the message body on the inbound stream
    And the exchange uses TLS-backed XMPP-style message stanzas

  Scenario: Prefer direct-p2p when contact preferred_transport is set
    Given a contact in the address book with preferred_transport "direct-p2p"
    And a direct host, port, and public_key_fingerprint
    When a UI calls chat.start for that contact
    Then the SessionManager selects the DirectP2PTransport
    And connection.status reflects the direct-p2p transport state
