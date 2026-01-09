import time

from interface.session_store import SessionStore, PasswordResetStore


def test_refresh_session_rotation(tmp_path):
    db = tmp_path / "auth.db"
    store = SessionStore(db, token_secret="secret")
    store.max_sessions_per_user = 2
    _, tok = store.create_session(user_id=1, ip="1.2.3.4", user_agent="ua", ttl_seconds=60)
    rotated = store.rotate(refresh_token=tok, ip="1.2.3.4", user_agent="ua", ttl_seconds=60)
    assert rotated is not None
    user_id, _, new_tok = rotated
    assert user_id == 1
    assert new_tok != tok

    # Old token should be invalid after rotation
    assert store.rotate(refresh_token=tok, ip="1.2.3.4", user_agent="ua", ttl_seconds=60) is None


def test_refresh_session_cap(tmp_path):
    db = tmp_path / "auth.db"
    store = SessionStore(db, token_secret="secret")
    store.max_sessions_per_user = 2
    store.create_session(user_id=1, ip=None, user_agent=None, ttl_seconds=60)
    store.create_session(user_id=1, ip=None, user_agent=None, ttl_seconds=60)
    store.create_session(user_id=1, ip=None, user_agent=None, ttl_seconds=60)
    # Should keep at most 2 sessions
    import sqlite3

    with sqlite3.connect(db) as conn:
        n = conn.execute("SELECT COUNT(1) FROM refresh_sessions WHERE user_id = 1").fetchone()[0]
    assert int(n) <= 2


def test_password_reset_issue_and_consume(tmp_path):
    db = tmp_path / "auth.db"
    store = PasswordResetStore(db, token_secret="secret")
    _, tok = store.issue(user_id=7, ttl_seconds=60, requested_ip="1.2.3.4")
    uid = store.consume(token=tok)
    assert uid == 7
    # One-time use
    assert store.consume(token=tok) is None

