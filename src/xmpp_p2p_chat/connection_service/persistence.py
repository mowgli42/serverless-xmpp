"""SQLite persistence for messages, chats, and outbox."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiosqlite

from xmpp_p2p_chat.common.models import (
    AddressBookSyncPending,
    ChatSession,
    DeliveryStatus,
    Message,
    MessageDirection,
)

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    direction TEXT NOT NULL,
    body TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    stanza_id TEXT,
    delivered INTEGER NOT NULL DEFAULT 0,
    read_flag INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    raw_stanza TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, timestamp);

CREATE TABLE IF NOT EXISTS chats (
    chat_id TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL,
    remote_jid TEXT NOT NULL,
    transport TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    chat_id TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS presence (
    contact_id TEXT PRIMARY KEY,
    show TEXT NOT NULL DEFAULT 'offline',
    status TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS addressbook_sync_pending (
    id TEXT PRIMARY KEY,
    from_jid TEXT NOT NULL,
    action TEXT NOT NULL,
    contact_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    received_at TEXT NOT NULL
);
"""


class PersistenceManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if not self._db:
            raise RuntimeError("PersistenceManager not initialized")
        return self._db

    async def save_message(self, message: Message) -> Message:
        await self.db.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, chat_id, direction, body, timestamp, stanza_id, delivered, read_flag, status, raw_stanza)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.chat_id,
                message.direction.value,
                message.body,
                message.timestamp.isoformat(),
                message.stanza_id,
                int(message.delivered),
                int(message.read),
                message.status.value,
                json.dumps(message.raw_stanza) if message.raw_stanza else None,
            ),
        )
        await self.db.commit()
        return message

    async def get_history(
        self, chat_id: str, limit: int = 50, before: datetime | None = None
    ) -> list[Message]:
        params: list = [chat_id]
        query = "SELECT * FROM messages WHERE chat_id = ?"
        if before:
            query += " AND timestamp < ?"
            params.append(before.isoformat())
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = await self.db.execute_fetchall(query, params)
        messages = [self._row_to_message(row) for row in reversed(rows)]
        return messages

    async def queue_outbound(self, message: Message) -> None:
        await self.save_message(message)
        await self.db.execute(
            "INSERT OR IGNORE INTO outbox (message_id, chat_id, body, created_at) VALUES (?, ?, ?, ?)",
            (message.id, message.chat_id, message.body, message.timestamp.isoformat()),
        )
        await self.db.commit()

    async def mark_delivered(self, message_id: str) -> None:
        await self.db.execute(
            "UPDATE messages SET delivered = 1, status = ? WHERE id = ?",
            (DeliveryStatus.DELIVERED.value, message_id),
        )
        await self.db.execute("DELETE FROM outbox WHERE message_id = ?", (message_id,))
        await self.db.commit()

    async def mark_sent(self, message_id: str, stanza_id: str | None = None) -> None:
        await self.db.execute(
            "UPDATE messages SET status = ?, stanza_id = COALESCE(?, stanza_id) WHERE id = ?",
            (DeliveryStatus.SENT.value, stanza_id, message_id),
        )
        await self.db.commit()

    async def get_pending_outbox(self, chat_id: str | None = None) -> list[Message]:
        query = """
            SELECT m.* FROM outbox o
            JOIN messages m ON m.id = o.message_id
        """
        params: list = []
        if chat_id:
            query += " WHERE o.chat_id = ?"
            params.append(chat_id)
        query += " ORDER BY o.created_at ASC"
        rows = await self.db.execute_fetchall(query, params)
        return [self._row_to_message(row) for row in rows]

    async def pending_outbox_count(self) -> int:
        row = await self.db.execute_fetchall("SELECT COUNT(*) AS c FROM outbox")
        return int(row[0]["c"]) if row else 0

    async def save_chat(self, session: ChatSession) -> ChatSession:
        await self.db.execute(
            """
            INSERT OR REPLACE INTO chats (chat_id, contact_id, remote_jid, transport, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.chat_id,
                session.contact_id,
                session.remote_jid,
                session.transport,
                int(session.active),
                session.created_at.isoformat(),
            ),
        )
        await self.db.commit()
        return session

    async def get_chat(self, chat_id: str) -> ChatSession | None:
        rows = await self.db.execute_fetchall("SELECT * FROM chats WHERE chat_id = ?", (chat_id,))
        if not rows:
            return None
        row = rows[0]
        return ChatSession(
            chat_id=row["chat_id"],
            contact_id=row["contact_id"],
            remote_jid=row["remote_jid"],
            transport=row["transport"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def list_active_chats(self) -> list[ChatSession]:
        rows = await self.db.execute_fetchall("SELECT * FROM chats WHERE active = 1")
        return [
            ChatSession(
                chat_id=row["chat_id"],
                contact_id=row["contact_id"],
                remote_jid=row["remote_jid"],
                transport=row["transport"],
                active=bool(row["active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    async def save_presence(self, contact_id: str, show: str, status: str = "") -> None:
        now = datetime.now(UTC).isoformat()
        await self.db.execute(
            """
            INSERT OR REPLACE INTO presence (contact_id, show, status, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (contact_id, show, status, now),
        )
        await self.db.commit()

    async def get_presence(self, contact_id: str) -> tuple[str, str]:
        rows = await self.db.execute_fetchall(
            "SELECT show, status FROM presence WHERE contact_id = ?", (contact_id,)
        )
        if not rows:
            return "offline", ""
        return rows[0]["show"], rows[0]["status"]

    async def save_sync_pending(
        self,
        pending_id: str,
        *,
        from_jid: str,
        action: str,
        contact_id: str,
        payload: dict,
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO addressbook_sync_pending (id, from_jid, action, contact_id, payload, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                pending_id,
                from_jid,
                action,
                contact_id,
                json.dumps(payload),
                datetime.now(UTC).isoformat(),
            ),
        )
        await self.db.commit()

    async def list_sync_pending(self) -> list[AddressBookSyncPending]:
        rows = await self.db.execute_fetchall(
            "SELECT * FROM addressbook_sync_pending ORDER BY received_at ASC"
        )
        return [self._row_to_sync_pending(row) for row in rows]

    async def get_sync_pending(self, pending_id: str) -> AddressBookSyncPending | None:
        rows = await self.db.execute_fetchall(
            "SELECT * FROM addressbook_sync_pending WHERE id = ?", (pending_id,)
        )
        if not rows:
            return None
        return self._row_to_sync_pending(rows[0])

    async def delete_sync_pending(self, pending_id: str) -> None:
        await self.db.execute("DELETE FROM addressbook_sync_pending WHERE id = ?", (pending_id,))
        await self.db.commit()

    def _row_to_sync_pending(self, row: aiosqlite.Row) -> AddressBookSyncPending:
        return AddressBookSyncPending(
            id=row["id"],
            from_jid=row["from_jid"],
            action=row["action"],
            contact_id=row["contact_id"],
            payload=json.loads(row["payload"]),
            received_at=datetime.fromisoformat(row["received_at"]),
        )

    def _row_to_message(self, row: aiosqlite.Row) -> Message:
        raw = json.loads(row["raw_stanza"]) if row["raw_stanza"] else None
        return Message(
            id=row["id"],
            chat_id=row["chat_id"],
            direction=MessageDirection(row["direction"]),
            body=row["body"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            stanza_id=row["stanza_id"],
            delivered=bool(row["delivered"]),
            read=bool(row["read_flag"]),
            status=DeliveryStatus(row["status"]),
            raw_stanza=raw,
        )

    @staticmethod
    def new_message_id() -> str:
        return str(uuid4())
