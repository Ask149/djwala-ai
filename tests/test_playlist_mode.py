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


@pytest.mark.asyncio
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
