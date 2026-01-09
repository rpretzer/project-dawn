from pathlib import Path

from core.ops_log import OpsLogStore


def test_ops_log_store_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "ops.db"
    s = OpsLogStore(db_path=db, retention_days=1, max_events=100)
    s.append("ws_in", {"msg_type": "chat", "room": "lobby"})
    s.append("create_task", {"room": "lobby", "target": "all"})

    evs = s.list_recent(limit=10)
    assert len(evs) >= 2
    assert evs[0].id >= evs[1].id
    assert {e.event_type for e in evs} >= {"ws_in", "create_task"}

    evs2 = s.list_recent(limit=10, event_type="create_task")
    assert all(e.event_type == "create_task" for e in evs2)

