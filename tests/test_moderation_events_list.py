from pathlib import Path

from interface.moderation_store import ModerationStore


def test_list_events_returns_recent_events(tmp_path: Path) -> None:
    store = ModerationStore(db_path=tmp_path / "moderation.db")
    store.audit(
        action="patch_apply",
        actor_user_id="1",
        actor_name="admin",
        actor_ip="127.0.0.1",
        room="lobby",
        target="artifacts/tsk_x/change.patch",
        reason="ok=True exit=0",
    )
    store.audit(
        action="ban",
        actor_user_id="1",
        actor_name="admin",
        actor_ip="127.0.0.1",
        room="lobby",
        target="user:2",
        reason="spam",
    )

    evs = store.list_events(limit=10)
    assert len(evs) >= 2
    assert evs[0]["id"] >= evs[1]["id"]
    assert any(e["action"] == "patch_apply" for e in evs)
    assert any(e["action"] == "ban" for e in evs)

