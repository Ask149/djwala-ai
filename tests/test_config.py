"""Tests for configuration module."""

import os
import pytest
from djwala.config import Settings


def test_config_defaults():
    """Config provides reasonable defaults when no env vars set."""
    settings = Settings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.cors_origins == ["*"]
    assert settings.rate_limit == "5/minute"
    assert settings.database_path == "djwala_cache.db"


def test_config_env_override(monkeypatch):
    """Config reads from DJWALA_* environment variables."""
    monkeypatch.setenv("DJWALA_HOST", "127.0.0.1")
    monkeypatch.setenv("DJWALA_PORT", "9000")
    monkeypatch.setenv("DJWALA_CORS_ORIGINS", '["http://localhost:3000"]')
    monkeypatch.setenv("DJWALA_RATE_LIMIT", "10/minute")
    monkeypatch.setenv("DJWALA_DATABASE_PATH", "custom.db")
    
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 9000
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.rate_limit == "10/minute"
    assert settings.database_path == "custom.db"


def test_oauth_disabled_by_default():
    """OAuth is disabled when no client IDs configured."""
    s = Settings()
    assert not s.oauth_enabled


def test_oauth_enabled_with_google():
    """OAuth enabled when Google credentials present."""
    s = Settings(google_client_id="id", google_client_secret="secret")
    assert s.oauth_enabled
    assert s.google_enabled
    assert not s.spotify_enabled


def test_oauth_enabled_with_spotify():
    """OAuth enabled when Spotify credentials present."""
    s = Settings(spotify_client_id="id", spotify_client_secret="secret")
    assert s.oauth_enabled
    assert not s.google_enabled
    assert s.spotify_enabled


def test_session_secret_default_none():
    s = Settings()
    assert s.session_secret is None
