"""
Chat storage for Project Dawn.

Provides persistent room history and basic moderation metadata.
"""

from __future__ import annotations

import sqlite3
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.db_migrations import ensure_schema

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatMessage:
    id: int
    room: str
    sender_type: str  # "human" | "agent" | "system" | "guest"
    sender_id: Optional[str]  # user_id or agent_id; None for system
    sender_name: str
    content: str
    created_at_ts: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "room": self.room,
            "sender_type": self.sender_type,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "content": self.content,
            "created_at_ts": self.created_at_ts,
        }


class ChatStore:
    """SQLite-backed chat log."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/chat.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            ensure_schema(conn, schema_name="chat_store", target_version=1)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS room_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL,
                    sender_type TEXT NOT NULL,
                    sender_id TEXT,
                    sender_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_room_messages_room_id ON room_messages(room, id)")
            conn.commit()

    def append_message(
        self,
        *,
        room: str,
        sender_type: str,
        sender_id: Optional[str],
        sender_name: str,
        content: str,
        created_at_ts: float,
    ) -> ChatMessage:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO room_messages (room, sender_type, sender_id, sender_name, content, created_at_ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (room, sender_type, sender_id, sender_name, content, created_at_ts),
            )
            msg_id = int(cur.lastrowid)
            conn.commit()

        return ChatMessage(
            id=msg_id,
            room=room,
            sender_type=sender_type,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            created_at_ts=created_at_ts,
        )

    def get_recent(self, *, room: str, limit: int = 200) -> List[ChatMessage]:
        limit = max(1, min(int(limit), 2000))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT id, room, sender_type, sender_id, sender_name, content, created_at_ts
                FROM room_messages
                WHERE room = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (room, limit),
            )
            rows = list(cur.fetchall())

        # Return ascending order for clients.
        rows.reverse()
        return [
            ChatMessage(
                id=int(r["id"]),
                room=str(r["room"]),
                sender_type=str(r["sender_type"]),
                sender_id=(str(r["sender_id"]) if r["sender_id"] is not None else None),
                sender_name=str(r["sender_name"]),
                content=str(r["content"]),
                created_at_ts=float(r["created_at_ts"]),
            )
            for r in rows
        ]

