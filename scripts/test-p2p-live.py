#!/usr/bin/env python3
"""Live two-peer P2P test: bidirectional messaging via RPC."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from typing import Any

import websockets


class RpcClient:
    """JSON-RPC client that ignores server push notifications."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._ws: websockets.ClientConnection | None = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(self.url, ping_interval=20, ping_timeout=20)

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def call(self, method: str, params: dict | None = None, *, timeout: float = 30.0) -> Any:
        if not self._ws:
            raise RuntimeError("Not connected")

        req_id = str(uuid.uuid4())
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        await self._ws.send(json.dumps(payload))

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"RPC timeout waiting for {method}")

            raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
            message = json.loads(raw)

            if message.get("id") != req_id:
                continue

            if "error" in message:
                err = message["error"]
                raise RuntimeError(f"{method} failed: {err.get('message', err)}")

            return message.get("result")


async def wait_for_fingerprint(client: RpcClient, *, timeout: float = 30.0) -> str:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for P2P fingerprint")

        try:
            status = await client.call("connection.status", timeout=min(5.0, remaining))
            fp = status.get("p2p_fingerprint")
            if fp:
                return fp
        except (TimeoutError, RuntimeError, websockets.ConnectionClosed):
            pass

        await asyncio.sleep(0.5)


async def wait_for_message(
    client: RpcClient,
    chat_id: str,
    body: str,
    *,
    timeout: float = 15.0,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for message: {body!r}")

        history = await client.call(
            "chat.get_history",
            {"chat_id": chat_id, "limit": 50},
            timeout=min(5.0, remaining),
        )
        messages = history.get("messages", [])
        if any(m.get("body") == body for m in messages):
            return

        await asyncio.sleep(0.5)


async def run_test(alice_url: str, bob_url: str) -> int:
    alice = RpcClient(alice_url)
    bob = RpcClient(bob_url)

    try:
        await alice.connect()
        await bob.connect()

        print("Waiting for P2P fingerprints...")
        alice_fp = await wait_for_fingerprint(alice)
        bob_fp = await wait_for_fingerprint(bob)
        print(f"  alice: {alice_fp}")
        print(f"  bob:   {bob_fp}")

        await alice.call(
            "addressbook.update",
            {
                "id": "bob",
                "partial": {
                    "direct": {
                        "host": "127.0.0.1",
                        "port": 5224,
                        "public_key_fingerprint": bob_fp,
                    }
                },
            },
        )
        await bob.call(
            "addressbook.update",
            {
                "id": "alice",
                "partial": {
                    "direct": {
                        "host": "127.0.0.1",
                        "port": 5223,
                        "public_key_fingerprint": alice_fp,
                    }
                },
            },
        )

        print("Reconnecting transports with trusted fingerprints...")
        await alice.call("connection.reconnect")
        await bob.call("connection.reconnect")

        await alice.call("chat.start", {"contact_id": "bob"})
        await bob.call("chat.start", {"contact_id": "alice"})

        alice_msg = "Hello Bob from live P2P test"
        bob_msg = "Hi Alice from live P2P test"

        print(f"Alice → Bob: {alice_msg!r}")
        sent = await alice.call("chat.send_message", {"chat_id": "bob", "body": alice_msg})
        if sent["message"]["body"] != alice_msg:
            print("FAIL: Alice send_message returned unexpected body", file=sys.stderr)
            return 1

        await wait_for_message(bob, "alice", alice_msg)
        print("Bob received Alice's message")

        print(f"Bob → Alice: {bob_msg!r}")
        sent = await bob.call("chat.send_message", {"chat_id": "alice", "body": bob_msg})
        if sent["message"]["body"] != bob_msg:
            print("FAIL: Bob send_message returned unexpected body", file=sys.stderr)
            return 1

        await wait_for_message(alice, "bob", bob_msg)
        print("Alice received Bob's message")

        print("PASS: bidirectional live P2P messaging OK")
        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        await alice.close()
        await bob.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live two-peer P2P RPC test")
    parser.add_argument(
        "--alice",
        default=os.environ.get("ALICE_RPC_URL", "ws://127.0.0.1:8765/rpc"),
        help="Alice RPC WebSocket URL",
    )
    parser.add_argument(
        "--bob",
        default=os.environ.get("BOB_RPC_URL", "ws://127.0.0.1:8766/rpc"),
        help="Bob RPC WebSocket URL",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run_test(args.alice, args.bob)))


if __name__ == "__main__":
    main()
