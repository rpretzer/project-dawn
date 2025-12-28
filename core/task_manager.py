"""
Task management for agent orchestration.

This is the backbone for "agentic" behavior: tasks are persisted, can be
delegated/spawned, and stream progress events to UIs.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

logger = logging.getLogger(__name__)

TaskStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


@dataclass(frozen=True)
class Task:
    id: str
    room: str
    created_by: str  # user id or "system"
    requested_by_name: str
    assigned_to: str  # agent id
    title: str
    prompt: str
    status: TaskStatus
    result: Optional[str]
    error: Optional[str]
    parent_task_id: Optional[str]
    created_at_ts: float
    updated_at_ts: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "room": self.room,
            "created_by": self.created_by,
            "requested_by_name": self.requested_by_name,
            "assigned_to": self.assigned_to,
            "title": self.title,
            "prompt": self.prompt,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "parent_task_id": self.parent_task_id,
            "created_at_ts": self.created_at_ts,
            "updated_at_ts": self.updated_at_ts,
        }


@dataclass(frozen=True)
class TaskEvent:
    id: int
    task_id: str
    event_type: str  # created|started|progress|tool|completed|failed|cancelled
    payload: Dict[str, Any]
    created_at_ts: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at_ts": self.created_at_ts,
        }


class TaskStore:
    """SQLite task/event store."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/tasks.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    room TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    requested_by_name TEXT NOT NULL,
                    assigned_to TEXT NOT NULL,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    parent_task_id TEXT,
                    created_at_ts REAL NOT NULL,
                    updated_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_room_time ON tasks(room, created_at_ts DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assignee_time ON tasks(assigned_to, created_at_ts DESC)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id, id)")
            conn.commit()

    def create_task(
        self,
        *,
        room: str,
        created_by: str,
        requested_by_name: str,
        assigned_to: str,
        title: str,
        prompt: str,
        parent_task_id: Optional[str] = None,
    ) -> Task:
        now = time.time()
        task_id = f"tsk_{uuid.uuid4().hex[:12]}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tasks
                (id, room, created_by, requested_by_name, assigned_to, title, prompt, status, result, error, parent_task_id, created_at_ts, updated_at_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    room,
                    created_by,
                    requested_by_name,
                    assigned_to,
                    title,
                    prompt,
                    "queued",
                    None,
                    None,
                    parent_task_id,
                    now,
                    now,
                ),
            )
            conn.commit()

        task = self.get_task(task_id)
        if task:
            self.append_event(task_id, "created", {"title": title, "assigned_to": assigned_to})
            return task
        raise RuntimeError("failed_to_create_task")

    def get_task(self, task_id: str) -> Optional[Task]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cur.fetchone()
        if not row:
            return None
        return Task(
            id=str(row["id"]),
            room=str(row["room"]),
            created_by=str(row["created_by"]),
            requested_by_name=str(row["requested_by_name"]),
            assigned_to=str(row["assigned_to"]),
            title=str(row["title"]),
            prompt=str(row["prompt"]),
            status=str(row["status"]),  # type: ignore[assignment]
            result=(str(row["result"]) if row["result"] is not None else None),
            error=(str(row["error"]) if row["error"] is not None else None),
            parent_task_id=(str(row["parent_task_id"]) if row["parent_task_id"] is not None else None),
            created_at_ts=float(row["created_at_ts"]),
            updated_at_ts=float(row["updated_at_ts"]),
        )

    def list_recent(self, *, room: Optional[str] = None, limit: int = 50) -> List[Task]:
        limit = max(1, min(int(limit), 200))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if room:
                cur = conn.execute(
                    "SELECT * FROM tasks WHERE room = ? ORDER BY created_at_ts DESC LIMIT ?",
                    (room, limit),
                )
            else:
                cur = conn.execute("SELECT * FROM tasks ORDER BY created_at_ts DESC LIMIT ?", (limit,))
            rows = list(cur.fetchall())
        return [self.get_task(str(r["id"])) for r in rows if r and r.get("id")]  # type: ignore[arg-type]

    def update_status(self, task_id: str, status: TaskStatus, *, result: Optional[str] = None, error: Optional[str] = None) -> Optional[Task]:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, result = COALESCE(?, result), error = COALESCE(?, error), updated_at_ts = ?
                WHERE id = ?
                """,
                (status, result, error, now, task_id),
            )
            conn.commit()
        return self.get_task(task_id)

    def append_event(self, task_id: str, event_type: str, payload: Dict[str, Any]) -> TaskEvent:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO task_events (task_id, event_type, payload, created_at_ts) VALUES (?, ?, ?, ?)",
                (task_id, event_type, json.dumps(payload, ensure_ascii=False), now),
            )
            event_id = int(cur.lastrowid)
            conn.commit()
        return TaskEvent(id=event_id, task_id=task_id, event_type=event_type, payload=payload, created_at_ts=now)

    def get_events(self, task_id: str, *, after_id: int = 0, limit: int = 200) -> List[TaskEvent]:
        limit = max(1, min(int(limit), 1000))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT id, task_id, event_type, payload, created_at_ts
                FROM task_events
                WHERE task_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (task_id, int(after_id), limit),
            )
            rows = list(cur.fetchall())
        events: List[TaskEvent] = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except Exception:
                payload = {"raw": r["payload"]}
            events.append(
                TaskEvent(
                    id=int(r["id"]),
                    task_id=str(r["task_id"]),
                    event_type=str(r["event_type"]),
                    payload=payload,
                    created_at_ts=float(r["created_at_ts"]),
                )
            )
        return events

