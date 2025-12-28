"""
Session + password reset stores (SQLite).

Design goals:
- Refresh tokens are opaque random strings stored only as a hash (HMAC-SHA256).
- Support rotation-on-refresh (one-time use refresh tokens).
- Provide admin-friendly revocation (revoke all sessions for a user).
- Password reset tokens are also opaque and hashed.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from core.db_migrations import ensure_schema


def _now() -> float:
    return time.time()


def _hmac_sha256_hex(*, secret: str, msg: str) -> str:
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: int
    created_at_ts: float
    expires_at_ts: float
    last_used_at_ts: Optional[float]
    revoked_at_ts: Optional[float]
    rotated_from_id: Optional[str]
    rotated_to_id: Optional[str]
    ip: Optional[str]
    user_agent: Optional[str]


class SessionStore:
    """
    Stores refresh sessions in SQLite.

    IMPORTANT: refresh tokens are stored hashed; the raw token is returned once.
    """

    def __init__(self, db_path: Optional[Path] = None, *, token_secret: str):
        self.db_path = Path(db_path or "data/users.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_secret = str(token_secret or "")
        if not self.token_secret:
            raise ValueError("token_secret_required")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            ensure_schema(conn, schema_name="session_store", target_version=1)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_sessions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    created_at_ts REAL NOT NULL,
                    expires_at_ts REAL NOT NULL,
                    last_used_at_ts REAL,
                    revoked_at_ts REAL,
                    rotated_from_id TEXT,
                    rotated_to_id TEXT,
                    ip TEXT,
                    user_agent TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_sessions_user_id ON refresh_sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_sessions_expires ON refresh_sessions(expires_at_ts)")
            conn.commit()

    def _hash(self, token: str) -> str:
        return _hmac_sha256_hex(secret=self.token_secret, msg=str(token or ""))

    def create_session(
        self,
        *,
        user_id: int,
        ip: Optional[str],
        user_agent: Optional[str],
        ttl_seconds: int,
        rotated_from_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Returns: (session_id, refresh_token)
        """
        now = _now()
        sess_id = secrets.token_hex(16)
        refresh_token = secrets.token_urlsafe(48)
        token_hash = self._hash(refresh_token)
        expires_at = now + float(int(ttl_seconds))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO refresh_sessions (
                    id, user_id, token_hash, created_at_ts, expires_at_ts,
                    last_used_at_ts, revoked_at_ts, rotated_from_id, rotated_to_id,
                    ip, user_agent
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, NULL, ?, ?)
                """,
                (
                    sess_id,
                    int(user_id),
                    token_hash,
                    float(now),
                    float(expires_at),
                    rotated_from_id,
                    ip,
                    user_agent,
                ),
            )
            conn.commit()
        return sess_id, refresh_token

    def revoke_token(self, refresh_token: str) -> bool:
        token_hash = self._hash(refresh_token)
        now = _now()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE refresh_sessions
                SET revoked_at_ts = COALESCE(revoked_at_ts, ?)
                WHERE token_hash = ?
                """,
                (float(now), token_hash),
            )
            conn.commit()
            return int(cur.rowcount or 0) > 0

    def revoke_user_sessions(self, user_id: int) -> int:
        now = _now()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE refresh_sessions
                SET revoked_at_ts = COALESCE(revoked_at_ts, ?)
                WHERE user_id = ? AND revoked_at_ts IS NULL
                """,
                (float(now), int(user_id)),
            )
            conn.commit()
            return int(cur.rowcount or 0)

    def rotate(
        self,
        *,
        refresh_token: str,
        ip: Optional[str],
        user_agent: Optional[str],
        ttl_seconds: int,
    ) -> Optional[Tuple[int, str, str]]:
        """
        Atomically rotate an existing refresh token.

        Returns: (user_id, new_session_id, new_refresh_token) or None if invalid/expired/revoked.
        """
        now = _now()
        token_hash = self._hash(refresh_token)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, user_id, expires_at_ts, revoked_at_ts
                FROM refresh_sessions
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                return None
            if row["revoked_at_ts"] is not None:
                conn.execute("ROLLBACK")
                return None
            if float(row["expires_at_ts"]) <= float(now):
                conn.execute("ROLLBACK")
                return None

            old_id = str(row["id"])
            user_id = int(row["user_id"])

            # Create next session
            new_id = secrets.token_hex(16)
            new_token = secrets.token_urlsafe(48)
            new_hash = self._hash(new_token)
            new_expires = now + float(int(ttl_seconds))
            conn.execute(
                """
                INSERT INTO refresh_sessions (
                    id, user_id, token_hash, created_at_ts, expires_at_ts,
                    last_used_at_ts, revoked_at_ts, rotated_from_id, rotated_to_id,
                    ip, user_agent
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, NULL, ?, ?)
                """,
                (
                    new_id,
                    user_id,
                    new_hash,
                    float(now),
                    float(new_expires),
                    old_id,
                    ip,
                    user_agent,
                ),
            )
            # Revoke old and link
            conn.execute(
                """
                UPDATE refresh_sessions
                SET revoked_at_ts = ?,
                    last_used_at_ts = ?,
                    rotated_to_id = ?
                WHERE id = ? AND revoked_at_ts IS NULL
                """,
                (float(now), float(now), new_id, old_id),
            )
            conn.commit()
        return user_id, new_id, new_token


class PasswordResetStore:
    """
    Stores password reset tokens in SQLite.
    """

    def __init__(self, db_path: Optional[Path] = None, *, token_secret: str):
        self.db_path = Path(db_path or "data/users.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_secret = str(token_secret or "")
        if not self.token_secret:
            raise ValueError("token_secret_required")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            ensure_schema(conn, schema_name="password_reset_store", target_version=1)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT UNIQUE NOT NULL,
                    created_at_ts REAL NOT NULL,
                    expires_at_ts REAL NOT NULL,
                    used_at_ts REAL,
                    requested_ip TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pwreset_user_id ON password_reset_tokens(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pwreset_expires ON password_reset_tokens(expires_at_ts)")
            conn.commit()

    def _hash(self, token: str) -> str:
        return _hmac_sha256_hex(secret=self.token_secret, msg=str(token or ""))

    def issue(self, *, user_id: int, ttl_seconds: int, requested_ip: Optional[str]) -> Tuple[str, str]:
        now = _now()
        tok_id = secrets.token_hex(16)
        token = secrets.token_urlsafe(40)
        token_hash = self._hash(token)
        expires_at = now + float(int(ttl_seconds))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO password_reset_tokens (
                    id, user_id, token_hash, created_at_ts, expires_at_ts, used_at_ts, requested_ip
                ) VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (tok_id, int(user_id), token_hash, float(now), float(expires_at), requested_ip),
            )
            conn.commit()
        return tok_id, token

    def consume(self, *, token: str) -> Optional[int]:
        """
        Mark token as used and return user_id, or None if invalid/expired/used.
        """
        now = _now()
        token_hash = self._hash(token)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, user_id, expires_at_ts, used_at_ts
                FROM password_reset_tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                return None
            if row["used_at_ts"] is not None:
                conn.execute("ROLLBACK")
                return None
            if float(row["expires_at_ts"]) <= float(now):
                conn.execute("ROLLBACK")
                return None
            tok_id = str(row["id"])
            user_id = int(row["user_id"])
            conn.execute(
                "UPDATE password_reset_tokens SET used_at_ts = ? WHERE id = ? AND used_at_ts IS NULL",
                (float(now), tok_id),
            )
            conn.commit()
        return user_id

