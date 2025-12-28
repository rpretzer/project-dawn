import sqlite3
from pathlib import Path

from core.task_manager import TaskStore
from core.agent_policy import PolicyStore
from interface.chat_store import ChatStore


def _get_version(db_path: Path, schema_name: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT version FROM schema_versions WHERE schema_name = ?", (schema_name,)).fetchone()
    assert row is not None
    return int(row[0])


def test_schema_versions_created_for_stores(tmp_path: Path) -> None:
    task_db = tmp_path / "tasks.db"
    policy_db = tmp_path / "policies.db"
    chat_db = tmp_path / "chat.db"

    TaskStore(db_path=task_db)
    PolicyStore(db_path=policy_db)
    ChatStore(db_path=chat_db)

    assert _get_version(task_db, "task_store") >= 1
    assert _get_version(policy_db, "policy_store") >= 1
    assert _get_version(chat_db, "chat_store") >= 1

