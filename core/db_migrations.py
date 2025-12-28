"""
Tiny SQLite schema versioning helper.

This project uses several small SQLite databases. Historically each module used
`CREATE TABLE IF NOT EXISTS` with no explicit schema version. This helper adds:
- a shared `schema_versions` table (per-DB)
- an explicit version number per schema_name
- a forward-only migration mechanism

For now, most stores are at version 1 with no migrations.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Callable, Dict, Optional


MigrationFn = Callable[[sqlite3.Connection], None]


def _ensure_versions_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            schema_name TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            updated_at_ts REAL NOT NULL
        )
        """
    )


def get_schema_version(conn: sqlite3.Connection, schema_name: str) -> Optional[int]:
    _ensure_versions_table(conn)
    row = conn.execute(
        "SELECT version FROM schema_versions WHERE schema_name = ?",
        (str(schema_name),),
    ).fetchone()
    if not row:
        return None
    try:
        return int(row[0])
    except Exception:
        return None


def set_schema_version(conn: sqlite3.Connection, schema_name: str, version: int) -> None:
    _ensure_versions_table(conn)
    now = time.time()
    conn.execute(
        """
        INSERT INTO schema_versions (schema_name, version, updated_at_ts)
        VALUES (?, ?, ?)
        ON CONFLICT(schema_name) DO UPDATE SET
            version=excluded.version,
            updated_at_ts=excluded.updated_at_ts
        """,
        (str(schema_name), int(version), float(now)),
    )


def ensure_schema(
    conn: sqlite3.Connection,
    *,
    schema_name: str,
    target_version: int,
    migrations: Optional[Dict[int, MigrationFn]] = None,
) -> int:
    """
    Ensure schema is upgraded to target_version.

    migrations: map of {from_version: migration_fn} where migration_fn upgrades
    from_version -> from_version+1.
    """
    if target_version < 1:
        raise ValueError("target_version_must_be_positive")
    migrations = migrations or {}

    cur = get_schema_version(conn, schema_name)
    if cur is None:
        # Brand new schema record; assume module will create the versioned schema.
        set_schema_version(conn, schema_name, target_version)
        return target_version

    v = int(cur)
    while v < target_version:
        fn = migrations.get(v)
        if not fn:
            raise RuntimeError(f"missing_migration:{schema_name}:{v}_to_{v+1}")
        fn(conn)
        v += 1
        set_schema_version(conn, schema_name, v)

    return v

