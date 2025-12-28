"""
Agent policy configuration + lightweight evolution hooks.

This is intentionally practical: policies tune how an agent plans/acts inside the
orchestrator, and can be evolved based on outcomes (task completion + ratings).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AgentPolicy:
    agent_id: str
    max_plan_steps: int = 8
    max_tool_calls: int = 12
    step_timeout_seconds: float = 30.0
    delegation_bias: float = 0.35  # 0..1 (higher => more delegation)
    verbosity: str = "concise"  # concise|balanced|verbose
    updated_at_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "max_plan_steps": self.max_plan_steps,
            "max_tool_calls": self.max_tool_calls,
            "step_timeout_seconds": self.step_timeout_seconds,
            "delegation_bias": self.delegation_bias,
            "verbosity": self.verbosity,
            "updated_at_ts": self.updated_at_ts,
        }


class PolicyStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data/policies.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_policies (
                    agent_id TEXT PRIMARY KEY,
                    policy_json TEXT NOT NULL,
                    updated_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_policy_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    policy_json TEXT NOT NULL,
                    created_at_ts REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_history_agent_time ON agent_policy_history(agent_id, created_at_ts DESC)")
            conn.commit()

    def get_policy(self, agent_id: str) -> AgentPolicy:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT policy_json, updated_at_ts FROM agent_policies WHERE agent_id = ?",
                (str(agent_id),),
            ).fetchone()
        if not row:
            return AgentPolicy(agent_id=str(agent_id), updated_at_ts=0.0)
        data = json.loads(row[0])
        return AgentPolicy(
            agent_id=str(agent_id),
            max_plan_steps=int(data.get("max_plan_steps", 8)),
            max_tool_calls=int(data.get("max_tool_calls", 12)),
            step_timeout_seconds=float(data.get("step_timeout_seconds", 30.0)),
            delegation_bias=float(data.get("delegation_bias", 0.35)),
            verbosity=str(data.get("verbosity", "concise")),
            updated_at_ts=float(row[1] or 0.0),
        )

    def set_policy(self, policy: AgentPolicy) -> None:
        now = time.time()
        payload = policy.to_dict()
        payload["updated_at_ts"] = now
        with sqlite3.connect(self.db_path) as conn:
            # Always keep an append-only history for rollback/debugging.
            conn.execute(
                "INSERT INTO agent_policy_history (agent_id, policy_json, created_at_ts) VALUES (?, ?, ?)",
                (policy.agent_id, json.dumps(payload, ensure_ascii=False), now),
            )
            conn.execute(
                """
                INSERT INTO agent_policies (agent_id, policy_json, updated_at_ts)
                VALUES (?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    policy_json=excluded.policy_json,
                    updated_at_ts=excluded.updated_at_ts
                """,
                (policy.agent_id, json.dumps(payload, ensure_ascii=False), now),
            )
            conn.commit()

    def list_history(self, agent_id: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = list(
                conn.execute(
                    """
                    SELECT id, agent_id, policy_json, created_at_ts
                    FROM agent_policy_history
                    WHERE agent_id = ?
                    ORDER BY created_at_ts DESC, id DESC
                    LIMIT ?
                    """,
                    (str(agent_id), limit),
                ).fetchall()
            )
        out: List[Dict[str, Any]] = []
        for r in rows:
            try:
                data = json.loads(r["policy_json"])
            except Exception:
                data = {"raw": r["policy_json"]}
            out.append(
                {
                    "id": int(r["id"]),
                    "agent_id": str(r["agent_id"]),
                    "created_at_ts": float(r["created_at_ts"]),
                    "policy": data,
                }
            )
        return out

    def rollback_to_history_id(self, agent_id: str, history_id: int) -> AgentPolicy:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT policy_json
                FROM agent_policy_history
                WHERE agent_id = ? AND id = ?
                """,
                (str(agent_id), int(history_id)),
            ).fetchone()
        if not row:
            raise KeyError("unknown_history_id")
        data = json.loads(row[0])
        p = AgentPolicy(
            agent_id=str(agent_id),
            max_plan_steps=int(data.get("max_plan_steps", 8)),
            max_tool_calls=int(data.get("max_tool_calls", 12)),
            step_timeout_seconds=float(data.get("step_timeout_seconds", 30.0)),
            delegation_bias=float(data.get("delegation_bias", 0.35)),
            verbosity=str(data.get("verbosity", "concise")),
            updated_at_ts=float(data.get("updated_at_ts") or 0.0),
        )
        # Re-save as "current" (also appends to history)
        self.set_policy(p)
        return self.get_policy(agent_id)

