# Direct P2P (Serverless) Mode

Serverless-xmpp's primary mode is **direct peer-to-peer XMPP** over TLS — no central chat server required. Each client runs a Connection Service that listens for inbound peers and connects outbound using pre-placed address book entries (host, port, certificate fingerprint).

Inspired by [XEP-0174 Serverless Messaging](https://xmpp.org/extensions/xep-0174.html).

## How It Works

```
Alice (listen :5223)  ←—— TLS + XMPP stream ——→  Bob (listen :5224)
         ↑                                              ↑
    Text TUI / Web UI                            Text TUI / Web UI
         ↑                                              ↑
   ws://127.0.0.1:8765                          ws://127.0.0.1:8766
```

1. Each peer generates a local TLS certificate (stored in `data/p2p/`).
2. Share your **SHA256 fingerprint** with contacts out-of-band (Signal, in person, etc.).
3. Add contacts to `addressbook.json` with `preferred_transport: "direct-p2p"` and `direct.host/port/fingerprint`.
4. Messages flow directly between peers — no XMPP server in the middle.

## Quick Setup (Two Peers on One Machine)

```bash
# Install
pip install -e ".[dev]"

# Initialize both peers
./scripts/test-multi-client.sh init-p2p-alice
./scripts/test-multi-client.sh init-p2p-bob

# Terminal 1 — start alice (generates cert on first run)
./scripts/test-multi-client.sh service-p2p-alice

# Terminal 2 — start bob
./scripts/test-multi-client.sh service-p2p-bob

# Get fingerprints (after both services have started once)
./scripts/test-multi-client.sh p2p-fingerprints

# Update each peer's addressbook.json with the other's fingerprint, then restart services.
```

### Automated live test

To spin up both peers, exchange fingerprints, and verify bidirectional messaging in one step:

```bash
FRESH=1 ./scripts/test-multi-client.sh test-p2p-live
```

## Config Reference

```toml
[connection]
default_transport = "direct-p2p"

[p2p]
local_jid = "alice@p2p.local"   # Your identity for P2P streams
listen_host = "0.0.0.0"         # Bind for inbound peers
listen_port = 5223              # Your listening port
mdns_enabled = true             # Advertise and browse on LAN (zeroconf)
mdns_service_type = "_xmpp-p2p._tcp.local."

[security]
allow_self_signed_direct = true # Required for self-signed P2P certs
```

## Address Book Entry

```json
{
  "id": "bob",
  "jid": "bob@p2p.local",
  "name": "Bob",
  "preferred_transport": "direct-p2p",
  "direct": {
    "host": "192.168.1.50",
    "port": 5224,
    "public_key_fingerprint": "SHA256:ABCD..."
  }
}
```

## mDNS LAN Discovery

When `mdns_enabled = true` (default), each running Connection Service:

1. **Advertises** itself as `_xmpp-p2p._tcp.local.` with TXT records `jid`, `fp` (fingerprint), and `transport`.
2. **Browses** for other peers on the same LAN.
3. Exposes discovered peers via `discovery.list` and pushes `discovery.updated` to connected UIs.

Use `discovery.apply` with a matching contact id to fill in `direct.host`, `direct.port`, and fingerprint from a discovered peer — useful when you know someone's JID but not their current IP.

Fingerprints should still be verified out-of-band before trusting a peer.

## API: Check P2P Status

```json
// connection.status
{
  "transports": [{"transport": "direct-p2p", "state": "connected", ...}],
  "p2p_fingerprint": "SHA256:...",
  "p2p_listen_port": 5223
}
```

## Automated Test

```bash
./scripts/test-multi-client.sh test-p2p
```

Runs a pytest that spins up two `DirectP2PTransport` instances on localhost and verifies bidirectional messaging.

## XMPP Server Fallback

Set `preferred_transport: "xmpp-server"` on a contact (or configure `[xmpp]` credentials) to use traditional server-mediated XMPP alongside or instead of P2P. Both transports can coexist in one Connection Service.

## Security Notes

- TLS 1.2+ is required for all P2P connections.
- Pin each contact's certificate fingerprint in the address book.
- The local API remains bound to `127.0.0.1` only.
- No telemetry; external connections only to configured peer endpoints.
