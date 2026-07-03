#!/usr/bin/env python3
"""Seed demo data for documentation screenshots."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from xmpp_p2p_chat.common.models import ChatSession, DeliveryStatus, Message, MessageDirection
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager


async def seed(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    addressbook = [
        {
            "id": "bob",
            "jid": "bob@p2p.local",
            "name": "Bob",
            "tags": ["friends"],
            "preferred_transport": "direct-p2p",
            "direct": {"host": "192.168.1.50", "port": 5224, "public_key_fingerprint": "SHA256:demo"},
        },
        {
            "id": "carol",
            "jid": "carol@p2p.local",
            "name": "Carol",
            "tags": ["work"],
            "preferred_transport": "direct-p2p",
            "direct": {"host": "192.168.1.51", "port": 5225, "public_key_fingerprint": "SHA256:demo2"},
        },
    ]
    (data_dir / "addressbook.json").write_text(json.dumps(addressbook, indent=2), encoding="utf-8")

    db_path = data_dir / "messages.db"
    if db_path.exists():
        db_path.unlink()

    db = PersistenceManager(db_path)
    await db.initialize()

    now = datetime.now(UTC)
    await db.save_chat(
        ChatSession(
            chat_id="bob",
            contact_id="bob",
            remote_jid="bob@p2p.local",
            transport="direct-p2p",
            created_at=now,
        )
    )
    for msg in [
        Message(
            id="m1",
            chat_id="bob",
            direction=MessageDirection.IN,
            body="Hey Alice — P2P is working!",
            timestamp=now,
            delivered=True,
            status=DeliveryStatus.DELIVERED,
        ),
        Message(
            id="m2",
            chat_id="bob",
            direction=MessageDirection.OUT,
            body="Hi Bob! Serverless mode confirmed.",
            timestamp=now,
            delivered=True,
            status=DeliveryStatus.DELIVERED,
        ),
        Message(
            id="m3",
            chat_id="bob",
            direction=MessageDirection.IN,
            body="No central server needed",
            timestamp=now,
            delivered=True,
            status=DeliveryStatus.DELIVERED,
        ),
    ]:
        await db.save_message(msg)

    await db.save_presence("bob", "available", "Online via direct P2P")
    await db.save_presence("carol", "away", "In a meeting")
    await db.close()


def main() -> None:
    import sys

    target = Path(sys.argv[1] if len(sys.argv) > 1 else ".screenshot-data/data")
    asyncio.run(seed(target))
    print(f"Seeded screenshot data in {target}")


if __name__ == "__main__":
    main()
