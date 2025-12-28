"""
Evolution experiment manager.

Purpose: make evolution safe and observable.

We track each policy mutation as an "experiment":
- baseline fitness score before mutation
- mutated policy applied
- after enough *new* tasks, re-score
- accept if improved / stable, rollback if regressed beyond a threshold
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.agent_policy import AgentPolicy, PolicyStore
from core.evolution_engine import EvolutionEngine, FitnessReport
from core.task_manager import TaskStore


ExperimentStatus = str  # pending|accepted|rolled_back


@dataclass(frozen=True)
class EvolutionExperiment:
    id: int
    agent_id: str
    baseline_score: float
    baseline_window_tasks: int
    start_ts: float
    min_tasks_after: int
    old_policy_history_id: int
    new_policy_history_id: int
    status: ExperimentStatus
    evaluated_at_ts: Optional[float]
    new_score: Optional[float]
    decision: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "baseline_score": self.baseline_score,
            "baseline_window_tasks": self.baseline_window_tasks,
            "start_ts": self.start_ts,
            "min_tasks_after": self.min_tasks_after,
            "old_policy_history_id": self.old_policy_history_id,
            "new_policy_history_id": self.new_policy_history_id,
            "status": self.status,
            "evaluated_at_ts": self.evaluated_at_ts,
            "new_score": self.new_score,
            "decision": self.decision,
        }


class EvolutionManager:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        policy_store: PolicyStore,
        evolution_engine: EvolutionEngine,
        db_path: Optional[Path] = None,
    ):
        self.task_store = task_store
        self.policy_store = policy_store
        self.engine = evolution_engine
        self.db_path = db_path or Path("data/evolution.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evolution_experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    baseline_score REAL NOT NULL,
                    baseline_window_tasks INTEGER NOT NULL,
                    start_ts REAL NOT NULL,
                    min_tasks_after INTEGER NOT NULL,
                    old_policy_history_id INTEGER NOT NULL,
                    new_policy_history_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    evaluated_at_ts REAL,
                    new_score REAL,
                    decision TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evo_agent_status ON evolution_experiments(agent_id, status, id DESC)")
            conn.commit()

    def _row_to_exp(self, r: sqlite3.Row) -> EvolutionExperiment:
        return EvolutionExperiment(
            id=int(r["id"]),
            agent_id=str(r["agent_id"]),
            baseline_score=float(r["baseline_score"]),
            baseline_window_tasks=int(r["baseline_window_tasks"]),
            start_ts=float(r["start_ts"]),
            min_tasks_after=int(r["min_tasks_after"]),
            old_policy_history_id=int(r["old_policy_history_id"]),
            new_policy_history_id=int(r["new_policy_history_id"]),
            status=str(r["status"]),
            evaluated_at_ts=(float(r["evaluated_at_ts"]) if r["evaluated_at_ts"] is not None else None),
            new_score=(float(r["new_score"]) if r["new_score"] is not None else None),
            decision=(str(r["decision"]) if r["decision"] is not None else None),
        )

    def list_experiments(self, agent_id: Optional[str] = None, *, limit: int = 20) -> List[EvolutionExperiment]:
        limit = max(1, min(int(limit), 200))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if agent_id:
                rows = list(
                    conn.execute(
                        """
                        SELECT * FROM evolution_experiments
                        WHERE agent_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                        """,
                        (str(agent_id), limit),
                    ).fetchall()
                )
            else:
                rows = list(
                    conn.execute(
                        "SELECT * FROM evolution_experiments ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                )
        return [self._row_to_exp(r) for r in rows]

    def has_pending(self, agent_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM evolution_experiments WHERE agent_id = ? AND status = 'pending' LIMIT 1",
                (str(agent_id),),
            ).fetchone()
        return bool(row)

    def start_experiment(
        self,
        *,
        agent_id: str,
        min_tasks_after: int = 5,
    ) -> EvolutionExperiment:
        agent_id = str(agent_id)
        if self.has_pending(agent_id):
            raise RuntimeError("experiment_already_pending")

        baseline: FitnessReport = self.engine.evaluate_agent(agent_id)
        old_policy: AgentPolicy = self.policy_store.get_policy(agent_id)
        old_hist_id = self.policy_store.set_policy(old_policy)  # snapshot

        mutated = self.engine.propose_mutation(old_policy, baseline)
        new_hist_id = self.policy_store.set_policy(mutated)

        start_ts = time.time()
        min_tasks_after = max(1, min(int(min_tasks_after), 50))
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO evolution_experiments
                (agent_id, baseline_score, baseline_window_tasks, start_ts, min_tasks_after, old_policy_history_id, new_policy_history_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    agent_id,
                    float(baseline.score),
                    int(baseline.window_tasks),
                    float(start_ts),
                    int(min_tasks_after),
                    int(old_hist_id),
                    int(new_hist_id),
                ),
            )
            exp_id = int(cur.lastrowid)
            conn.commit()

        exp = self.get_experiment(exp_id)
        if not exp:
            raise RuntimeError("failed_to_create_experiment")
        return exp

    def get_experiment(self, exp_id: int) -> Optional[EvolutionExperiment]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM evolution_experiments WHERE id = ?", (int(exp_id),)).fetchone()
        if not row:
            return None
        return self._row_to_exp(row)

    def _mark(self, exp_id: int, *, status: str, new_score: Optional[float], decision: str) -> EvolutionExperiment:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE evolution_experiments
                SET status = ?, evaluated_at_ts = ?, new_score = ?, decision = ?
                WHERE id = ?
                """,
                (str(status), float(now), (float(new_score) if new_score is not None else None), str(decision), int(exp_id)),
            )
            conn.commit()
        exp = self.get_experiment(exp_id)
        if not exp:
            raise RuntimeError("failed_to_update_experiment")
        return exp

    def check_pending_and_finalize(
        self,
        *,
        regression_threshold: float = 0.08,
        min_window_tasks: int = 3,
    ) -> List[EvolutionExperiment]:
        """
        Evaluate pending experiments that have enough new tasks; accept or rollback.
        """
        regression_threshold = float(regression_threshold)
        min_window_tasks = max(1, min(int(min_window_tasks), 50))
        finalized: List[EvolutionExperiment] = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = list(conn.execute("SELECT * FROM evolution_experiments WHERE status = 'pending' ORDER BY id ASC").fetchall())

        for r in rows:
            exp = self._row_to_exp(r)
            tasks_after = self.task_store.list_recent_for_agent(
                assigned_to=exp.agent_id,
                since_ts=exp.start_ts,
                limit=max(exp.min_tasks_after, 200),
            )
            # Wait until enough new tasks have happened.
            done_after = [t for t in tasks_after if t.status in ("completed", "failed")]
            if len(done_after) < exp.min_tasks_after:
                continue

            rep = self.engine.evaluate_agent(exp.agent_id, since_ts=exp.start_ts)
            # If too few tasks in-window, defer for stability.
            if rep.window_tasks < min_window_tasks:
                continue

            delta = float(rep.score) - float(exp.baseline_score)
            if delta < -abs(regression_threshold):
                # Roll back to the old policy snapshot.
                try:
                    self.policy_store.rollback_to_history_id(exp.agent_id, exp.old_policy_history_id)
                except Exception:
                    # If rollback fails, we still mark it (so it doesn't loop forever).
                    finalized.append(self._mark(exp.id, status="rolled_back", new_score=rep.score, decision="rollback_failed"))
                    continue
                finalized.append(self._mark(exp.id, status="rolled_back", new_score=rep.score, decision="regressed_rollback"))
            else:
                finalized.append(self._mark(exp.id, status="accepted", new_score=rep.score, decision="accepted"))
        return finalized

