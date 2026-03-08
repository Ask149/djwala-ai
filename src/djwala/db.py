# src/djwala/db.py
"""User and auth session database operations (SQLite)."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from djwala.models import AuthSession, User


class UserDB:
    """SQLite-backed user and session store."""

    def __init__(self, db_path: str = "djwala_cache.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                avatar_url TEXT,
                google_id TEXT UNIQUE,
                google_access_token TEXT,
                google_refresh_token TEXT,
                google_token_expires_at INTEGER,
                spotify_id TEXT UNIQUE,
                spotify_access_token TEXT,
                spotify_refresh_token TEXT,
                spotify_token_expires_at INTEGER,
                spotify_is_premium INTEGER DEFAULT 0,
                playback_preference TEXT DEFAULT 'youtube',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def get_user(self, user_id: str) -> User | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return self._row_to_user(row) if row else None

    def find_by_google_id(self, google_id: str) -> User | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()
        return self._row_to_user(row) if row else None

    def find_by_spotify_id(self, spotify_id: str) -> User | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE spotify_id = ?", (spotify_id,)
        ).fetchone()
        return self._row_to_user(row) if row else None

    def find_or_create_google(
        self, *, google_id: str, display_name: str,
        avatar_url: str | None = None,
        access_token: str, refresh_token: str, expires_at: int,
    ) -> User:
        existing = self.find_by_google_id(google_id)
        if existing:
            self._conn.execute("""
                UPDATE users SET
                    display_name = ?, avatar_url = ?,
                    google_access_token = ?, google_refresh_token = ?,
                    google_token_expires_at = ?
                WHERE id = ?
            """, (display_name, avatar_url, access_token, refresh_token,
                  expires_at, existing.id))
            self._conn.commit()
            return self.get_user(existing.id)

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            INSERT INTO users (id, display_name, avatar_url,
                google_id, google_access_token, google_refresh_token,
                google_token_expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, display_name, avatar_url,
              google_id, access_token, refresh_token, expires_at, now))
        self._conn.commit()
        return self.get_user(user_id)

    def find_or_create_spotify(
        self, *, spotify_id: str, display_name: str,
        avatar_url: str | None = None,
        access_token: str, refresh_token: str, expires_at: int,
        is_premium: bool = False,
    ) -> User:
        existing = self.find_by_spotify_id(spotify_id)
        if existing:
            self._conn.execute("""
                UPDATE users SET
                    display_name = ?, avatar_url = ?,
                    spotify_access_token = ?, spotify_refresh_token = ?,
                    spotify_token_expires_at = ?, spotify_is_premium = ?
                WHERE id = ?
            """, (display_name, avatar_url, access_token, refresh_token,
                  expires_at, int(is_premium), existing.id))
            self._conn.commit()
            return self.get_user(existing.id)

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            INSERT INTO users (id, display_name, avatar_url,
                spotify_id, spotify_access_token, spotify_refresh_token,
                spotify_token_expires_at, spotify_is_premium, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, display_name, avatar_url,
              spotify_id, access_token, refresh_token, expires_at,
              int(is_premium), now))
        self._conn.commit()
        return self.get_user(user_id)

    def link_google(
        self, *, user_id: str, google_id: str,
        access_token: str, refresh_token: str, expires_at: int,
    ) -> None:
        conflict = self.find_by_google_id(google_id)
        if conflict and conflict.id != user_id:
            raise ValueError("This Google account is already linked to another DjwalaAI account")
        self._conn.execute("""
            UPDATE users SET
                google_id = ?, google_access_token = ?,
                google_refresh_token = ?, google_token_expires_at = ?
            WHERE id = ?
        """, (google_id, access_token, refresh_token, expires_at, user_id))
        self._conn.commit()

    def link_spotify(
        self, *, user_id: str, spotify_id: str,
        access_token: str, refresh_token: str, expires_at: int,
        is_premium: bool = False,
    ) -> None:
        conflict = self.find_by_spotify_id(spotify_id)
        if conflict and conflict.id != user_id:
            raise ValueError("This Spotify account is already linked to another DjwalaAI account")
        self._conn.execute("""
            UPDATE users SET
                spotify_id = ?, spotify_access_token = ?,
                spotify_refresh_token = ?, spotify_token_expires_at = ?,
                spotify_is_premium = ?
            WHERE id = ?
        """, (spotify_id, access_token, refresh_token, expires_at,
              int(is_premium), user_id))
        self._conn.commit()

    def update_google_tokens(self, user_id: str, access_token: str, expires_at: int) -> None:
        self._conn.execute("""
            UPDATE users SET google_access_token = ?, google_token_expires_at = ?
            WHERE id = ?
        """, (access_token, expires_at, user_id))
        self._conn.commit()

    def update_spotify_tokens(self, user_id: str, access_token: str, expires_at: int) -> None:
        self._conn.execute("""
            UPDATE users SET spotify_access_token = ?, spotify_token_expires_at = ?
            WHERE id = ?
        """, (access_token, expires_at, user_id))
        self._conn.commit()

    def update_playback_preference(self, user_id: str, preference: str) -> None:
        self._conn.execute(
            "UPDATE users SET playback_preference = ? WHERE id = ?",
            (preference, user_id),
        )
        self._conn.commit()

    # --- Auth Sessions ---

    def create_session(self, user_id: str, ttl_days: int = 30) -> AuthSession:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=ttl_days)
        self._conn.execute("""
            INSERT INTO auth_sessions (session_id, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, user_id, now.isoformat(), expires.isoformat()))
        self._conn.commit()
        return AuthSession(
            session_id=session_id, user_id=user_id,
            created_at=now.isoformat(), expires_at=expires.isoformat(),
        )

    def get_session(self, session_id: str) -> AuthSession | None:
        row = self._conn.execute(
            "SELECT * FROM auth_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        now = datetime.now(timezone.utc).isoformat()
        if row["expires_at"] < now:
            self.delete_session(session_id)
            return None
        return AuthSession(
            session_id=row["session_id"], user_id=row["user_id"],
            created_at=row["created_at"], expires_at=row["expires_at"],
        )

    def delete_session(self, session_id: str) -> None:
        self._conn.execute(
            "DELETE FROM auth_sessions WHERE session_id = ?", (session_id,)
        )
        self._conn.commit()

    def close(self):
        self._conn.close()

    # --- Internal ---

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            display_name=row["display_name"],
            avatar_url=row["avatar_url"],
            google_id=row["google_id"],
            google_access_token=row["google_access_token"],
            google_refresh_token=row["google_refresh_token"],
            google_token_expires_at=row["google_token_expires_at"],
            spotify_id=row["spotify_id"],
            spotify_access_token=row["spotify_access_token"],
            spotify_refresh_token=row["spotify_refresh_token"],
            spotify_token_expires_at=row["spotify_token_expires_at"],
            spotify_is_premium=bool(row["spotify_is_premium"]),
            playback_preference=row["playback_preference"],
            created_at=row["created_at"],
        )
