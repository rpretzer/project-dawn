from interface.chat_store import ChatStore


def test_chat_store_roundtrip(tmp_path):
    store = ChatStore(db_path=tmp_path / "chat.db")
    m1 = store.append_message(
        room="lobby",
        sender_type="human",
        sender_id="1",
        sender_name="alice",
        content="hello",
        created_at_ts=123.4,
    )
    assert m1.id > 0
    recent = store.get_recent(room="lobby", limit=10)
    assert len(recent) == 1
    assert recent[0].content == "hello"

