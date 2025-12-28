import sqlite3
import time
from pathlib import Path

from core.agent_policy import PolicyStore
from core.evolution_engine import EvolutionEngine
from core.evolution_manager import EvolutionManager
from core.task_manager import TaskStore


def _set_task_times(db_path: Path, task_id: str, *, created_at: float, updated_at: float) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET created_at_ts = ?, updated_at_ts = ? WHERE id = ?",
            (float(created_at), float(updated_at), str(task_id)),
        )
        conn.commit()


def test_evolution_manager_rolls_back_on_regression(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    policies_db = tmp_path / "policies.db"
    evo_db = tmp_path / "evolution.db"

    ts = TaskStore(db_path=tasks_db)
    ps = PolicyStore(db_path=policies_db)
    eng = EvolutionEngine(task_store=ts, policy_store=ps, window_tasks=20)
    mgr = EvolutionManager(task_store=ts, policy_store=ps, evolution_engine=eng, db_path=evo_db)

    agent_id = "agent_r"
    now = time.time()

    # Baseline: a few good completed tasks with high ratings
    for _ in range(5):
        t = ts.create_task(room="lobby", created_by="u", requested_by_name="u", assigned_to=agent_id, title="x", prompt="x")
        ts.update_status(t.id, "completed", result="ok")
        ts.record_rating(t.id, rater_id="u", rating=5)
        _set_task_times(tasks_db, t.id, created_at=now - 120, updated_at=now - 110)

    baseline_policy = ps.get_policy(agent_id)
    exp = mgr.start_experiment(agent_id=agent_id, min_tasks_after=3)
    assert exp.status == "pending"

    # After experiment start: create clearly worse outcomes
    start_ts = mgr.get_experiment(exp.id).start_ts
    for _ in range(3):
        t = ts.create_task(room="lobby", created_by="u", requested_by_name="u", assigned_to=agent_id, title="bad", prompt="bad")
        ts.update_status(t.id, "failed", error="boom")
        ts.record_rating(t.id, rater_id="u", rating=1)
        _set_task_times(tasks_db, t.id, created_at=start_ts + 1, updated_at=start_ts + 2)

    finalized = mgr.check_pending_and_finalize(regression_threshold=0.01, min_window_tasks=1)
    assert len(finalized) == 1
    assert finalized[0].status in ("rolled_back", "accepted")

    # With these tasks, it should regress and roll back.
    assert finalized[0].status == "rolled_back"

    # Current policy should now match the "old" snapshot values.
    cur = ps.get_policy(agent_id)
    assert cur.max_plan_steps == baseline_policy.max_plan_steps
    assert cur.max_tool_calls == baseline_policy.max_tool_calls

