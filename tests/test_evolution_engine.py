import sqlite3
import time
from pathlib import Path

from core.task_manager import TaskStore
from core.agent_policy import PolicyStore
from core.evolution_engine import EvolutionEngine


def _set_task_times(db_path: Path, task_id: str, *, created_at: float, updated_at: float) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET created_at_ts = ?, updated_at_ts = ? WHERE id = ?",
            (float(created_at), float(updated_at), str(task_id)),
        )
        conn.commit()


def test_fitness_scoring_uses_outcomes_ratings_and_speed(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    policies_db = tmp_path / "policies.db"
    ts = TaskStore(db_path=tasks_db)
    ps = PolicyStore(db_path=policies_db)
    eng = EvolutionEngine(task_store=ts, policy_store=ps, window_tasks=20)

    agent_id = "agent_001"
    now = time.time()

    # 3 completed tasks with good ratings, varying durations
    for i, dur in enumerate([5, 15, 60], start=1):
        t = ts.create_task(
            room="lobby",
            created_by="u1",
            requested_by_name="User",
            assigned_to=agent_id,
            title=f"t{i}",
            prompt="do work",
        )
        ts.update_status(t.id, "completed", result="ok")
        _set_task_times(tasks_db, t.id, created_at=now - dur, updated_at=now)
        ts.record_rating(t.id, rater_id="u1", rating=5, comment="great")

    # 1 failed task with low rating
    t_bad = ts.create_task(
        room="lobby",
        created_by="u1",
        requested_by_name="User",
        assigned_to=agent_id,
        title="bad",
        prompt="do work",
    )
    ts.update_status(t_bad.id, "failed", error="boom")
    _set_task_times(tasks_db, t_bad.id, created_at=now - 30, updated_at=now)
    ts.record_rating(t_bad.id, rater_id="u1", rating=1, comment="bad")

    rep = eng.evaluate_agent(agent_id)
    assert rep.agent_id == agent_id
    assert rep.window_tasks >= 4
    assert rep.completed == 3
    assert rep.failed == 1
    assert rep.avg_rating is not None
    assert 0.0 <= rep.score <= 1.0


def test_mutation_is_bounded(tmp_path: Path) -> None:
    ts = TaskStore(db_path=tmp_path / "tasks.db")
    ps = PolicyStore(db_path=tmp_path / "policies.db")
    eng = EvolutionEngine(task_store=ts, policy_store=ps, window_tasks=10)

    agent_id = "agent_002"
    rep = eng.evaluate_agent(agent_id)
    cur = ps.get_policy(agent_id)
    nxt = eng.propose_mutation(cur, rep)

    assert nxt.agent_id == agent_id
    assert eng.bounds["max_plan_steps"][0] <= nxt.max_plan_steps <= eng.bounds["max_plan_steps"][1]
    assert eng.bounds["max_tool_calls"][0] <= nxt.max_tool_calls <= eng.bounds["max_tool_calls"][1]
    assert eng.bounds["step_timeout_seconds"][0] <= nxt.step_timeout_seconds <= eng.bounds["step_timeout_seconds"][1]
    assert eng.bounds["delegation_bias"][0] <= nxt.delegation_bias <= eng.bounds["delegation_bias"][1]
    assert nxt.verbosity in eng.verbosity_levels


def test_evolve_agent_persists_policy(tmp_path: Path) -> None:
    ts = TaskStore(db_path=tmp_path / "tasks.db")
    ps = PolicyStore(db_path=tmp_path / "policies.db")
    eng = EvolutionEngine(task_store=ts, policy_store=ps, window_tasks=10)

    agent_id = "agent_003"
    # Seed a couple tasks to give non-zero report
    t = ts.create_task(
        room="lobby",
        created_by="u1",
        requested_by_name="User",
        assigned_to=agent_id,
        title="x",
        prompt="do",
    )
    ts.update_status(t.id, "completed", result="ok")
    ts.record_rating(t.id, rater_id="u1", rating=4)

    rep, old, new = eng.evolve_agent(agent_id)
    assert rep.agent_id == agent_id
    saved = ps.get_policy(agent_id)
    assert saved.agent_id == agent_id
    # At minimum it should match what evolve applied.
    assert saved.max_plan_steps == new.max_plan_steps
    assert saved.max_tool_calls == new.max_tool_calls

