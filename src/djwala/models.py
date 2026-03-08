"""Data models for DjwalaAI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InputMode(str, Enum):
    ARTISTS = "artists"
    SONG = "song"
    MOOD = "mood"
    PLAYLIST = "playlist"


@dataclass
class TrackInfo:
    """Basic track info from YouTube search (before analysis)."""
    video_id: str
    title: str
    duration: float  # seconds
    channel: str = ""


@dataclass
class TrackAnalysis:
    """Full DJ analysis of a track."""
    video_id: str
    title: str
    duration: float
    bpm: float
    key: str                          # e.g., "Am"
    camelot: str                      # e.g., "8A"
    energy_curve: list[float] = field(default_factory=list)  # per-second energy
    mix_in_point: float = 0.0        # seconds — where to start playing this track
    mix_out_point: float = 0.0       # seconds — where to start fading out


@dataclass
class MixCommand:
    """Command sent to frontend to execute a crossfade."""
    action: str                       # "fade_to_next"
    current_fade_start: float         # seconds into current track to begin fade
    next_video_id: str
    next_seek_to: float               # seconds — where to seek incoming track
    fade_duration: float              # seconds — length of crossfade
    next_title: str = ""


# ── Spotify key helpers ──────────────────────────────────────────────

# Intentionally duplicated from analyzer.KEY_NAMES to avoid importing heavy audio deps
KEY_NAMES_SPOTIFY = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# CAMELOT_WHEEL uses flats (Db, Eb, Ab, Bb) but Spotify uses sharps — map between them
_ENHARMONIC = {"C#": "Db", "D#": "Eb", "G#": "Ab", "A#": "Bb"}


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
    result = CAMELOT_WHEEL.get((name, mode_str))
    if result is None:
        alt = _ENHARMONIC.get(name)
        if alt:
            result = CAMELOT_WHEEL.get((alt, mode_str))
    return result or "8A"


# ── Auth models ──────────────────────────────────────────────────────

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
