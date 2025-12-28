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
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/ops.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
        return OpsEvent(id=event_id, event_type=str(event_type), payload=payload_obj, created_at_ts=now)

    def list_recent(self, *, limit: int = 200) -> List[OpsEvent]:
        limit = max(1, min(int(limit), 1000))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = list(
                conn.execute(
                    """
                    SELECT id, event_type, payload_json, created_at_ts
                    FROM ops_events
                    ORDER BY created_at_ts DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            )
        out: List[OpsEvent] = []
        for r in rows:
            try:
                payload = json.loads(r["payload_json"])
            except Exception:
                payload = {"raw": r["payload_json"]}
            out.append(OpsEvent(id=int(r["id"]), event_type=str(r["event_type"]), payload=payload, created_at_ts=float(r["created_at_ts"])))
        return out

