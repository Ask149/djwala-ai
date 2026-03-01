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
