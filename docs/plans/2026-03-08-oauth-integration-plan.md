# OAuth Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add YouTube + Spotify OAuth login, playlist import as mix seeds, Spotify Audio Features for instant analysis, and optional Spotify playback for Premium users.

**Architecture:** Server-side sessions with HTTP-only cookies. OAuth 2.0 authorization code flow for both Google and Spotify. 3 new backend files (`auth.py`, `providers.py`, `db.py`), modifications to 4 existing files, and frontend changes across HTML/JS/CSS. App works fully without login — OAuth unlocks bonus features.

**Tech Stack:** FastAPI, SQLite, OAuth 2.0 (manual implementation with `requests`), Spotify Web Playback SDK (JS), `cryptography` (Fernet for CSRF state signing)

**Design doc:** `docs/plans/2026-03-08-oauth-integration-design.md`

---

## Task 1: User & Auth Models

**Files:**
- Modify: `src/djwala/models.py`
- Test: `tests/test_models.py` (new)

**Step 1: Write tests for new models**

```python
# tests/test_models.py
"""Tests for data models."""
from djwala.models import (
    InputMode, TrackInfo, TrackAnalysis,
    User, AuthSession,
    spotify_key_to_name, spotify_key_to_camelot,
)

def test_input_mode_playlist():
    assert InputMode.PLAYLIST.value == "playlist"

def test_user_has_google():
    user = User(id="u1", display_name="Test", google_id="g123")
    assert user.has_google
    assert not user.has_spotify

def test_user_has_spotify():
    user = User(id="u1", display_name="Test", spotify_id="s123")
    assert not user.has_google
    assert user.has_spotify

def test_spotify_key_to_name():
    # Spotify key=0 (C), mode=1 (major) → "C"
    assert spotify_key_to_name(0, 1) == "C"
    # key=9 (A), mode=0 (minor) → "Am"
    assert spotify_key_to_name(9, 0) == "Am"
    # key=1 (C#), mode=1 (major) → "C#"
    assert spotify_key_to_name(1, 1) == "C#"
    # key=-1 (unknown) → "Am" default
    assert spotify_key_to_name(-1, 0) == "Am"

def test_spotify_key_to_camelot():
    assert spotify_key_to_camelot(0, 1) == "8B"   # C major
    assert spotify_key_to_camelot(9, 0) == "8A"   # A minor
    assert spotify_key_to_camelot(7, 1) == "9B"   # G major
    assert spotify_key_to_camelot(-1, 0) == "8A"  # unknown → default
```

**Step 2: Run tests — expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_models.py -v --tb=short
```

**Step 3: Implement models**

Add to `src/djwala/models.py`:

```python
# Add PLAYLIST to InputMode
class InputMode(str, Enum):
    ARTISTS = "artists"
    SONG = "song"
    MOOD = "mood"
    PLAYLIST = "playlist"

# After existing models, add:

KEY_NAMES_SPOTIFY = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def spotify_key_to_name(key: int, mode: int) -> str:
    """Convert Spotify key (0-11) + mode (0=minor, 1=major) to key name."""
    if key < 0 or key > 11:
        return "Am" if mode == 0 else "C"
    name = KEY_NAMES_SPOTIFY[key]
    return f"{name}m" if mode == 0 else name

def spotify_key_to_camelot(key: int, mode: int) -> str:
    """Convert Spotify key + mode to Camelot wheel code."""
    from djwala.analyzer import CAMELOT_WHEEL
    if key < 0 or key > 11:
        return "8A" if mode == 0 else "8B"
    name = KEY_NAMES_SPOTIFY[key]
    mode_str = "minor" if mode == 0 else "major"
    return CAMELOT_WHEEL.get((name, mode_str), "8A")


@dataclass
class User:
    """User account."""
    id: str
    display_name: str
    avatar_url: str | None = None
    google_id: str | None = None
    google_access_token: str | None = None
    google_refresh_token: str | None = None
    google_token_expires_at: int | None = None
    spotify_id: str | None = None
    spotify_access_token: str | None = None
    spotify_refresh_token: str | None = None
    spotify_token_expires_at: int | None = None
    spotify_is_premium: bool = False
    playback_preference: str = "youtube"
    created_at: str = ""

    @property
    def has_google(self) -> bool:
        return self.google_id is not None

    @property
    def has_spotify(self) -> bool:
        return self.spotify_id is not None


@dataclass
class AuthSession:
    """Server-side auth session (maps cookie → user)."""
    session_id: str
    user_id: str
    created_at: str
    expires_at: str
```

**Step 4: Run tests — expect PASS**

```bash
.venv/bin/python -m pytest tests/test_models.py -v --tb=short
```

**Step 5: Run ALL tests to verify no breakage**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

**Step 6: Commit**

```bash
git add src/djwala/models.py tests/test_models.py
git commit -m "feat(models): add User, AuthSession, PLAYLIST mode, Spotify key helpers"
```

---

## Task 2: Database Module

**Files:**
- Create: `src/djwala/db.py`
- Test: `tests/test_db.py` (new)

**Step 1: Write tests**

```python
# tests/test_db.py
"""Tests for user/session database operations."""
import time
import pytest
from djwala.db import UserDB
from djwala.models import User


@pytest.fixture
def db(tmp_path):
    d = UserDB(str(tmp_path / "test.db"))
    yield d
    d.close()


def test_create_user_google(db):
    user = db.find_or_create_google(
        google_id="g123",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
        access_token="at_123",
        refresh_token="rt_123",
        expires_at=int(time.time()) + 3600,
    )
    assert user.id  # uuid assigned
    assert user.display_name == "Test User"
    assert user.google_id == "g123"
    assert user.google_access_token == "at_123"


def test_find_existing_google_user(db):
    user1 = db.find_or_create_google(
        google_id="g123", display_name="Test",
        access_token="at1", refresh_token="rt1",
        expires_at=int(time.time()) + 3600,
    )
    user2 = db.find_or_create_google(
        google_id="g123", display_name="Test Updated",
        access_token="at2", refresh_token="rt2",
        expires_at=int(time.time()) + 3600,
    )
    assert user1.id == user2.id  # same user
    assert user2.google_access_token == "at2"  # tokens updated


def test_create_user_spotify(db):
    user = db.find_or_create_spotify(
        spotify_id="s456",
        display_name="Spotify User",
        avatar_url=None,
        access_token="sp_at",
        refresh_token="sp_rt",
        expires_at=int(time.time()) + 3600,
        is_premium=True,
    )
    assert user.spotify_id == "s456"
    assert user.spotify_is_premium is True


def test_link_spotify_to_google_user(db):
    user = db.find_or_create_google(
        google_id="g123", display_name="Test",
        access_token="at", refresh_token="rt",
        expires_at=int(time.time()) + 3600,
    )
    db.link_spotify(
        user_id=user.id,
        spotify_id="s789",
        access_token="sp_at",
        refresh_token="sp_rt",
        expires_at=int(time.time()) + 3600,
        is_premium=False,
    )
    updated = db.get_user(user.id)
    assert updated.spotify_id == "s789"
    assert updated.has_google
    assert updated.has_spotify


def test_link_spotify_already_taken(db):
    db.find_or_create_spotify(
        spotify_id="s789", display_name="Other User",
        access_token="x", refresh_token="x",
        expires_at=int(time.time()) + 3600,
        is_premium=False,
    )
    google_user = db.find_or_create_google(
        google_id="g123", display_name="Test",
        access_token="at", refresh_token="rt",
        expires_at=int(time.time()) + 3600,
    )
    with pytest.raises(ValueError, match="already linked"):
        db.link_spotify(
            user_id=google_user.id,
            spotify_id="s789",
            access_token="x", refresh_token="x",
            expires_at=int(time.time()) + 3600,
            is_premium=False,
        )


def test_create_and_get_session(db):
    user = db.find_or_create_google(
        google_id="g1", display_name="Test",
        access_token="at", refresh_token="rt",
        expires_at=int(time.time()) + 3600,
    )
    session = db.create_session(user.id)
    assert session.user_id == user.id
    fetched = db.get_session(session.session_id)
    assert fetched is not None
    assert fetched.user_id == user.id


def test_get_expired_session_returns_none(db):
    user = db.find_or_create_google(
        google_id="g1", display_name="Test",
        access_token="at", refresh_token="rt",
        expires_at=int(time.time()) + 3600,
    )
    session = db.create_session(user.id, ttl_days=0)  # expires immediately
    result = db.get_session(session.session_id)
    assert result is None


def test_delete_session(db):
    user = db.find_or_create_google(
        google_id="g1", display_name="Test",
        access_token="at", refresh_token="rt",
        expires_at=int(time.time()) + 3600,
    )
    session = db.create_session(user.id)
    db.delete_session(session.session_id)
    assert db.get_session(session.session_id) is None


def test_update_tokens(db):
    user = db.find_or_create_google(
        google_id="g1", display_name="Test",
        access_token="old_at", refresh_token="rt",
        expires_at=1000,
    )
    db.update_google_tokens(user.id, "new_at", 2000)
    updated = db.get_user(user.id)
    assert updated.google_access_token == "new_at"
    assert updated.google_token_expires_at == 2000


def test_update_playback_preference(db):
    user = db.find_or_create_spotify(
        spotify_id="s1", display_name="Test",
        access_token="at", refresh_token="rt",
        expires_at=int(time.time()) + 3600,
        is_premium=True,
    )
    assert user.playback_preference == "youtube"  # default
    db.update_playback_preference(user.id, "spotify")
    updated = db.get_user(user.id)
    assert updated.playback_preference == "spotify"
```

**Step 2: Run tests — expect FAIL**

```bash
.venv/bin/python -m pytest tests/test_db.py -v --tb=short
```

**Step 3: Implement db.py**

```python
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
```

**Step 4: Run tests — expect PASS**

```bash
.venv/bin/python -m pytest tests/test_db.py -v --tb=short
```

**Step 5: Run ALL tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

**Step 6: Commit**

```bash
git add src/djwala/db.py tests/test_db.py
git commit -m "feat(db): add user and auth session SQLite store"
```

---

## Task 3: Config Updates

**Files:**
- Modify: `src/djwala/config.py`
- Test: `tests/test_config.py` (existing — add tests)

**Step 1: Read existing test_config.py to understand patterns**

```bash
cat tests/test_config.py
```

**Step 2: Add tests for OAuth config**

Add to `tests/test_config.py`:

```python
def test_oauth_disabled_by_default():
    """OAuth is disabled when no client IDs configured."""
    s = Settings()
    assert not s.oauth_enabled

def test_oauth_enabled_with_google():
    """OAuth enabled when Google credentials present."""
    s = Settings(google_client_id="id", google_client_secret="secret")
    assert s.oauth_enabled

def test_oauth_enabled_with_spotify():
    """OAuth enabled when Spotify credentials present."""
    s = Settings(spotify_client_id="id", spotify_client_secret="secret")
    assert s.oauth_enabled

def test_session_secret_default_none():
    s = Settings()
    assert s.session_secret is None
```

**Step 3: Implement config changes**

Update `src/djwala/config.py`:

```python
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit: str = "5/minute"
    database_path: str = "djwala_cache.db"
    youtube_api_key: str | None = None

    # OAuth (optional — app works without login)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    session_secret: str | None = None

    @property
    def oauth_enabled(self) -> bool:
        """True if at least one OAuth provider is configured."""
        return bool(
            (self.google_client_id and self.google_client_secret)
            or (self.spotify_client_id and self.spotify_client_secret)
        )

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def spotify_enabled(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)

    model_config = SettingsConfigDict(
        env_prefix="DJWALA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_config.py -v --tb=short
```

**Step 5: Run ALL tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

**Step 6: Commit**

```bash
git add src/djwala/config.py tests/test_config.py
git commit -m "feat(config): add OAuth provider settings (Google, Spotify)"
```

---

## Task 4: Auth Module — Routes & Session Middleware

**Files:**
- Create: `src/djwala/auth.py`
- Test: `tests/test_auth.py` (new)

This is the largest task. It covers:
- CSRF state cookie (signed with Fernet)
- Google OAuth login/callback
- Spotify OAuth login/callback
- `/auth/me`, `/auth/logout`
- Link provider routes
- Spotify player token endpoint
- `get_current_user()` dependency

**Step 1: Add `cryptography` dependency**

```bash
# Add to pyproject.toml dependencies
```

Update `pyproject.toml` — add `"cryptography>=43.0"` to dependencies list.

**Step 2: Write tests**

```python
# tests/test_auth.py
"""Tests for auth routes and session management."""
import time
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport
from djwala.main import app, settings


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_auth_me_unauthenticated(client):
    """GET /auth/me without cookie returns logged_in=false."""
    resp = await client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["logged_in"] is False


async def test_auth_me_invalid_cookie(client):
    """GET /auth/me with invalid session cookie returns logged_in=false."""
    resp = await client.get("/auth/me", cookies={"djwala_session": "invalid"})
    assert resp.status_code == 200
    assert resp.json()["logged_in"] is False


async def test_google_login_redirect_disabled(client):
    """GET /auth/google/login returns 404 when Google not configured."""
    resp = await client.get("/auth/google/login", follow_redirects=False)
    assert resp.status_code == 404


async def test_spotify_login_redirect_disabled(client):
    """GET /auth/spotify/login returns 404 when Spotify not configured."""
    resp = await client.get("/auth/spotify/login", follow_redirects=False)
    assert resp.status_code == 404


async def test_logout_clears_cookie(client):
    """GET /auth/logout clears session cookie."""
    resp = await client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    # Cookie should be set with max_age=0 to clear it
    set_cookie = resp.headers.get("set-cookie", "")
    assert "djwala_session" in set_cookie


async def test_auth_status_in_page_data(client):
    """GET /auth/status returns oauth_enabled flag."""
    resp = await client.get("/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "oauth_enabled" in data
    assert "google_enabled" in data
    assert "spotify_enabled" in data
```

**Step 3: Implement auth.py**

```python
# src/djwala/auth.py
"""OAuth routes, session middleware, and auth utilities."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
import urllib.parse

import requests as http_requests
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from djwala.config import Settings
from djwala.db import UserDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# These will be initialized from main.py
_settings: Settings | None = None
_db: UserDB | None = None

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"

GOOGLE_SCOPES = "openid profile email https://www.googleapis.com/auth/youtube.readonly"
SPOTIFY_SCOPES = "user-read-email user-read-private playlist-read-private user-library-read streaming"


def init_auth(settings: Settings, db: UserDB):
    """Initialize auth module with settings and DB. Called from main.py."""
    global _settings, _db
    _settings = settings
    _db = db


def _sign_state(state: str) -> str:
    """Sign a CSRF state string using session secret."""
    key = (_settings.session_secret or "djwala-dev-key").encode()
    sig = hmac.new(key, state.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{state}.{sig}"


def _verify_state(signed: str) -> str | None:
    """Verify and return the original state, or None if invalid."""
    if "." not in signed:
        return None
    state, sig = signed.rsplit(".", 1)
    expected = _sign_state(state)
    if hmac.compare_digest(signed, expected):
        return state
    return None


def _get_base_url(request: Request) -> str:
    """Get base URL for OAuth callbacks."""
    # Use X-Forwarded headers in production (behind Fly.io proxy)
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{proto}://{host}"


def _set_session_cookie(response: Response, session_id: str):
    response.set_cookie(
        key="djwala_session",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 86400,
        path="/",
    )


def get_current_user(request: Request):
    """Extract current user from session cookie. Returns None if not logged in."""
    session_id = request.cookies.get("djwala_session")
    if not session_id or not _db:
        return None
    auth_session = _db.get_session(session_id)
    if not auth_session:
        return None
    return _db.get_user(auth_session.user_id)


# --- Status ---

@router.get("/status")
async def auth_status():
    """Return OAuth configuration status (used by frontend to show/hide buttons)."""
    return {
        "oauth_enabled": _settings.oauth_enabled if _settings else False,
        "google_enabled": _settings.google_enabled if _settings else False,
        "spotify_enabled": _settings.spotify_enabled if _settings else False,
    }


@router.get("/me")
async def auth_me(request: Request):
    """Return current user info, or logged_in=false."""
    user = get_current_user(request)
    if not user:
        return {"logged_in": False}
    return {
        "logged_in": True,
        "user": {
            "id": user.id,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "has_google": user.has_google,
            "has_spotify": user.has_spotify,
            "spotify_is_premium": user.spotify_is_premium,
            "playback_preference": user.playback_preference,
        },
    }


# --- Logout ---

@router.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("djwala_session")
    if session_id and _db:
        _db.delete_session(session_id)
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("djwala_session", path="/")
    return response


# --- Google OAuth ---

@router.get("/google/login")
async def google_login(request: Request):
    if not _settings or not _settings.google_enabled:
        raise HTTPException(404, "Google login not configured")
    state = _sign_state(secrets.token_urlsafe(16))
    base = _get_base_url(request)
    params = {
        "client_id": _settings.google_client_id,
        "redirect_uri": f"{base}/auth/google/callback",
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
    response = RedirectResponse(url, status_code=302)
    response.set_cookie("oauth_state", state, httponly=True, secure=True,
                         samesite="lax", max_age=300, path="/")
    return response


@router.get("/google/callback")
async def google_callback(request: Request, code: str = "", state: str = ""):
    if not _settings or not _settings.google_enabled or not _db:
        raise HTTPException(404, "Google login not configured")

    # Verify CSRF state
    stored_state = request.cookies.get("oauth_state", "")
    if not stored_state or stored_state != state:
        raise HTTPException(400, "Invalid OAuth state")
    if not _verify_state(state):
        raise HTTPException(400, "Invalid OAuth state signature")

    base = _get_base_url(request)
    # Exchange code for tokens
    token_resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": _settings.google_client_id,
        "client_secret": _settings.google_client_secret,
        "redirect_uri": f"{base}/auth/google/callback",
        "grant_type": "authorization_code",
    }, timeout=10)
    if token_resp.status_code != 200:
        logger.error("Google token exchange failed: %s", token_resp.text)
        raise HTTPException(502, "Google authentication failed")

    tokens = token_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", 3600)
    expires_at = int(time.time()) + expires_in

    # Fetch user profile
    profile_resp = http_requests.get(GOOGLE_USERINFO_URL, headers={
        "Authorization": f"Bearer {access_token}"
    }, timeout=10)
    if profile_resp.status_code != 200:
        raise HTTPException(502, "Failed to fetch Google profile")

    profile = profile_resp.json()
    google_id = profile["id"]
    display_name = profile.get("name", "User")
    avatar_url = profile.get("picture")

    # Check if this is a "link" flow (user already logged in)
    existing_user = get_current_user(request)
    if existing_user:
        try:
            _db.link_google(
                user_id=existing_user.id, google_id=google_id,
                access_token=access_token, refresh_token=refresh_token,
                expires_at=expires_at,
            )
        except ValueError as e:
            raise HTTPException(409, str(e))
        response = RedirectResponse("/", status_code=302)
        response.delete_cookie("oauth_state", path="/")
        return response

    # Find or create user
    user = _db.find_or_create_google(
        google_id=google_id, display_name=display_name,
        avatar_url=avatar_url,
        access_token=access_token, refresh_token=refresh_token,
        expires_at=expires_at,
    )

    # Create auth session
    auth_session = _db.create_session(user.id)
    response = RedirectResponse("/", status_code=302)
    _set_session_cookie(response, auth_session.session_id)
    response.delete_cookie("oauth_state", path="/")
    return response


# --- Spotify OAuth ---

@router.get("/spotify/login")
async def spotify_login(request: Request):
    if not _settings or not _settings.spotify_enabled:
        raise HTTPException(404, "Spotify login not configured")
    state = _sign_state(secrets.token_urlsafe(16))
    base = _get_base_url(request)
    params = {
        "client_id": _settings.spotify_client_id,
        "redirect_uri": f"{base}/auth/spotify/callback",
        "response_type": "code",
        "scope": SPOTIFY_SCOPES,
        "state": state,
    }
    url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"
    response = RedirectResponse(url, status_code=302)
    response.set_cookie("oauth_state", state, httponly=True, secure=True,
                         samesite="lax", max_age=300, path="/")
    return response


@router.get("/spotify/callback")
async def spotify_callback(request: Request, code: str = "", state: str = ""):
    if not _settings or not _settings.spotify_enabled or not _db:
        raise HTTPException(404, "Spotify login not configured")

    stored_state = request.cookies.get("oauth_state", "")
    if not stored_state or stored_state != state:
        raise HTTPException(400, "Invalid OAuth state")
    if not _verify_state(state):
        raise HTTPException(400, "Invalid OAuth state signature")

    base = _get_base_url(request)
    token_resp = http_requests.post(SPOTIFY_TOKEN_URL, data={
        "code": code,
        "client_id": _settings.spotify_client_id,
        "client_secret": _settings.spotify_client_secret,
        "redirect_uri": f"{base}/auth/spotify/callback",
        "grant_type": "authorization_code",
    }, timeout=10)
    if token_resp.status_code != 200:
        logger.error("Spotify token exchange failed: %s", token_resp.text)
        raise HTTPException(502, "Spotify authentication failed")

    tokens = token_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    expires_in = tokens.get("expires_in", 3600)
    expires_at = int(time.time()) + expires_in

    # Fetch Spotify profile
    profile_resp = http_requests.get(SPOTIFY_ME_URL, headers={
        "Authorization": f"Bearer {access_token}"
    }, timeout=10)
    if profile_resp.status_code != 200:
        raise HTTPException(502, "Failed to fetch Spotify profile")

    profile = profile_resp.json()
    spotify_id = profile["id"]
    display_name = profile.get("display_name") or profile.get("id")
    images = profile.get("images", [])
    avatar_url = images[0]["url"] if images else None
    is_premium = profile.get("product") == "premium"

    # Check if this is a "link" flow
    existing_user = get_current_user(request)
    if existing_user:
        try:
            _db.link_spotify(
                user_id=existing_user.id, spotify_id=spotify_id,
                access_token=access_token, refresh_token=refresh_token,
                expires_at=expires_at, is_premium=is_premium,
            )
        except ValueError as e:
            raise HTTPException(409, str(e))
        response = RedirectResponse("/", status_code=302)
        response.delete_cookie("oauth_state", path="/")
        return response

    user = _db.find_or_create_spotify(
        spotify_id=spotify_id, display_name=display_name,
        avatar_url=avatar_url,
        access_token=access_token, refresh_token=refresh_token,
        expires_at=expires_at, is_premium=is_premium,
    )

    auth_session = _db.create_session(user.id)
    response = RedirectResponse("/", status_code=302)
    _set_session_cookie(response, auth_session.session_id)
    response.delete_cookie("oauth_state", path="/")
    return response


# --- Link routes (redirect to same OAuth flow when user is already logged in) ---

@router.get("/link/google")
async def link_google(request: Request):
    """Redirect to Google OAuth to link Google to existing account."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Must be logged in to link accounts")
    return await google_login(request)


@router.get("/link/spotify")
async def link_spotify(request: Request):
    """Redirect to Spotify OAuth to link Spotify to existing account."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Must be logged in to link accounts")
    return await spotify_login(request)


# --- Spotify Player Token ---

@router.get("/spotify/player-token")
async def spotify_player_token(request: Request):
    """Return a fresh Spotify access token for the Web Playback SDK."""
    user = get_current_user(request)
    if not user or not user.has_spotify:
        raise HTTPException(401, "Spotify not connected")
    if not user.spotify_is_premium:
        raise HTTPException(403, "Spotify Premium required for playback")

    # Refresh token if expired
    if user.spotify_token_expires_at and time.time() > user.spotify_token_expires_at - 60:
        from djwala.providers import refresh_spotify_token
        new_token, new_expires = refresh_spotify_token(
            user.spotify_refresh_token, _settings
        )
        _db.update_spotify_tokens(user.id, new_token, new_expires)
        return {"access_token": new_token}

    return {"access_token": user.spotify_access_token}


# --- Playback Preference ---

@router.post("/playback-preference")
async def update_playback_preference(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Must be logged in")
    body = await request.json()
    pref = body.get("preference", "youtube")
    if pref not in ("youtube", "spotify"):
        raise HTTPException(400, "Invalid preference")
    if pref == "spotify" and not user.spotify_is_premium:
        raise HTTPException(403, "Spotify Premium required")
    _db.update_playback_preference(user.id, pref)
    return {"preference": pref}
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_auth.py -v --tb=short
```

**Step 5: Run ALL tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

**Step 6: Commit**

```bash
git add src/djwala/auth.py tests/test_auth.py pyproject.toml
git commit -m "feat(auth): add OAuth routes, session middleware, CSRF protection"
```

---

## Task 5: Providers Module — Google & Spotify API Wrappers

**Files:**
- Create: `src/djwala/providers.py`
- Test: `tests/test_providers.py` (new)

**Step 1: Write tests**

```python
# tests/test_providers.py
"""Tests for Google/Spotify API provider wrappers."""
from unittest.mock import patch, MagicMock
import pytest

from djwala.providers import (
    fetch_youtube_playlists,
    fetch_youtube_playlist_tracks,
    fetch_spotify_playlists,
    fetch_spotify_playlist_tracks,
    fetch_spotify_audio_features,
    search_spotify_track,
    refresh_spotify_token,
    refresh_google_token,
    spotify_features_to_analysis,
)
from djwala.models import TrackAnalysis


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@patch("djwala.providers.http_requests.get")
def test_fetch_youtube_playlists(mock_get):
    mock_get.return_value = _mock_response({
        "items": [
            {
                "id": "PL123",
                "snippet": {"title": "My Playlist", "thumbnails": {"default": {"url": "http://img"}}},
                "contentDetails": {"itemCount": 10},
            }
        ]
    })
    playlists = fetch_youtube_playlists("fake_token")
    assert len(playlists) == 1
    assert playlists[0]["id"] == "PL123"
    assert playlists[0]["name"] == "My Playlist"
    assert playlists[0]["track_count"] == 10
    assert playlists[0]["source"] == "youtube"


@patch("djwala.providers.http_requests.get")
def test_fetch_spotify_playlists(mock_get):
    mock_get.return_value = _mock_response({
        "items": [
            {
                "id": "sp_pl_1",
                "name": "Chill Vibes",
                "images": [{"url": "http://img"}],
                "tracks": {"total": 34},
            }
        ]
    })
    playlists = fetch_spotify_playlists("fake_token")
    assert len(playlists) == 1
    assert playlists[0]["name"] == "Chill Vibes"
    assert playlists[0]["source"] == "spotify"


@patch("djwala.providers.http_requests.get")
def test_fetch_spotify_audio_features(mock_get):
    mock_get.return_value = _mock_response({
        "audio_features": [
            {
                "id": "track1",
                "tempo": 128.0,
                "key": 0,
                "mode": 1,
                "energy": 0.75,
                "duration_ms": 210000,
                "danceability": 0.8,
                "valence": 0.6,
            }
        ]
    })
    features = fetch_spotify_audio_features(["track1"], "fake_token")
    assert len(features) == 1
    assert features[0]["tempo"] == 128.0


def test_spotify_features_to_analysis():
    features = {
        "id": "track1",
        "tempo": 128.0,
        "key": 0,
        "mode": 1,
        "energy": 0.75,
        "duration_ms": 210000,
        "danceability": 0.8,
        "valence": 0.6,
    }
    analysis = spotify_features_to_analysis(
        features, title="Test Track", video_id="yt_123",
    )
    assert isinstance(analysis, TrackAnalysis)
    assert analysis.bpm == 128.0
    assert analysis.key == "C"        # key=0, mode=1 → C major
    assert analysis.camelot == "8B"   # C major → 8B
    assert analysis.duration == 210.0
    assert analysis.video_id == "yt_123"
    assert len(analysis.energy_curve) == 210


@patch("djwala.providers.http_requests.post")
def test_refresh_spotify_token(mock_post):
    mock_post.return_value = _mock_response({
        "access_token": "new_token",
        "expires_in": 3600,
    })
    settings = MagicMock()
    settings.spotify_client_id = "cid"
    settings.spotify_client_secret = "csecret"
    token, expires = refresh_spotify_token("old_refresh", settings)
    assert token == "new_token"
    assert expires > 0
```

**Step 2: Implement providers.py**

```python
# src/djwala/providers.py
"""Google/Spotify API wrappers — profiles, playlists, audio features."""

from __future__ import annotations

import logging
import time

import requests as http_requests

from djwala.models import TrackAnalysis, TrackInfo, spotify_key_to_name, spotify_key_to_camelot

logger = logging.getLogger(__name__)

# --- YouTube / Google ---

YT_PLAYLISTS_URL = "https://www.googleapis.com/youtube/v3/playlists"
YT_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

SPOTIFY_PLAYLISTS_URL = "https://api.spotify.com/v1/me/playlists"
SPOTIFY_PLAYLIST_TRACKS_URL = "https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
SPOTIFY_AUDIO_FEATURES_URL = "https://api.spotify.com/v1/audio-features"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def fetch_youtube_playlists(access_token: str) -> list[dict]:
    """Fetch user's YouTube playlists."""
    resp = http_requests.get(YT_PLAYLISTS_URL, params={
        "mine": "true",
        "part": "snippet,contentDetails",
        "maxResults": 50,
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    playlists = []
    # Add Liked Videos as virtual playlist
    playlists.append({
        "id": "LL",
        "name": "Liked Videos",
        "image_url": None,
        "track_count": 0,
        "source": "youtube",
    })
    for item in items:
        playlists.append({
            "id": item["id"],
            "name": item["snippet"]["title"],
            "image_url": item["snippet"].get("thumbnails", {}).get("default", {}).get("url"),
            "track_count": item["contentDetails"]["itemCount"],
            "source": "youtube",
        })
    return playlists


def fetch_youtube_playlist_tracks(playlist_id: str, access_token: str, max_tracks: int = 50) -> list[TrackInfo]:
    """Fetch tracks from a YouTube playlist."""
    tracks = []
    page_token = None
    while len(tracks) < max_tracks:
        params = {
            "playlistId": playlist_id,
            "part": "snippet,contentDetails",
            "maxResults": min(50, max_tracks - len(tracks)),
        }
        if page_token:
            params["pageToken"] = page_token
        resp = http_requests.get(YT_PLAYLIST_ITEMS_URL, params=params,
                                  headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            video_id = item["contentDetails"]["videoId"]
            title = item["snippet"]["title"]
            # Duration requires a separate videos.list call; use 0 as placeholder
            tracks.append(TrackInfo(video_id=video_id, title=title, duration=0.0,
                                    channel=item["snippet"].get("videoOwnerChannelTitle", "")))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    # Fetch durations in batch
    if tracks:
        video_ids = [t.video_id for t in tracks]
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            resp = http_requests.get(YT_VIDEOS_URL, params={
                "id": ",".join(batch),
                "part": "contentDetails",
            }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
            resp.raise_for_status()
            for vid_item in resp.json().get("items", []):
                vid_id = vid_item["id"]
                duration_iso = vid_item["contentDetails"]["duration"]
                duration_sec = _parse_iso8601_duration(duration_iso)
                for t in tracks:
                    if t.video_id == vid_id:
                        t.duration = duration_sec
                        break

    return tracks


def _parse_iso8601_duration(duration: str) -> float:
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return float(hours * 3600 + minutes * 60 + seconds)


# --- Spotify ---

def fetch_spotify_playlists(access_token: str) -> list[dict]:
    """Fetch user's Spotify playlists."""
    resp = http_requests.get(SPOTIFY_PLAYLISTS_URL, params={
        "limit": 50,
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "image_url": item["images"][0]["url"] if item.get("images") else None,
            "track_count": item["tracks"]["total"],
            "source": "spotify",
        }
        for item in items
    ]


def fetch_spotify_playlist_tracks(playlist_id: str, access_token: str, max_tracks: int = 100) -> list[dict]:
    """Fetch tracks from a Spotify playlist. Returns list of Spotify track objects."""
    url = SPOTIFY_PLAYLIST_TRACKS_URL.format(playlist_id=playlist_id)
    resp = http_requests.get(url, params={
        "limit": min(100, max_tracks),
        "fields": "items(track(id,name,artists,duration_ms,uri)),next",
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    tracks = []
    for item in items:
        track = item.get("track")
        if track and track.get("id"):
            artists = ", ".join(a["name"] for a in track.get("artists", []))
            tracks.append({
                "spotify_id": track["id"],
                "name": track["name"],
                "artists": artists,
                "duration_ms": track["duration_ms"],
                "uri": track.get("uri", ""),
            })
    return tracks


def fetch_spotify_audio_features(track_ids: list[str], access_token: str) -> list[dict]:
    """Fetch audio features for up to 100 Spotify tracks."""
    if not track_ids:
        return []
    resp = http_requests.get(SPOTIFY_AUDIO_FEATURES_URL, params={
        "ids": ",".join(track_ids[:100]),
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    features = resp.json().get("audio_features", [])
    return [f for f in features if f is not None]


def search_spotify_track(query: str, access_token: str) -> dict | None:
    """Search Spotify for a track. Returns first result or None."""
    resp = http_requests.get(SPOTIFY_SEARCH_URL, params={
        "q": query,
        "type": "track",
        "limit": 1,
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("tracks", {}).get("items", [])
    if not items:
        return None
    track = items[0]
    artists = ", ".join(a["name"] for a in track.get("artists", []))
    return {
        "spotify_id": track["id"],
        "name": track["name"],
        "artists": artists,
        "duration_ms": track["duration_ms"],
        "uri": track.get("uri", ""),
    }


def spotify_features_to_analysis(
    features: dict, *, title: str, video_id: str,
    spotify_uri: str = "",
) -> TrackAnalysis:
    """Convert Spotify Audio Features to a TrackAnalysis object."""
    bpm = features.get("tempo", 120.0)
    key_num = features.get("key", -1)
    mode = features.get("mode", 0)
    energy = features.get("energy", 0.5)
    duration_ms = features.get("duration_ms", 240000)
    duration = duration_ms / 1000.0

    key_name = spotify_key_to_name(key_num, mode)
    camelot = spotify_key_to_camelot(key_num, mode)

    # Create flat energy curve (Spotify gives single value, not per-second)
    energy_curve = [round(energy, 3)] * int(duration)

    # Estimate mix points based on energy
    mix_in = 8.0 if energy > 0.5 else 12.0
    mix_out = max(duration - 16.0, mix_in + 30.0)

    return TrackAnalysis(
        video_id=video_id,
        title=title,
        duration=duration,
        bpm=round(bpm, 1),
        key=key_name,
        camelot=camelot,
        energy_curve=energy_curve,
        mix_in_point=round(mix_in, 1),
        mix_out_point=round(mix_out, 1),
    )


# --- Token Refresh ---

def refresh_spotify_token(refresh_token: str, settings) -> tuple[str, int]:
    """Refresh Spotify access token. Returns (new_access_token, expires_at)."""
    resp = http_requests.post(SPOTIFY_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.spotify_client_id,
        "client_secret": settings.spotify_client_secret,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    new_token = data["access_token"]
    expires_at = int(time.time()) + data.get("expires_in", 3600)
    return new_token, expires_at


def refresh_google_token(refresh_token: str, settings) -> tuple[str, int]:
    """Refresh Google access token. Returns (new_access_token, expires_at)."""
    resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    new_token = data["access_token"]
    expires_at = int(time.time()) + data.get("expires_in", 3600)
    return new_token, expires_at
```

**Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/test_providers.py -v --tb=short
```

**Step 4: Run ALL tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

**Step 5: Commit**

```bash
git add src/djwala/providers.py tests/test_providers.py
git commit -m "feat(providers): add Google/Spotify API wrappers for playlists and audio features"
```

---

## Task 6: Session Manager — Playlist Mode + Spotify Analysis

**Files:**
- Modify: `src/djwala/session.py`
- Modify: `src/djwala/main.py` (add playlist fields to SessionCreate)
- Test: `tests/test_integration.py` (add playlist mode tests)

**Step 1: Write tests**

Add to `tests/test_integration.py` (or create new `tests/test_playlist_mode.py`):

```python
# tests/test_playlist_mode.py
"""Tests for playlist mode in session manager."""
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from djwala.session import SessionManager, SessionStatus
from djwala.models import InputMode, TrackAnalysis, TrackInfo


@pytest.fixture
def manager(tmp_path):
    return SessionManager(database_path=str(tmp_path / "test.db"))


def _make_track(video_id: str, bpm: float = 120.0) -> TrackAnalysis:
    return TrackAnalysis(
        video_id=video_id, title=f"Track {video_id}", duration=240.0,
        bpm=bpm, key="Am", camelot="8A", energy_curve=[0.5] * 10,
        mix_in_point=2.0, mix_out_point=220.0,
    )


def test_create_playlist_session(manager):
    session = manager.create_session(
        InputMode.PLAYLIST, "my-playlist",
        playlist_id="PL123", playlist_source="youtube",
    )
    assert session.mode == InputMode.PLAYLIST
    assert session.playlist_id == "PL123"
    assert session.playlist_source == "youtube"


async def test_build_playlist_queue_spotify(manager):
    """Playlist mode with Spotify source uses Audio Features."""
    session = manager.create_session(
        InputMode.PLAYLIST, "test-playlist",
        playlist_id="sp_pl_1", playlist_source="spotify",
    )

    mock_tracks = [
        {"spotify_id": "t1", "name": "Track 1", "artists": "Artist A",
         "duration_ms": 240000, "uri": "spotify:track:t1"},
        {"spotify_id": "t2", "name": "Track 2", "artists": "Artist B",
         "duration_ms": 200000, "uri": "spotify:track:t2"},
    ]
    mock_features = [
        {"id": "t1", "tempo": 128.0, "key": 0, "mode": 1, "energy": 0.7,
         "duration_ms": 240000, "danceability": 0.8, "valence": 0.6},
        {"id": "t2", "tempo": 130.0, "key": 7, "mode": 1, "energy": 0.8,
         "duration_ms": 200000, "danceability": 0.9, "valence": 0.7},
    ]

    with patch("djwala.session.fetch_spotify_playlist_tracks", return_value=mock_tracks):
        with patch("djwala.session.fetch_spotify_audio_features", return_value=mock_features):
            with patch("djwala.session.search_youtube_for_spotify_track",
                       side_effect=lambda name, artists, **kw: TrackInfo(
                           video_id=f"yt_{name.replace(' ', '')}", title=name, duration=240.0)):
                await manager.build_queue(session.session_id,
                                          spotify_token="fake_token")

    assert session.status == SessionStatus.READY
    assert len(session.queue) == 2
```

**Step 2: Modify session.py**

Add `playlist_id` and `playlist_source` to Session dataclass. Add `_build_playlist_queue` method. Key changes:

- `Session` gets new fields: `playlist_id: str | None = None`, `playlist_source: str | None = None`
- `build_queue` dispatches to `_build_playlist_queue` when mode is PLAYLIST
- `_build_playlist_queue` calls providers for track listing + audio features
- For Spotify source: gets Audio Features → `spotify_features_to_analysis()` → DJ Brain ordering
- For YouTube source: gets playlist tracks → librosa analysis (or Spotify if available)
- `create_session` accepts optional `playlist_id` and `playlist_source`

**Step 3: Modify main.py SessionCreate**

Add optional fields:
```python
class SessionCreate(BaseModel):
    mode: str
    query: str
    youtube_api_key: str | None = None
    mix_length: int = Field(default=50, ge=0, le=100)
    playlist_id: str | None = None
    playlist_source: str | None = None  # "youtube" or "spotify"
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_playlist_mode.py -v --tb=short
```

**Step 5: Run ALL tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

**Step 6: Commit**

```bash
git add src/djwala/session.py src/djwala/main.py tests/test_playlist_mode.py
git commit -m "feat(session): add playlist mode with Spotify/YouTube playlist import"
```

---

## Task 7: Main.py Integration — Mount Auth Routes + Playlists API

**Files:**
- Modify: `src/djwala/main.py`
- Test: `tests/test_api.py` (add playlists tests)

**Step 1: Add tests**

Add to `tests/test_api.py`:

```python
async def test_playlists_unauthenticated(client):
    """GET /api/playlists without login returns 401."""
    resp = await client.get("/api/playlists")
    assert resp.status_code == 401


async def test_auth_status_endpoint(client):
    """GET /auth/status returns OAuth config."""
    resp = await client.get("/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "oauth_enabled" in data
```

**Step 2: Modify main.py**

Key changes to `src/djwala/main.py`:
- Import and mount auth router
- Initialize UserDB and pass to auth module
- Add `GET /api/playlists` endpoint
- Pass auth user's tokens to session manager when creating playlist sessions

```python
# Near top of main.py, after existing imports:
from djwala.auth import router as auth_router, init_auth, get_current_user
from djwala.db import UserDB

# After manager initialization:
user_db = UserDB(db_path=settings.database_path)
init_auth(settings, user_db)
app.include_router(auth_router)

# New endpoint:
@app.get("/api/playlists")
async def get_playlists(request: Request):
    """Return user's playlists from connected providers."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Login required")
    # ... fetch from YouTube and/or Spotify based on user's connected providers
```

**Step 3: Update create_session to pass playlist fields**

```python
@app.post("/session")
async def create_session(request: Request, req: SessionCreate):
    # ... existing code ...
    session = manager.create_session(
        mode, req.query,
        youtube_api_key=req.youtube_api_key,
        mix_length=req.mix_length,
        playlist_id=req.playlist_id,
        playlist_source=req.playlist_source,
    )
    # For playlist mode, pass user's tokens
    user = get_current_user(request)
    spotify_token = user.spotify_access_token if user and user.has_spotify else None
    google_token = user.google_access_token if user and user.has_google else None
    task = asyncio.create_task(
        manager.build_queue(session.session_id,
                            spotify_token=spotify_token,
                            google_token=google_token),
    )
    # ... rest unchanged ...
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

**Step 5: Commit**

```bash
git add src/djwala/main.py tests/test_api.py
git commit -m "feat(main): mount auth routes, add playlists API, wire up playlist mode"
```

---

## Task 8: Frontend — Login UI + Auth State

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/app.js`
- Modify: `static/css/style.css`

**Step 1: Add login buttons to index.html**

Above the existing hero form, add:
```html
<div id="auth-section" class="auth-section" style="display:none">
    <div id="auth-logged-out" class="auth-logged-out">
        <button class="btn-oauth btn-youtube" onclick="window.location='/auth/google/login'">
            🎵 Continue with YouTube
        </button>
        <button class="btn-oauth btn-spotify" onclick="window.location='/auth/spotify/login'">
            🎧 Continue with Spotify
        </button>
        <div class="auth-divider"><span>or skip login and mix now</span></div>
    </div>
    <div id="auth-logged-in" class="auth-logged-in" style="display:none">
        <!-- Filled by JS -->
    </div>
</div>
```

**Step 2: Add auth state management to app.js**

```javascript
// At startup, check auth status
async function checkAuth() {
    try {
        const resp = await fetch('/auth/status');
        const status = await resp.json();
        if (!status.oauth_enabled) return;  // OAuth not configured, hide buttons

        document.getElementById('auth-section').style.display = 'block';

        const meResp = await fetch('/auth/me');
        const me = await meResp.json();
        if (me.logged_in) {
            showLoggedIn(me.user);
        } else {
            showLoggedOut(status);
        }
    } catch (e) {
        console.warn('Auth check failed:', e);
    }
}
```

**Step 3: Add user dropdown**

When logged in, show avatar + name in top-right, with dropdown for:
- Connected accounts status
- Link YouTube / Link Spotify buttons
- Playback preference toggle
- Sign Out

**Step 4: Add CSS styles**

Style the login buttons (green outlined for YouTube, green filled for Spotify), the user dropdown, and the auth divider to match the existing Spotify-like theme.

**Step 5: Increment cache bust version**

Update all `?v=21` to `?v=22` in `index.html`.

**Step 6: Test manually**

```bash
# Start dev server
.venv/bin/python -m uvicorn djwala.main:app --reload
# Visit http://localhost:8000 — verify:
# 1. Login buttons appear if OAuth is configured (won't appear without env vars)
# 2. Existing flow (artists/song/mood) works without login
# 3. No JS errors in console
```

**Step 7: Commit**

```bash
git add static/index.html static/js/app.js static/css/style.css
git commit -m "feat(ui): add OAuth login buttons, user dropdown, auth state management"
```

---

## Task 9: Frontend — Playlist Picker

**Files:**
- Modify: `static/js/app.js`
- Modify: `static/css/style.css`
- Modify: `static/index.html`

**Step 1: Add Playlist mode to mode selector**

Add "Playlist" option to the mode `<select>` — only visible when logged in.

**Step 2: Implement playlist picker**

When "Playlist" mode is selected:
- Fetch `GET /api/playlists`
- Show playlists in a dropdown/list with provider icons (🎧/🎵)
- Clicking a playlist → POST /session with playlist_id + source

**Step 3: Style playlist picker**

Green accent colors, dark cards matching existing theme.

**Step 4: Test manually**

Verify playlist picker shows when logged in and Playlist mode is selected.

**Step 5: Commit**

```bash
git add static/js/app.js static/css/style.css static/index.html
git commit -m "feat(ui): add playlist picker mode with provider icons"
```

---

## Task 10: Frontend — Spotify Web Playback SDK

**Files:**
- Modify: `static/js/app.js`
- Modify: `static/index.html`

**Step 1: Load Spotify SDK conditionally**

```html
<!-- Only loaded when user has Spotify Premium and chooses Spotify playback -->
<script id="spotify-sdk" src="https://sdk.scdn.co/spotify-player.js" defer></script>
```

**Step 2: Implement Spotify player wrapper**

```javascript
class SpotifyPlayerWrapper {
    constructor() {
        this.player = null;
        this.deviceId = null;
        this.tokenRefreshInterval = null;
    }

    async init() {
        const tokenResp = await fetch('/auth/spotify/player-token');
        if (!tokenResp.ok) return false;
        const { access_token } = await tokenResp.json();

        this.player = new Spotify.Player({
            name: 'DjwalaAI',
            getOAuthToken: async cb => {
                const resp = await fetch('/auth/spotify/player-token');
                const data = await resp.json();
                cb(data.access_token);
            },
            volume: 1.0,
        });

        // ... event listeners, connect, error handling
    }

    async play(spotifyUri, seekMs = 0) {
        // PUT https://api.spotify.com/v1/me/player/play
    }

    setVolume(vol) { this.player?.setVolume(vol); }
    pause() { this.player?.pause(); }
    resume() { this.player?.resume(); }
}
```

**Step 3: Integrate with existing crossfade system**

The existing `MixCommand` system stays. When playback preference is Spotify:
- `loadVideoById()` calls → `spotifyPlayer.play(spotifyUri)`
- Volume fading uses Spotify's `setVolume()` instead of YouTube's

**Step 4: Add fallback logic**

If Spotify playback fails → fall back to YouTube for that track, show toast notification.

**Step 5: Test manually**

```bash
# Requires Spotify Premium account and configured OAuth
# Test: login → set playback to Spotify → start a mix → verify Spotify plays
```

**Step 6: Commit**

```bash
git add static/js/app.js static/index.html
git commit -m "feat(ui): add Spotify Web Playback SDK with YouTube fallback"
```

---

## Task 11: Privacy Page

**Files:**
- Create: `static/privacy.html`
- Modify: `src/djwala/main.py` (add /privacy route)

**Step 1: Create privacy.html**

Minimal privacy policy covering:
- What data we collect (name, email from OAuth, playlist access)
- How we use it (playlist import, playback, analysis)
- No third-party sharing
- How to delete account (email or unlink from settings)
- Cookie policy (session cookie only)

**Step 2: Add /privacy route**

```python
@app.get("/privacy")
async def privacy():
    from fastapi.responses import FileResponse
    privacy_page = STATIC_DIR / "privacy.html"
    if privacy_page.is_file():
        return FileResponse(privacy_page)
    raise HTTPException(404, "Privacy policy not found")
```

**Step 3: Commit**

```bash
git add static/privacy.html src/djwala/main.py
git commit -m "feat: add privacy policy page (required for OAuth)"
```

---

## Task 12: Integration Tests

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Add integration tests for full OAuth flow**

Test the complete flow with mocked HTTP requests:
- Google login → callback → session cookie set
- Spotify login → callback → session cookie set
- /auth/me returns user after login
- /api/playlists returns data for logged-in user
- Playlist mode creates session and builds queue
- Logout clears cookie

**Step 2: Run ALL tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

Expected: ALL tests pass (existing 141 + new tests).

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add OAuth integration tests for full login/playlist flow"
```

---

## Task 13: Deploy Configuration

**Files:**
- Modify: `fly.toml` (no secret values — just document)

**Step 1: Set Fly.io secrets**

```bash
fly secrets set \
  DJWALA_GOOGLE_CLIENT_ID=<from-gcp-console> \
  DJWALA_GOOGLE_CLIENT_SECRET=<from-gcp-console> \
  DJWALA_SPOTIFY_CLIENT_ID=<from-spotify-dashboard> \
  DJWALA_SPOTIFY_CLIENT_SECRET=<from-spotify-dashboard> \
  DJWALA_SESSION_SECRET=$(openssl rand -hex 32)
```

**Step 2: Register OAuth callback URLs**

- Google Cloud Console → Credentials → OAuth client → Authorized redirect URIs:
  `https://djwala-ai.fly.dev/auth/google/callback`
- Spotify Developer Dashboard → App Settings → Redirect URIs:
  `https://djwala-ai.fly.dev/auth/spotify/callback`

**Step 3: Deploy and verify**

```bash
fly deploy
# Test: visit https://djwala-ai.fly.dev
# 1. Login buttons visible
# 2. Google login flow works
# 3. Spotify login flow works
# 4. Playlist picker loads after login
# 5. Mix from playlist works
# 6. Existing anonymous flow still works
```

**Step 4: Commit any final config changes**

```bash
git add -A
git commit -m "chore: deployment config for OAuth integration"
```

---

## Execution Order & Dependencies

```
Task 1 (Models) ──┐
                   ├──→ Task 2 (DB) ──→ Task 3 (Config) ──→ Task 4 (Auth) ──→ Task 5 (Providers)
                   │                                                              │
                   │                                                              ▼
                   │                                              Task 6 (Session Manager)
                   │                                                              │
                   │                                                              ▼
                   │                                              Task 7 (Main.py Integration)
                   │                                                              │
                   │                    ┌──────────────────────────────────────────┤
                   │                    ▼                    ▼                     ▼
                   │            Task 8 (Login UI)   Task 9 (Playlists)   Task 10 (Spotify SDK)
                   │                    │                    │                     │
                   │                    └────────────────────┼─────────────────────┘
                   │                                        ▼
                   │                                Task 11 (Privacy)
                   │                                        │
                   │                                        ▼
                   └────────────────────────────→ Task 12 (Integration Tests)
                                                            │
                                                            ▼
                                                    Task 13 (Deploy)
```

Tasks 1-7 are strictly sequential (each depends on prior).
Tasks 8, 9, 10 can be parallelized (frontend work).
Tasks 11-13 are sequential final steps.
