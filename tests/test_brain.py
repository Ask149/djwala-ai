# tests/test_brain.py
"""Tests for DJ Brain."""

import pytest
from djwala.brain import DJBrain
from djwala.models import TrackAnalysis


def _make_track(video_id: str, bpm: float, camelot: str, energy: float = 0.5) -> TrackAnalysis:
    """Helper to create a TrackAnalysis with minimal data."""
    duration = 240.0
    return TrackAnalysis(
        video_id=video_id,
        title=f"Track {video_id}",
        duration=duration,
        bpm=bpm,
        key="Am",
        camelot=camelot,
        energy_curve=[energy] * int(duration),
        mix_in_point=2.0,
        mix_out_point=duration - 16.0,
    )


class TestCamelotCompatibility:
    def test_same_key_compatible(self):
        brain = DJBrain()
        assert brain.keys_compatible("8A", "8A") is True

    def test_adjacent_number_compatible(self):
        brain = DJBrain()
        assert brain.keys_compatible("8A", "7A") is True
        assert brain.keys_compatible("8A", "9A") is True

    def test_same_number_different_letter_compatible(self):
        brain = DJBrain()
        assert brain.keys_compatible("8A", "8B") is True

    def test_far_keys_incompatible(self):
        brain = DJBrain()
        assert brain.keys_compatible("8A", "3B") is False

    def test_wrapping_12_to_1(self):
        brain = DJBrain()
        assert brain.keys_compatible("12A", "1A") is True


class TestBPMCompatibility:
    def test_same_bpm(self):
        brain = DJBrain()
        assert brain.bpm_compatible(128.0, 128.0) is True

    def test_within_5_percent(self):
        brain = DJBrain()
        assert brain.bpm_compatible(128.0, 134.0) is True  # ~4.7%

    def test_too_far_apart(self):
        brain = DJBrain()
        assert brain.bpm_compatible(128.0, 150.0) is False


class TestPlaylistOrdering:
    def test_orders_by_bpm(self):
        brain = DJBrain()
        tracks = [
            _make_track("c", 130.0, "8A"),
            _make_track("a", 120.0, "8A"),
            _make_track("b", 125.0, "8A"),
        ]
        ordered = brain.order_playlist(tracks)
        bpms = [t.bpm for t in ordered]
        assert bpms == sorted(bpms)  # should be ascending

    def test_empty_playlist(self):
        brain = DJBrain()
        assert brain.order_playlist([]) == []

    def test_single_track(self):
        brain = DJBrain()
        tracks = [_make_track("a", 128.0, "8A")]
        assert brain.order_playlist(tracks) == tracks


class TestCrossfadeDuration:
    def test_chill_longer_fade(self):
        brain = DJBrain()
        low_energy = _make_track("a", 110.0, "8A", energy=0.3)
        duration = brain.crossfade_duration(low_energy, low_energy)
        assert duration >= 14  # chill = longer crossfade

    def test_high_energy_shorter_fade(self):
        brain = DJBrain()
        high_energy = _make_track("a", 140.0, "8A", energy=0.8)
        duration = brain.crossfade_duration(high_energy, high_energy)
        assert duration <= 12  # high energy = shorter crossfade
