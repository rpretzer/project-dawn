"""
Moderation and room policy storage for realtime chat.

Keeps persistent bans/mutes and per-room settings in SQLite.
"""

from __future__ import annotations

import sqlite3
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.db_migrations import ensure_schema

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ban:
    kind: str  # "user" | "ip"
    value: str
    reason: str
    created_at_ts: float
    expires_at_ts: Optional[float]

    def active(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        if self.expires_at_ts is None:
            return True
        return now < self.expires_at_ts


@dataclass(frozen=True)
class Mute:
    user_id: str
    room: str
    reason: str
    created_at_ts: float
    expires_at_ts: Optional[float]

    def active(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        if self.expires_at_ts is None:
            return True
        return now < self.expires_at_ts


class ModerationStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/moderation.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            ensure_schema(conn, schema_name="moderation_store", target_version=1)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bans (
                    kind TEXT NOT NULL,
                    value TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at_ts REAL NOT NULL,
                    expires_at_ts REAL,
                    PRIMARY KEY (kind, value)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bans_expires ON bans(expires_at_ts)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mutes (
                    user_id TEXT NOT NULL,
                    room TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at_ts REAL NOT NULL,
                    expires_at_ts REAL,
                    PRIMARY KEY (user_id, room)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mutes_expires ON mutes(expires_at_ts)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS room_settings (
                    room TEXT PRIMARY KEY,
                    allow_guests INTEGER NOT NULL DEFAULT 0,
                    read_only INTEGER NOT NULL DEFAULT 0,
                    created_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS moderation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    actor_user_id TEXT,
                    actor_name TEXT,
                    actor_ip TEXT,
                    room TEXT,
                    target TEXT,
                    reason TEXT,
                    created_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_moderation_events_time ON moderation_events(created_at_ts DESC)")
            conn.commit()

    def audit(
        self,
        *,
        action: str,
        actor_user_id: Optional[str],
        actor_name: Optional[str],
        actor_ip: Optional[str],
        room: Optional[str],
        target: Optional[str],
        reason: Optional[str],
    ) -> None:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO moderation_events
                (action, actor_user_id, actor_name, actor_ip, room, target, reason, created_at_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (action, actor_user_id, actor_name, actor_ip, room, target, reason, now),
            )
            conn.commit()

    def list_events(self, *, limit: int = 100, room: Optional[str] = None) -> list[Dict[str, Any]]:
        """
        Return recent moderation events (includes patch audit actions).
        """
        limit = max(1, min(int(limit), 500))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if room:
                rows = list(
                    conn.execute(
                        """
                        SELECT id, action, actor_user_id, actor_name, actor_ip, room, target, reason, created_at_ts
                        FROM moderation_events
                        WHERE room = ?
                        ORDER BY created_at_ts DESC, id DESC
                        LIMIT ?
                        """,
                        (str(room), limit),
                    ).fetchall()
                )
            else:
                rows = list(
                    conn.execute(
                        """
                        SELECT id, action, actor_user_id, actor_name, actor_ip, room, target, reason, created_at_ts
                        FROM moderation_events
                        ORDER BY created_at_ts DESC, id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                )
        out: list[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": int(r["id"]),
                    "action": str(r["action"]),
                    "actor_user_id": (str(r["actor_user_id"]) if r["actor_user_id"] is not None else None),
                    "actor_name": (str(r["actor_name"]) if r["actor_name"] is not None else None),
                    "actor_ip": (str(r["actor_ip"]) if r["actor_ip"] is not None else None),
                    "room": (str(r["room"]) if r["room"] is not None else None),
                    "target": (str(r["target"]) if r["target"] is not None else None),
                    "reason": (str(r["reason"]) if r["reason"] is not None else None),
                    "created_at_ts": float(r["created_at_ts"]),
                }
            )
        return out

    def get_room_settings(self, room: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM room_settings WHERE room = ?", (room,)).fetchone()
        if not row:
            return {"allow_guests": False, "read_only": False}
        return {"allow_guests": bool(row["allow_guests"]), "read_only": bool(row["read_only"])}

    def set_room_settings(self, room: str, *, allow_guests: Optional[bool] = None, read_only: Optional[bool] = None) -> None:
        current = self.get_room_settings(room)
        allow_guests_val = int(current["allow_guests"] if allow_guests is None else bool(allow_guests))
        read_only_val = int(current["read_only"] if read_only is None else bool(read_only))
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO room_settings (room, allow_guests, read_only, created_at_ts)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(room) DO UPDATE SET
                    allow_guests=excluded.allow_guests,
                    read_only=excluded.read_only
                """,
                (room, allow_guests_val, read_only_val, now),
            )
            conn.commit()

    def set_ban(self, *, kind: str, value: str, reason: str, duration_seconds: Optional[int] = None) -> None:
        now = time.time()
        expires = (now + duration_seconds) if duration_seconds else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO bans (kind, value, reason, created_at_ts, expires_at_ts)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(kind, value) DO UPDATE SET
                    reason=excluded.reason,
                    created_at_ts=excluded.created_at_ts,
                    expires_at_ts=excluded.expires_at_ts
                """,
                (kind, value, reason, now, expires),
            )
            conn.commit()

    def clear_ban(self, *, kind: str, value: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM bans WHERE kind = ? AND value = ?", (kind, value))
            conn.commit()

    def get_ban(self, *, kind: str, value: str) -> Optional[Ban]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM bans WHERE kind = ? AND value = ?", (kind, value)).fetchone()
        if not row:
            return None
        return Ban(
            kind=str(row["kind"]),
            value=str(row["value"]),
            reason=str(row["reason"]),
            created_at_ts=float(row["created_at_ts"]),
            expires_at_ts=(float(row["expires_at_ts"]) if row["expires_at_ts"] is not None else None),
        )

    def is_banned(self, *, user_id: Optional[str], ip: Optional[str]) -> Tuple[bool, Optional[str]]:
        now = time.time()
        if user_id:
            ban = self.get_ban(kind="user", value=str(user_id))
            if ban and ban.active(now):
                return True, ban.reason
        if ip:
            ban = self.get_ban(kind="ip", value=str(ip))
            if ban and ban.active(now):
                return True, ban.reason
        return False, None

    def set_mute(self, *, user_id: str, room: str, reason: str, duration_seconds: Optional[int] = None) -> None:
        now = time.time()
        expires = (now + duration_seconds) if duration_seconds else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO mutes (user_id, room, reason, created_at_ts, expires_at_ts)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, room) DO UPDATE SET
                    reason=excluded.reason,
                    created_at_ts=excluded.created_at_ts,
                    expires_at_ts=excluded.expires_at_ts
                """,
                (str(user_id), str(room), reason, now, expires),
            )
            conn.commit()

    def clear_mute(self, *, user_id: str, room: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM mutes WHERE user_id = ? AND room = ?", (str(user_id), str(room)))
            conn.commit()

    def get_mute(self, *, user_id: str, room: str) -> Optional[Mute]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM mutes WHERE user_id = ? AND room = ?", (str(user_id), str(room))).fetchone()
        if not row:
            return None
        return Mute(
            user_id=str(row["user_id"]),
            room=str(row["room"]),
            reason=str(row["reason"]),
            created_at_ts=float(row["created_at_ts"]),
            expires_at_ts=(float(row["expires_at_ts"]) if row["expires_at_ts"] is not None else None),
        )

    def is_muted(self, *, user_id: Optional[str], room: str) -> Tuple[bool, Optional[str]]:
        if not user_id:
            return False, None
        now = time.time()
        mute = self.get_mute(user_id=str(user_id), room=str(room))
        if mute and mute.active(now):
            return True, mute.reason
        return False, None

