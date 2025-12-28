"""
Operational event log (optional).

This is a lightweight, queryable store for runtime events:
- HTTP request logs (optional)
- WS actions (create_task/rate_task/patch actions, etc.)
- server errors

Use cases: incident review, debugging, basic audit trail beyond chat messages.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.db_migrations import ensure_schema


@dataclass(frozen=True)
class OpsEvent:
    id: int
    event_type: str
    payload: Dict[str, Any]
    created_at_ts: float

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "event_type": self.event_type, "payload": self.payload, "created_at_ts": self.created_at_ts}


class OpsLogStore:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        *,
        retention_days: Optional[int] = None,
        max_events: Optional[int] = None,
    ):
        self.db_path = db_path or Path("data/ops.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days = int(retention_days) if retention_days is not None else None
        self.max_events = int(max_events) if max_events is not None else None
        self._append_count = 0
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            ensure_schema(conn, schema_name="ops_log_store", target_version=1)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ops_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ops_events_time ON ops_events(created_at_ts DESC)")
            conn.commit()

    def _prune_if_needed(self) -> None:
        # Prune occasionally to avoid write amplification.
        self._append_count += 1
        if self._append_count % 25 != 0:
            return

        with sqlite3.connect(self.db_path) as conn:
            if self.retention_days and self.retention_days > 0:
                cutoff = time.time() - float(self.retention_days) * 86400.0
                conn.execute("DELETE FROM ops_events WHERE created_at_ts < ?", (float(cutoff),))
            if self.max_events and self.max_events > 0:
                # Keep newest max_events by id.
                conn.execute(
                    """
                    DELETE FROM ops_events
                    WHERE id NOT IN (
                        SELECT id FROM ops_events ORDER BY id DESC LIMIT ?
                    )
                    """,
                    (int(self.max_events),),
                )
            conn.commit()

    def append(self, event_type: str, payload: Dict[str, Any]) -> OpsEvent:
        now = time.time()
        # Keep payload bounded (best-effort).
        raw = json.dumps(payload or {}, ensure_ascii=False)
        if len(raw) > 50_000:
            raw = raw[:50_000]
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO ops_events (event_type, payload_json, created_at_ts) VALUES (?, ?, ?)",
                (str(event_type), raw, float(now)),
            )
            event_id = int(cur.lastrowid)
            conn.commit()
        try:
            payload_obj = json.loads(raw)
        except Exception:
            payload_obj = {"raw": raw}
        self._prune_if_needed()
        return OpsEvent(id=event_id, event_type=str(event_type), payload=payload_obj, created_at_ts=now)

    def list_recent(
        self,
        *,
        limit: int = 200,
        event_type: Optional[str] = None,
        room: Optional[str] = None,
    ) -> List[OpsEvent]:
        limit = max(1, min(int(limit), 1000))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            where = []
            args: List[Any] = []
            if event_type:
                where.append("event_type = ?")
                args.append(str(event_type))
            if room:
                # Best-effort filter: payload is JSON text; this is a cheap contains filter.
                where.append("payload_json LIKE ?")
                args.append(f'%\"room\": \"{str(room)}\"%')
            sql = """
                SELECT id, event_type, payload_json, created_at_ts
                FROM ops_events
            """
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY created_at_ts DESC, id DESC LIMIT ?"
            args.append(limit)
            rows = list(conn.execute(sql, tuple(args)).fetchall())
        out: List[OpsEvent] = []
        for r in rows:
            try:
                payload = json.loads(r["payload_json"])
            except Exception:
                payload = {"raw": r["payload_json"]}
            out.append(OpsEvent(id=int(r["id"]), event_type=str(r["event_type"]), payload=payload, created_at_ts=float(r["created_at_ts"])))
        return out

