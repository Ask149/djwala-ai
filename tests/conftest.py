# tests/conftest.py
"""Shared test fixtures."""

import pytest
from djwala.models import TrackInfo, TrackAnalysis


@pytest.fixture
def sample_track_info() -> TrackInfo:
    return TrackInfo(
        video_id="dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up",
        duration=213.0,
        channel="Rick Astley",
    )


@pytest.fixture
def sample_analysis() -> TrackAnalysis:
    return TrackAnalysis(
        video_id="dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up",
        duration=213.0,
        bpm=113.0,
        key="Ab",
        camelot="4A",
        energy_curve=[0.3] * 213,
        mix_in_point=2.0,
        mix_out_point=195.0,
    )
