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

    stored_state = request.cookies.get("oauth_state", "")
    if not stored_state or stored_state != state:
        raise HTTPException(400, "Invalid OAuth state")
    if not _verify_state(state):
        raise HTTPException(400, "Invalid OAuth state signature")

    base = _get_base_url(request)
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

    profile_resp = http_requests.get(GOOGLE_USERINFO_URL, headers={
        "Authorization": f"Bearer {access_token}"
    }, timeout=10)
    if profile_resp.status_code != 200:
        raise HTTPException(502, "Failed to fetch Google profile")

    profile = profile_resp.json()
    google_id = profile["id"]
    display_name = profile.get("name", "User")
    avatar_url = profile.get("picture")

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

    user = _db.find_or_create_google(
        google_id=google_id, display_name=display_name,
        avatar_url=avatar_url,
        access_token=access_token, refresh_token=refresh_token,
        expires_at=expires_at,
    )

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


# --- Link routes ---

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
