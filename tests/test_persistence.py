"""Tests for SQLite persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from xmpp_p2p_chat.common.models import DeliveryStatus, Message, MessageDirection
from xmpp_p2p_chat.connection_service.persistence import PersistenceManager


@pytest.fixture
async def db(tmp_path: Path):
    manager = PersistenceManager(tmp_path / "messages.db")
    await manager.initialize()
    yield manager
    await manager.close()


@pytest.mark.asyncio
async def test_save_and_load_history(db: PersistenceManager):
    msg = Message(
        id="m1",
        chat_id="alice",
        direction=MessageDirection.OUT,
        body="Hello",
        timestamp=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
        status=DeliveryStatus.SENT,
    )
    await db.save_message(msg)
    history = await db.get_history("alice", limit=10)
    assert len(history) == 1
    assert history[0].body == "Hello"
    assert history[0].direction == MessageDirection.OUT


@pytest.mark.asyncio
async def test_outbox_queue_and_drain(db: PersistenceManager):
    msg = Message(
        id="m2",
        chat_id="bob",
        direction=MessageDirection.OUT,
        body="Queued",
        status=DeliveryStatus.PENDING,
    )
    await db.queue_outbound(msg)
    pending = await db.get_pending_outbox("bob")
    assert len(pending) == 1
    assert pending[0].body == "Queued"

    await db.mark_delivered("m2")
    assert await db.pending_outbox_count() == 0


@pytest.mark.asyncio
async def test_history_survives_reopen(tmp_path: Path):
    db_path = tmp_path / "messages.db"
    manager = PersistenceManager(db_path)
    await manager.initialize()
    await manager.save_message(
        Message(
            id="persist-1",
            chat_id="carol",
            direction=MessageDirection.IN,
            body="Survives restart",
            delivered=True,
            status=DeliveryStatus.DELIVERED,
        )
    )
    await manager.close()

    reloaded = PersistenceManager(db_path)
    await reloaded.initialize()
    history = await reloaded.get_history("carol")
    await reloaded.close()

    assert len(history) == 1
    assert history[0].body == "Survives restart"
