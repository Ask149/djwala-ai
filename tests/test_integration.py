# tests/test_integration.py
"""Integration tests — test component wiring (mocked YouTube/audio)."""

import pytest
from unittest.mock import patch, MagicMock
from djwala.models import InputMode, TrackInfo, TrackAnalysis
from djwala.session import SessionManager


def _mock_analysis(video_id: str, bpm: float, camelot: str) -> TrackAnalysis:
    return TrackAnalysis(
        video_id=video_id,
        title=f"Track {video_id}",
        duration=240.0,
        bpm=bpm,
        key="Am",
        camelot=camelot,
        energy_curve=[0.5] * 240,
        mix_in_point=2.0,
        mix_out_point=224.0,
    )


class TestIntegration:
    """Test the full pipeline with mocked external services."""

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_full_session_flow(self, MockCache, MockAnalyzer, MockYT):
        # Setup mocks
        mock_yt = MockYT.return_value
        mock_yt.search.return_value = [
            TrackInfo("vid1", "Track 1", 240, "Ch1"),
            TrackInfo("vid2", "Track 2", 200, "Ch2"),
            TrackInfo("vid3", "Track 3", 260, "Ch3"),
        ]

        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze.side_effect = [
            _mock_analysis("vid1", 124.0, "8A"),
            _mock_analysis("vid2", 126.0, "8B"),
            _mock_analysis("vid3", 128.0, "9A"),
        ]

        mock_cache = MockCache.return_value
        mock_cache.has.return_value = False

        # Run
        manager = SessionManager()
        session = manager.create_session(InputMode.ARTISTS, "Arijit Singh, Deadmau5")
        await manager.build_queue(session.session_id)

        # Verify
        session = manager.get_session(session.session_id)
        assert session.status.value == "ready"
        assert len(session.queue) == 3

        # Verify mix command
        mix_cmd = manager.get_mix_command(session.session_id)
        assert mix_cmd is not None
        assert mix_cmd.action == "fade_to_next"

        # Advance
        manager.advance(session.session_id)
        assert session.current_index == 1


class TestSongModeIntegration:
    """Test song mode: seed + mix playlist → ordered queue."""

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_song_mode_seed_first(self, MockCache, MockAnalyzer, MockYT):
        """Song mode: seed song is always first in queue."""
        mock_yt = MockYT.return_value
        mock_yt.search_song.return_value = TrackInfo("seed1", "Seed Song", 280, "Ch")
        mock_yt.get_mix_playlist.return_value = [
            TrackInfo("rel1", "Related 1", 240, "Ch"),
            TrackInfo("rel2", "Related 2", 200, "Ch"),
            TrackInfo("rel3", "Related 3", 260, "Ch"),
            TrackInfo("rel4", "Related 4", 220, "Ch"),
        ]

        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze.side_effect = [
            _mock_analysis("seed1", 120.0, "8A"),
            _mock_analysis("rel1", 122.0, "8B"),
            _mock_analysis("rel2", 118.0, "7A"),
            _mock_analysis("rel3", 124.0, "9A"),
            _mock_analysis("rel4", 126.0, "9B"),
        ]

        mock_cache = MockCache.return_value
        mock_cache.has.return_value = False

        manager = SessionManager()
        session = manager.create_session(InputMode.SONG, "Tum Hi Ho")
        await manager.build_queue(session.session_id)

        session = manager.get_session(session.session_id)
        assert session.status.value == "ready"
        assert session.queue[0].video_id == "seed1"  # Seed is ALWAYS first
        assert len(session.queue) == 5

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_song_mode_no_song_found(self, MockCache, MockAnalyzer, MockYT):
        """Song mode: error when seed song not found."""
        mock_yt = MockYT.return_value
        mock_yt.search_song.return_value = None

        mock_cache = MockCache.return_value

        manager = SessionManager()
        session = manager.create_session(InputMode.SONG, "nonexistent xyz")
        await manager.build_queue(session.session_id)

        session = manager.get_session(session.session_id)
        assert session.status.value == "error"
        assert "not found" in session.error.lower()

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_song_mode_empty_mix_playlist(self, MockCache, MockAnalyzer, MockYT):
        """Song mode: works with seed only if mix playlist is empty."""
        mock_yt = MockYT.return_value
        mock_yt.search_song.return_value = TrackInfo("seed1", "Lonely Song", 280, "Ch")
        mock_yt.get_mix_playlist.return_value = []

        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze.return_value = _mock_analysis("seed1", 120.0, "8A")

        mock_cache = MockCache.return_value
        mock_cache.has.return_value = False

        manager = SessionManager()
        session = manager.create_session(InputMode.SONG, "Lonely Song")
        await manager.build_queue(session.session_id)

        session = manager.get_session(session.session_id)
        assert session.status.value == "ready"
        assert len(session.queue) == 1
        assert session.queue[0].video_id == "seed1"


class TestQueueCleanup:
    """Test advance() trims old tracks."""

    def test_advance_trims_old_tracks(self):
        """After advancing past 3 tracks, old ones are trimmed."""
        manager = SessionManager()
        session = manager.create_session(InputMode.ARTISTS, "test")
        session.queue = [_mock_analysis(f"v{i}", 120.0, "8A") for i in range(10)]
        session.current_index = 0

        # Advance 5 times
        for _ in range(5):
            manager.advance(session.session_id)

        # After 5 advances: current_index was 5, trim should have happened
        # current_index > 3 triggers trim: trim = current_index - 3
        # Queue should be shorter, current_index adjusted
        assert session.current_index <= 3
        assert len(session.queue) < 10
        # Current track should still be accessible
        assert session.queue[session.current_index] is not None
