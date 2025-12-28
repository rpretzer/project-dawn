from interface.moderation_store import ModerationStore


def test_ban_and_mute(tmp_path):
    store = ModerationStore(db_path=tmp_path / "mod.db")
    store.set_ban(kind="user", value="123", reason="bad", duration_seconds=60)
    banned, reason = store.is_banned(user_id="123", ip=None)
    assert banned is True
    assert reason == "bad"

    store.set_mute(user_id="123", room="lobby", reason="spam", duration_seconds=60)
    muted, mreason = store.is_muted(user_id="123", room="lobby")
    assert muted is True
    assert mreason == "spam"

