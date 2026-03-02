"""Data models for DjwalaAI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InputMode(str, Enum):
    ARTISTS = "artists"
    SONG = "song"


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
