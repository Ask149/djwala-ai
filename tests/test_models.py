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
