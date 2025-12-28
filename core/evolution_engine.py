"""
Practical evolution engine for agents.

This is *not* about evolving model weights. It evolves measurable behavior knobs:
- planning budget (steps/tool calls)
- timeouts
- delegation tendency
- verbosity

Fitness is computed from recent task outcomes + user ratings.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.agent_policy import AgentPolicy, PolicyStore
from core.task_manager import TaskStore, Task


@dataclass(frozen=True)
class FitnessReport:
    agent_id: str
    window_tasks: int
    completed: int
    failed: int
    avg_rating: Optional[float]
    median_duration_s: Optional[float]
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "window_tasks": self.window_tasks,
            "completed": self.completed,
            "failed": self.failed,
            "avg_rating": self.avg_rating,
            "median_duration_s": self.median_duration_s,
            "score": self.score,
        }


class EvolutionEngine:
    def __init__(
        self,
        *,
        task_store: TaskStore,
        policy_store: PolicyStore,
        window_tasks: int = 20,
    ):
        self.task_store = task_store
        self.policy_store = policy_store
        self.window_tasks = max(5, min(int(window_tasks), 200))

        # Mutation bounds (safety)
        self.bounds = {
            "max_plan_steps": (3, 14),
            "max_tool_calls": (4, 30),
            "step_timeout_seconds": (10.0, 120.0),
            "delegation_bias": (0.0, 1.0),
        }
        self.verbosity_levels = ["concise", "balanced", "verbose"]

    def _clamp_int(self, v: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, int(v)))

    def _clamp_float(self, v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, float(v)))

    def _get_latest_rating(self, task_id: str) -> Optional[int]:
        # Scan events for the latest rating.
        events = self.task_store.get_events(task_id, after_id=0, limit=1000)
        latest: Optional[int] = None
        for e in events:
            if e.event_type == "rating":
                try:
                    latest = int(e.payload.get("rating"))
                except Exception:
                    continue
        if latest is None:
            return None
        if 1 <= latest <= 5:
            return latest
        return None

    def _list_recent_tasks_for_agent(self, agent_id: str, *, since_ts: Optional[float] = None) -> List[Task]:
        return self.task_store.list_recent_for_agent(
            assigned_to=str(agent_id),
            since_ts=since_ts,
            limit=self.window_tasks,
        )

    def evaluate_agent(self, agent_id: str, *, since_ts: Optional[float] = None) -> FitnessReport:
        tasks = self._list_recent_tasks_for_agent(agent_id, since_ts=since_ts)
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")

        durations: List[float] = []
        ratings: List[int] = []
        for t in tasks:
            # duration: only meaningful for completed/failed/running that have updates
            if t.updated_at_ts and t.created_at_ts and t.updated_at_ts >= t.created_at_ts:
                durations.append(float(t.updated_at_ts - t.created_at_ts))
            r = self._get_latest_rating(t.id)
            if r is not None:
                ratings.append(r)

        avg_rating = (sum(ratings) / len(ratings)) if ratings else None
        median_duration = statistics.median(durations) if durations else None

        # Score composition:
        # - success rate (40%)
        # - rating (40%) (if absent, assume neutral 3.0)
        # - speed (20%) (median duration; shorter => higher)
        total_done = completed + failed
        success_rate = (completed / total_done) if total_done > 0 else 0.0
        rating_norm = ((avg_rating if avg_rating is not None else 3.0) / 5.0)

        if median_duration is None:
            speed_score = 0.5
        else:
            # 0s => ~1.0, 120s => ~0.5, 600s => ~0.17
            speed_score = 1.0 / (1.0 + (median_duration / 120.0))

        score = 0.4 * success_rate + 0.4 * rating_norm + 0.2 * speed_score
        return FitnessReport(
            agent_id=agent_id,
            window_tasks=len(tasks),
            completed=completed,
            failed=failed,
            avg_rating=avg_rating,
            median_duration_s=median_duration,
            score=float(score),
        )

    def propose_mutation(self, policy: AgentPolicy, report: FitnessReport) -> AgentPolicy:
        # Heuristic mutation based on observed pain:
        # - Low success => increase tool budget slightly, maybe increase timeout
        # - Slow => reduce plan steps (less thrash) and increase delegation slightly
        # - Low ratings => adjust verbosity (try balanced)
        max_steps = policy.max_plan_steps
        max_tools = policy.max_tool_calls
        timeout = policy.step_timeout_seconds
        delegation = policy.delegation_bias
        verbosity = policy.verbosity

        # Random exploration
        explore = random.random() < 0.25

        success_rate = (report.completed / max(1, report.completed + report.failed))

        if explore:
            max_steps += random.choice([-1, 0, 1])
            max_tools += random.choice([-2, 0, 2])
            timeout += random.choice([-5.0, 0.0, 5.0, 10.0])
            delegation += random.choice([-0.1, 0.0, 0.1])
            if random.random() < 0.3:
                verbosity = random.choice(self.verbosity_levels)
        else:
            if success_rate < 0.6:
                max_tools += 2
                timeout += 10.0
            if report.median_duration_s is not None and report.median_duration_s > 180:
                delegation += 0.1
                max_steps -= 1
            if report.avg_rating is not None and report.avg_rating < 3.5:
                verbosity = "balanced"

        max_steps = self._clamp_int(max_steps, *self.bounds["max_plan_steps"])
        max_tools = self._clamp_int(max_tools, *self.bounds["max_tool_calls"])
        timeout = self._clamp_float(timeout, *self.bounds["step_timeout_seconds"])
        delegation = self._clamp_float(delegation, *self.bounds["delegation_bias"])
        if verbosity not in self.verbosity_levels:
            verbosity = "concise"

        return AgentPolicy(
            agent_id=policy.agent_id,
            max_plan_steps=max_steps,
            max_tool_calls=max_tools,
            step_timeout_seconds=timeout,
            delegation_bias=delegation,
            verbosity=verbosity,
        )

    def evolve_agent(self, agent_id: str) -> Tuple[FitnessReport, AgentPolicy, AgentPolicy]:
        """
        Evaluate current fitness and apply a mutated policy.
        Returns (fitness_report, old_policy, new_policy).
        """
        report = self.evaluate_agent(agent_id)
        old = self.policy_store.get_policy(agent_id)
        new = self.propose_mutation(old, report)
        self.policy_store.set_policy(new)
        return report, old, new

