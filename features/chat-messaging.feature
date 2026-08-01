# Mapped from OpenSpec: serverless-xmpp-p2p-chat-client
#   Requirement: Pluggable Transports (send/receive)
#   Requirement: Local Persistence, History, and Offline Resilience
# Covered by: tests/test_direct_p2p.py, tests/test_persistence.py, tests/test_e2e_integration.py

Feature: Chat message send, receive, and persistence
  As a connected UI client
  I want reliable message send/receive with local history
  So that conversations survive reconnects and service restarts

  Scenario: Send and receive a chat message over an active session
    Given an active chat session exists for a contact via a connected transport
    When the UI calls chat.send_message with a text body
    Then the service persists an outgoing message with delivered initially false or pending
    And the remote peer receives the stanza on the active transport
    When the remote peer replies with a message stanza
    Then the service persists an incoming message
    And connected UIs receive a message.received push notification

  Scenario: Retrieve chat history after service restart
    Given messages have been exchanged and persisted for a chat
    When the Connection Service is stopped and restarted
    And a UI calls chat.get_history for that chat_id
    Then the most recent messages are returned in chronological order
    And message bodies and directions match what was persisted before the restart

  Scenario: Outbox drains automatically on reconnect
    Given a message was queued because the transport failed to send
    When the transport becomes available again and the outbox is drained
    Then pending outbox entries for that chat are transmitted in order
    And each message delivered status is updated in local persistence
