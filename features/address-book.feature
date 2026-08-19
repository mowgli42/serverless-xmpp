# Mapped from OpenSpec: serverless-xmpp-p2p-chat-client
#   Requirement: Pre-placed Local Address Book as Single Source of Contacts
# Covered by: tests/test_addressbook.py, tests/test_addressbook_hash.py, tests/test_api.py

Feature: Local address book load and content hash
  As a user of the Connection Service
  I want contacts loaded from local JSON with a stable content fingerprint
  So that I can verify the distributed address book before peers connect

  Scenario: Successful load of primary address book on service start
    Given the configured data directory contains a valid addressbook.json with one or more contacts
    When the Connection Service starts
    Then the service parses the file without error
    And addressbook.list returns the full contact list
    And addressbook.status reports contact_count matching the loaded contacts

  Scenario: Address book version and content hash update on mutation
    Given the Connection Service has started with an empty or seeded address book
    When a UI calls addressbook.add with a valid contact id, jid, and name
    Then the address book version increments
    And content_hash is a SHA256 fingerprint that changes with the contact set
    And addressbook.status includes 64 hash_blocks for the visual fingerprint grid

  Scenario: Bundled address book import on first run
    Given the data directory has no addressbook.json
    And a bundled default address book is available
    When the Connection Service starts with import_bundled_if_empty enabled
    Then the bundled contacts are imported into the primary address book
    And addressbook.status reports the bundled_source path

  Scenario: Malformed address book entries are quarantined
    Given the address book file contains invalid JSON
    When the Connection Service loads the address book
    Then valid contacts are retained when possible
    And the bad file is quarantined with a .bad suffix
    And system.health or addressbook.status exposes load warnings
