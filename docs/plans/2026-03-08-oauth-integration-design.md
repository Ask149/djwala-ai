# OAuth Integration Design — YouTube + Spotify

**Date:** 2026-03-08
**Status:** Approved
**Scope:** Full integration (Option C) — both Google/YouTube + Spotify OAuth, playlist import, Spotify playback for Premium users

---

## Decisions Summary

| Question | Decision |
|----------|----------|
| User accounts | Lightweight — user record + refresh tokens in SQLite, no mix history |
| Playlist import | Playlist as seed — pick playlist → extract tracks → analyze → DJ mix |
| Spotify playback | User chooses — toggle YouTube/Spotify, Premium detection, grayed if free |
| Google OAuth purpose | Identity + YouTube playlists — login + playlist import as mix seeds |
| Auth flow | Either provider creates account — sign in with YouTube OR Spotify |
| Account merging | No merge — link the other provider from settings explicitly |
| Architecture | Server-side sessions — FastAPI manages tokens, HTTP-only cookies |

---

## 1. Architecture Overview

```
┌─────────────────── Browser ───────────────────────┐
│                                                     │
│  Login: "Continue with YouTube" / "Continue with    │
│          Spotify" buttons                           │
│                                                     │
│  Playlist Picker: user's playlists as mix seeds     │
│                                                     │
│  Player: YouTube IFrame API  ←or→  Spotify Web      │
│          (default)                 Playback SDK      │
│                                   (Premium only)     │
│                                                     │
│  Session cookie (HTTP-only) ←──── auth state        │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│                FastAPI Backend                        │
│                                                      │
│  /auth/google/login     → Google OAuth redirect      │
│  /auth/google/callback  → exchange code, set cookie  │
│  /auth/spotify/login    → Spotify OAuth redirect     │
│  /auth/spotify/callback → exchange code, set cookie  │
│  /auth/me               → current user + providers   │
│  /auth/logout           → clear cookie               │
│  /auth/link/google      → link Google to existing    │
│  /auth/link/spotify     → link Spotify to existing   │
│  /auth/spotify/player-token → fresh token for SDK    │
│                                                      │
│  /api/playlists         → user's playlists (YT/SP)   │
│  /session (existing)    → now can use Spotify data    │
│                                                      │
│  SQLite: users + auth_sessions + track_analysis      │
└──────────────────────────────────────────────────────┘
```

**Key principle: The app works without login.** Current flow (type artists/song → yt-dlp search → librosa analysis → YouTube playback) remains the default. Login unlocks bonus features: playlist import, faster Spotify analysis, optional Spotify playback.

---

## 2. Database Schema

All in the existing SQLite database (`djwala_cache.db`). Three new tables alongside the existing `track_analysis` table.

```sql
-- Users: one row per person, flat columns for both providers
CREATE TABLE users (
    id TEXT PRIMARY KEY,                    -- uuid4
    display_name TEXT NOT NULL,
    avatar_url TEXT,

    -- Google / YouTube
    google_id TEXT UNIQUE,                  -- Google 'sub' claim
    google_access_token TEXT,
    google_refresh_token TEXT,
    google_token_expires_at INTEGER,        -- unix timestamp

    -- Spotify
    spotify_id TEXT UNIQUE,                 -- Spotify user ID
    spotify_access_token TEXT,
    spotify_refresh_token TEXT,
    spotify_token_expires_at INTEGER,       -- unix timestamp
    spotify_is_premium INTEGER DEFAULT 0,   -- 1 if premium

    -- Preferences
    playback_preference TEXT DEFAULT 'youtube',  -- 'youtube' or 'spotify'

    created_at TEXT NOT NULL                 -- ISO timestamp
);

-- Auth sessions: maps cookie → user
CREATE TABLE auth_sessions (
    session_id TEXT PRIMARY KEY,            -- uuid4, stored in cookie
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL                -- 30-day expiry
);
```

**Design choices:**

| Decision | Why |
|----------|-----|
| Flat user table | Only 2 providers, YAGNI. Fewer JOINs, simpler queries. |
| Tokens as plaintext | Fly.io volume is encrypted at rest. Revisit for multi-tenant. |
| 30-day session expiry | Long enough to stay logged in, short enough to avoid stale sessions. |
| `google_id` / `spotify_id` UNIQUE | Lookup path: OAuth callback gets provider ID → find or create user. |

---

## 3. Auth Flow

### OAuth 2.0 Authorization Code Flow

```
1. User clicks "Continue with YouTube" or "Continue with Spotify"
2. Frontend: window.location = "/auth/google/login" (or /auth/spotify/login)
3. Backend builds OAuth URL:
   - client_id, redirect_uri, scopes, state (CSRF token), response_type=code
   - state stored in short-lived secure cookie (5 min TTL)
4. Browser redirected to Google/Spotify consent screen
5. User approves → redirected to callback with code + state
6. Backend:
   a. Verify state matches cookie (CSRF protection)
   b. Exchange code for access_token + refresh_token
   c. Fetch user profile (name, avatar, email, premium status)
   d. Find or create user in SQLite
   e. Create auth_session row (uuid4, 30-day expiry)
   f. Set HTTP-only session cookie
   g. Redirect to "/"
7. Frontend: on page load, fetch GET /auth/me
   - Logged in → show user avatar, playlist picker
   - Not logged in → show login buttons
```

### Linking a Second Provider

Same OAuth flow via `/auth/link/{provider}`. Callback updates existing user's provider columns. If provider_id already belongs to a different user → error message.

### Scopes

| Provider | Scopes | Why |
|----------|--------|-----|
| Google | `openid`, `profile`, `email`, `youtube.readonly` | Identity + YouTube playlists |
| Spotify | `user-read-email`, `user-read-private`, `playlist-read-private`, `user-library-read`, `streaming` | Identity + playlists + Premium detection + Web Playback SDK |

### Token Refresh

Tokens expire (~1hr for both). Backend refreshes automatically when calling provider APIs (60s before expiry). Updated tokens stored back to SQLite.

### Session Cookie Settings

```python
response.set_cookie(
    key="djwala_session",
    value=session_id,
    httponly=True,       # JS can't read it
    secure=True,         # HTTPS only
    samesite="lax",      # CSRF protection
    max_age=30*86400,    # 30 days
    path="/",
)
```

---

## 4. Spotify Integration

### 4a. Audio Features — Replacing librosa

```
Current flow (no Spotify):
  yt-dlp search → download audio → librosa analyze (~3s/track) → BPM, key, energy

New flow (Spotify connected):
  Spotify search → Audio Features API (instant) → BPM, key, energy, danceability
  → map to YouTube video ID for playback (unless Spotify playback chosen)
```

**Mapping:**

| Spotify Field | Maps To | Notes |
|---------------|---------|-------|
| `tempo` | `bpm` | Direct float |
| `key` + `mode` | `key`, `camelot` | Pitch class → note name → Camelot code |
| `energy` | `energy_curve` | Flat curve `[energy] * duration` |
| `duration_ms` | `duration` | Convert to seconds |

### 4b. Playlist Import

1. `GET /api/playlists` → user's Spotify playlists
2. User picks one
3. `POST /session` with `mode: "playlist"`, `playlist_id`, `source: "spotify"`
4. Backend: fetch tracks → batch Audio Features (up to 100/request) → DJBrain ordering → map to YouTube if needed

### 4c. Spotify Web Playback SDK (Premium only)

- JS SDK turns browser into Spotify Connect device
- Backend serves fresh tokens via `GET /auth/spotify/player-token`
- Token refresh every 50 min
- Graceful degradation: Premium expired → fall back to YouTube with toast

---

## 5. YouTube Integration

### Playlist Import

- `GET /api/playlists` also returns YouTube playlists (via YouTube Data API v3 with user's OAuth token)
- Includes "Liked Videos" (playlist ID `LL`) as virtual playlist
- Same flow: pick playlist → extract tracks → analyze (librosa or Spotify if linked) → DJ order

### What Stays the Same

- yt-dlp remains primary search for non-playlist flows
- YouTube IFrame API remains default player
- Settings API key field kept for anonymous users, hidden when logged in

---

## 6. Frontend UX

### Login Screen (above existing hero)

```
[🎵 Continue with YouTube]     ← green outlined button
[🎧 Continue with Spotify ]    ← green filled button

─── or skip login and mix now ───

[ Artists ▾ ]  [ type artists... ] [ Mix! ]   ← existing, works without login
```

### Logged-In State

- Login buttons replaced by playlist picker + user avatar
- Playlists show provider icon (🎧/🎵)
- Clicking a playlist starts a mix session

### User Dropdown (top-right)

- Shows connected accounts, link/unlink options
- Playback toggle: YouTube / Spotify (grayed if not Premium)
- Replaces Settings modal for logged-in users
- Sign Out option

### Mode Selector

Add `Playlist` mode (only visible when logged in). Replaces text input with playlist dropdown.

---

## 7. Config, Dependencies & Deployment

### New Dependencies

```
"cryptography>=43.0"    # CSRF state cookie signing (Fernet)
```

### New Environment Variables

```
DJWALA_GOOGLE_CLIENT_ID
DJWALA_GOOGLE_CLIENT_SECRET
DJWALA_SPOTIFY_CLIENT_ID
DJWALA_SPOTIFY_CLIENT_SECRET
DJWALA_SESSION_SECRET          # 32+ byte random key
```

### New Files

```
src/djwala/auth.py         # OAuth routes, session middleware, token refresh
src/djwala/providers.py    # Google/Spotify API wrappers
src/djwala/db.py           # User/session CRUD (SQLite)
static/privacy.html        # Required by OAuth providers
```

### Modified Files

```
src/djwala/main.py         # Import auth routes
src/djwala/config.py       # Add OAuth fields
src/djwala/session.py      # Accept Spotify analysis data
src/djwala/models.py       # Add User, AuthSession models
static/index.html          # Login buttons, user dropdown
static/js/app.js           # Playlist picker, Spotify SDK, auth state
static/css/style.css       # Login/dropdown/playlist styles
```

### Backward Compatibility

- Anonymous users: everything works exactly as today
- Existing tests (141): no breakage, auth middleware skips when no cookie
- Existing SQLite cache: new tables added alongside `track_analysis`
- OAuth fields optional in config: login buttons hidden when not configured
