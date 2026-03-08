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
