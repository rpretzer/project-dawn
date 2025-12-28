"""
User Database Module for Project Dawn
Handles persistent user account storage and authentication
"""

import sqlite3
import logging
from typing import Optional, Dict, Any, Tuple, List
from pathlib import Path
from datetime import datetime

from core.db_migrations import ensure_schema

logger = logging.getLogger(__name__)

class UserDatabase:
    """Database interface for user accounts"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize user database"""
        if db_path is None:
            db_path = Path("data/users.db")
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            ensure_schema(conn, schema_name="user_database", target_version=1)
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    nickname TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            # Create index on username for fast lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
            """)
            
            conn.commit()
            logger.info(f"User database initialized at {self.db_path}")
    
    def create_user(
        self,
        username: str,
        password_hash: str,
        nickname: Optional[str] = None,
        email: Optional[str] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Create a new user account
        
        Returns:
            (success: bool, user_id: Optional[int], error_message: Optional[str])
        """
        try:
            username = username.strip().lower()
            nickname = nickname.strip() if nickname else username
            
            if len(username) < 3 or len(username) > 20:
                return False, None, "Username must be 3-20 characters"
            
            if len(nickname) > 30:
                return False, None, "Nickname must be 30 characters or less"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO users (username, password_hash, nickname, email)
                    VALUES (?, ?, ?, ?)
                """, (username, password_hash, nickname, email))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"User created: {username} (id: {user_id})")
                return True, user_id, None
                
        except sqlite3.IntegrityError:
            return False, None, "Username already exists"
        except Exception as e:
            logger.error(f"Error creating user {username}: {e}")
            return False, None, str(e)
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            username = username.strip().lower()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT id, username, password_hash, nickname, email,
                           created_at, last_login, is_active
                    FROM users
                    WHERE username = ? AND is_active = 1
                """, (username,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'username': row['username'],
                        'password_hash': row['password_hash'],
                        'nickname': row['nickname'],
                        'email': row['email'],
                        'created_at': row['created_at'],
                        'last_login': row['last_login'],
                        'is_active': bool(row['is_active'])
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting user {username}: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT id, username, password_hash, nickname, email,
                           created_at, last_login, is_active
                    FROM users
                    WHERE id = ? AND is_active = 1
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row['id'],
                        'username': row['username'],
                        'password_hash': row['password_hash'],
                        'nickname': row['nickname'],
                        'email': row['email'],
                        'created_at': row['created_at'],
                        'last_login': row['last_login'],
                        'is_active': bool(row['is_active'])
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error getting user by id {user_id}: {e}")
            return None
    
    def update_last_login(self, user_id: int):
        """Update last login timestamp"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE users
                    SET last_login = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
    
    def update_nickname(self, user_id: int, nickname: str) -> bool:
        """Update user nickname"""
        try:
            if len(nickname) > 30:
                return False
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE users
                    SET nickname = ?
                    WHERE id = ?
                """, (nickname.strip(), user_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating nickname for user {user_id}: {e}")
            return False
    
    def update_password(self, user_id: int, password_hash: str) -> bool:
        """Update user password"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE users
                    SET password_hash = ?
                    WHERE id = ?
                """, (password_hash, user_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating password for user {user_id}: {e}")
            return False
    
    def username_exists(self, username: str) -> bool:
        """Check if username already exists"""
        user = self.get_user_by_username(username)
        return user is not None
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate user account (soft delete)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE users
                    SET is_active = 0
                    WHERE id = ?
                """, (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            return False

    def set_active(self, user_id: int, is_active: bool) -> bool:
        """Set active flag for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE users
                    SET is_active = ?
                    WHERE id = ?
                    """,
                    (1 if is_active else 0, int(user_id)),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting is_active for user {user_id}: {e}")
            return False

    def get_user_by_username_any(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username, including inactive."""
        try:
            username = username.strip().lower()
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT id, username, password_hash, nickname, email,
                           created_at, last_login, is_active
                    FROM users
                    WHERE username = ?
                    """,
                    (username,),
                ).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "password_hash": row["password_hash"],
                    "nickname": row["nickname"],
                    "email": row["email"],
                    "created_at": row["created_at"],
                    "last_login": row["last_login"],
                    "is_active": bool(row["is_active"]),
                }
        except Exception as e:
            logger.error(f"Error getting user (any) {username}: {e}")
            return None

    def list_users(self, *, include_inactive: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        """List users for admin UI."""
        try:
            lim = max(1, min(int(limit), 2000))
        except Exception:
            lim = 200
        where = "" if include_inactive else "WHERE is_active = 1"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT id, username, nickname, email, created_at, last_login, is_active
                FROM users
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "id": int(r["id"]),
                        "username": str(r["username"]),
                        "nickname": str(r["nickname"] or ""),
                        "email": str(r["email"] or ""),
                        "created_at": r["created_at"],
                        "last_login": r["last_login"],
                        "is_active": bool(r["is_active"]),
                    }
                )
            return out

