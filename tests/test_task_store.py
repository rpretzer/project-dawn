from core.task_manager import TaskStore


def test_task_store_roundtrip(tmp_path):
    store = TaskStore(db_path=tmp_path / "tasks.db")
    task = store.create_task(
        room="lobby",
        created_by="user_1",
        requested_by_name="alice",
        assigned_to="agent_001",
        title="Do thing",
        prompt="Please do the thing",
        parent_task_id=None,
    )
    assert task.id.startswith("tsk_")
    fetched = store.get_task(task.id)
    assert fetched is not None
    assert fetched.title == "Do thing"
    assert fetched.status == "queued"

    store.append_event(task.id, "progress", {"pct": 10})
    evs = store.get_events(task.id)
    assert len(evs) >= 2  # created + progress
    assert any(e.event_type == "progress" for e in evs)

    updated = store.update_status(task.id, "completed", result="done")
    assert updated is not None
    assert updated.status == "completed"
    assert updated.result == "done"

