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
