"""Prosody XMPP server for local multi-client testing."""

component_ports = {5222}

VirtualHost "localhost"
    enabled = true

-- Allow insecure auth for local dev only
c2s_require_encryption = false
allow_unencrypted_plain_auth = true

-- Test accounts: alice / alice, bob / bob
VirtualHost "localhost"
    authentication = "internal_hashed"

-- Register via: prosodyctl register alice localhost alice
