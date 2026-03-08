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
    assert len(playlists) == 2  # Liked Videos (virtual) + 1 real
    assert playlists[0]["id"] == "LL"  # Liked Videos always first
    assert playlists[1]["id"] == "PL123"
    assert playlists[1]["name"] == "My Playlist"
    assert playlists[1]["track_count"] == 10
    assert playlists[1]["source"] == "youtube"


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
