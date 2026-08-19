# Mapped from OpenSpec: serverless-xmpp-p2p-chat-client
#   Requirement: Full-Featured Text-Based User Interface (TUI)
#   Requirement: Modern Web-Based User Interface (SPA)
#   Requirement: Strict Separation of Connection Service from User Interfaces
# Covered by: tests/test_text_ui_display.py, tests/test_api.py, web_ui/src/App.svelte

Feature: UI smoke paths against the Connection Service API
  As a user of the Text TUI or Web SPA
  I want thin UIs that stay in sync with the Connection Service
  So that address book and chat state remain consistent across clients

  Scenario: Text TUI shows contacts, hash, and chat history
    Given the Connection Service is running and the TUI is connected over WebSocket JSON-RPC
    And the address book contains one or more contacts
    When the TUI loads the contact list and address book status
    Then the sidebar shows contact count and address book version
    And while awaiting connection the sidebar shows the full hash fingerprint grid
    When the user opens a chat with a contact that has history
    Then recent messages render with direction and delivery status markers

  Scenario: Web UI lists contacts and sends a message via the shared API
    Given the Web SPA is loaded and connected to ws://127.0.0.1 API
    When the main screen renders
    Then it shows a sidebar contact list from addressbook.list
    And it displays connection.status and address book hash when awaiting connection
    When the user selects a contact and sends a message from the composer
    Then the UI calls chat.send_message through the shared API client
    And optimistic outgoing bubbles appear without a page refresh

  Scenario: Multiple UIs stay in sync via push notifications
    Given two UI clients are attached to the same Connection Service
    When one client calls addressbook.add with a new contact
    Then the other client receives an addressbook.updated push notification
    And both clients see the same contact list on the next addressbook.list
