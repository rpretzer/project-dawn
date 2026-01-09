from pathlib import Path

from core.agent_policy import AgentPolicy, PolicyStore


def test_policy_history_and_rollback(tmp_path: Path) -> None:
    ps = PolicyStore(db_path=tmp_path / "policies.db")
    agent_id = "agent_010"

    p1 = AgentPolicy(agent_id=agent_id, max_plan_steps=6, max_tool_calls=10, step_timeout_seconds=20.0, delegation_bias=0.2, verbosity="concise")
    ps.set_policy(p1)

    p2 = AgentPolicy(agent_id=agent_id, max_plan_steps=9, max_tool_calls=14, step_timeout_seconds=40.0, delegation_bias=0.6, verbosity="verbose")
    ps.set_policy(p2)

    hist = ps.list_history(agent_id, limit=10)
    assert len(hist) >= 2
    newest = hist[0]
    older = hist[1]
    assert newest["agent_id"] == agent_id
    assert older["agent_id"] == agent_id

    # Roll back to the older entry and ensure current matches it.
    rolled = ps.rollback_to_history_id(agent_id, older["id"])
    assert rolled.agent_id == agent_id
    assert rolled.max_plan_steps == int((older["policy"] or {}).get("max_plan_steps"))
    assert rolled.max_tool_calls == int((older["policy"] or {}).get("max_tool_calls"))

