"""Tests for audio analyzer."""

import numpy as np
import pytest
from djwala.analyzer import AudioAnalyzer
from djwala.models import TrackInfo


@pytest.fixture
def analyzer():
    return AudioAnalyzer()


@pytest.fixture
def sample_track():
    return TrackInfo(
        video_id="test_video_123",
        title="Test Song",
        duration=240.0,
        channel="Test Channel"
    )


class TestBPMDetection:
    def test_returns_float(self, analyzer):
        # Generate a simple click track at 120 BPM (0.5s intervals)
        sr = 22050
        duration = 10
        y = np.zeros(sr * duration)
        interval = int(sr * 0.5)  # 120 BPM = 0.5s between beats
        for i in range(0, len(y), interval):
            y[i:i+100] = 1.0  # short click
        bpm = analyzer._detect_bpm(y, sr)
        assert isinstance(bpm, float)
        assert 100 < bpm < 140  # should be roughly 120

    def test_half_time_correction(self, analyzer):
        """BPM below 80 should be doubled (half-time detection fix).

        librosa often detects half-tempo for Bollywood, pop, and syncopated
        rhythms. Since DJ music below 80 BPM is extremely rare, we double it.
        """
        sr = 22050
        duration = 10
        # Generate a very slow click track at 65 BPM (0.923s intervals)
        # Without correction, librosa would return ~65 BPM
        y = np.zeros(sr * duration)
        interval = int(sr * (60.0 / 65.0))  # 65 BPM
        for i in range(0, len(y), interval):
            y[i:i+100] = 1.0
        bpm = analyzer._detect_bpm(y, sr)
        # After half-time correction, should be >= 80
        assert bpm >= 80.0, f"Expected BPM >= 80 after half-time correction, got {bpm}"

    def test_normal_bpm_not_doubled(self, analyzer):
        """BPM at or above 80 should NOT be doubled."""
        sr = 22050
        duration = 10
        # Generate click track at 100 BPM (0.6s intervals)
        y = np.zeros(sr * duration)
        interval = int(sr * 0.6)  # 100 BPM
        for i in range(0, len(y), interval):
            y[i:i+100] = 1.0
        bpm = analyzer._detect_bpm(y, sr)
        # Should stay around 100, not be doubled to 200
        assert 80 <= bpm <= 140, f"Expected BPM in 80-140 range, got {bpm}"


class TestKeyDetection:
    def test_returns_valid_key(self, analyzer):
        sr = 22050
        duration = 5
        # Generate a sine wave at A4 (440 Hz) — should detect A-related key
        t = np.linspace(0, duration, sr * duration)
        y = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        key, camelot = analyzer._detect_key(y, sr)
        assert isinstance(key, str)
        assert len(key) >= 1  # e.g., "Am", "C"
        assert isinstance(camelot, str)
        assert camelot[:-1].isdigit()  # e.g., "8A", "11B"


class TestEnergyCurve:
    def test_returns_per_second_values(self, analyzer):
        sr = 22050
        duration = 5
        y = np.random.randn(sr * duration).astype(np.float32) * 0.1
        curve = analyzer._compute_energy_curve(y, sr)
        assert len(curve) == duration
        assert all(isinstance(v, float) for v in curve)
        assert all(v >= 0 for v in curve)


class TestMixPoints:
    def test_mix_out_near_end(self, analyzer):
        energy_curve = [0.5] * 50 + [0.3] * 10  # energy drops at end
        duration = 60.0
        mix_out = analyzer._find_mix_out(energy_curve, duration)
        assert mix_out > 40  # should be in the last section

    def test_mix_in_skips_silence(self, analyzer):
        energy_curve = [0.01, 0.02, 0.1, 0.5, 0.6]  # quiet start
        mix_in = analyzer._find_mix_in(energy_curve)
        assert mix_in >= 2  # should skip the silence


class TestEstimate:
    def test_estimate_returns_valid_analysis(self, analyzer, sample_track):
        """Test that estimate() returns a valid TrackAnalysis with reasonable values."""
        result = analyzer.estimate(sample_track)
        
        assert result.video_id == sample_track.video_id
        assert result.title == sample_track.title
        assert result.duration == sample_track.duration
        
        # BPM should be in reasonable DJ range (not fixed 120.0)
        assert 78 <= result.bpm <= 145, f"BPM should be in DJ range, got {result.bpm}"
        
        # Key should be valid format
        assert result.key in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
                              "Am", "Cm", "Dm", "Em", "Gm"], f"Invalid key: {result.key}"
        assert result.camelot.endswith(("A", "B")), f"Invalid camelot: {result.camelot}"
        
        # Mix points should be reasonable (smart mix points skip intros/outros)
        assert result.mix_in_point > 0.0, "Should skip intro"
        assert result.mix_out_point < sample_track.duration - 16.0, "Should fade out earlier"
        assert result.mix_out_point - result.mix_in_point >= 60.0, "Should have at least 60s play time"
        
        # Energy curve should exist and be shaped (not flat)
        assert len(result.energy_curve) == int(sample_track.duration)
        assert all(0.0 <= v <= 1.0 for v in result.energy_curve), "Energy values should be 0-1"

    def test_estimate_handles_missing_duration(self, analyzer):
        """Test that estimate() handles tracks with no duration set."""
        track = TrackInfo(video_id="test", title="Test", duration=0.0)
        result = analyzer.estimate(track)
        
        assert result.duration == 240.0  # Default fallback
        # Smart mix points: should skip intro and fade out earlier
        assert result.mix_in_point > 0.0
        assert result.mix_out_point < 240.0 - 16.0
        assert len(result.energy_curve) == 240  # Should match duration
        assert all(0.0 <= v <= 1.0 for v in result.energy_curve)


class TestGenreAwareEstimation:
    """Test that estimate() returns varied values based on genre/artist hints."""

    def test_romantic_genre_gets_slower_bpm(self, analyzer):
        """Romantic songs should get BPM in 78-95 range."""
        track = TrackInfo(video_id="abc123", title="Tum Hi Ho - Romantic Song", duration=240.0)
        result = analyzer.estimate(track)
        assert 78 <= result.bpm <= 95, f"Romantic BPM should be 78-95, got {result.bpm}"

    def test_party_genre_gets_faster_bpm(self, analyzer):
        """Party songs should get BPM in 125-145 range."""
        track = TrackInfo(video_id="def456", title="Badtameez Dil - Party Song", duration=240.0)
        result = analyzer.estimate(track)
        assert 125 <= result.bpm <= 145, f"Party BPM should be 125-145, got {result.bpm}"

    def test_dance_genre_gets_medium_fast_bpm(self, analyzer):
        """Dance songs should get BPM in 120-140 range."""
        track = TrackInfo(video_id="ghi789", title="Kar Gayi Chull - Dance Mix", duration=240.0)
        result = analyzer.estimate(track)
        assert 120 <= result.bpm <= 140, f"Dance BPM should be 120-140, got {result.bpm}"

    def test_no_genre_gets_default_range(self, analyzer):
        """Songs with no genre keywords should get BPM in 95-130 range (Bollywood default)."""
        track = TrackInfo(video_id="jkl012", title="Some Random Song Title", duration=240.0)
        result = analyzer.estimate(track)
        assert 95 <= result.bpm <= 130, f"Default BPM should be 95-130, got {result.bpm}"

    def test_arijit_singh_gets_slower_range(self, analyzer):
        """Arijit Singh songs should narrow to 80-110 BPM."""
        track = TrackInfo(video_id="arijit123", title="Tum Hi Ho - Arijit Singh", duration=240.0)
        result = analyzer.estimate(track)
        assert 80 <= result.bpm <= 110, f"Arijit Singh BPM should be 80-110, got {result.bpm}"

    def test_ap_dhillon_gets_punjabi_range(self, analyzer):
        """AP Dhillon songs should narrow to 90-115 BPM."""
        track = TrackInfo(video_id="ap123", title="Brown Munde - AP Dhillon", duration=240.0)
        result = analyzer.estimate(track)
        assert 90 <= result.bpm <= 115, f"AP Dhillon BPM should be 90-115, got {result.bpm}"

    def test_badshah_gets_hip_hop_range(self, analyzer):
        """Badshah songs should narrow to 85-110 BPM."""
        track = TrackInfo(video_id="badshah123", title="Genda Phool - Badshah", duration=240.0)
        result = analyzer.estimate(track)
        assert 85 <= result.bpm <= 110, f"Badshah BPM should be 85-110, got {result.bpm}"

    def test_keys_vary_across_tracks(self, analyzer):
        """Different tracks should get different keys (not all Am)."""
        tracks = [
            TrackInfo(video_id=f"key{i}", title="Test Song", duration=240.0)
            for i in range(10)
        ]
        results = [analyzer.estimate(t) for t in tracks]
        keys = [r.key for r in results]
        assert len(set(keys)) >= 2, f"Expected key variation, got: {keys}"

    def test_same_track_gets_same_key(self, analyzer):
        """Same video_id should always return same key (deterministic)."""
        track = TrackInfo(video_id="consistent", title="Test", duration=240.0)
        result1 = analyzer.estimate(track)
        result2 = analyzer.estimate(track)
        assert result1.key == result2.key
        assert result1.camelot == result2.camelot

    def test_romantic_gets_low_energy_curve(self, analyzer):
        """Romantic songs should have lower energy values."""
        track = TrackInfo(video_id="rom1", title="Romantic Ballad", duration=240.0)
        result = analyzer.estimate(track)
        avg_energy = sum(result.energy_curve) / len(result.energy_curve)
        assert avg_energy < 0.5, f"Romantic avg energy should be < 0.5, got {avg_energy}"

    def test_party_gets_high_energy_curve(self, analyzer):
        """Party songs should have higher energy values."""
        track = TrackInfo(video_id="party1", title="Party Anthem", duration=240.0)
        result = analyzer.estimate(track)
        avg_energy = sum(result.energy_curve) / len(result.energy_curve)
        assert avg_energy > 0.5, f"Party avg energy should be > 0.5, got {avg_energy}"

    def test_energy_curves_not_flat(self, analyzer):
        """Energy curves should have some variation (not all identical values)."""
        track = TrackInfo(video_id="vary1", title="Test Song", duration=240.0)
        result = analyzer.estimate(track)
        unique_values = len(set(result.energy_curve))
        assert unique_values > 1, "Energy curve should vary, not be completely flat"

    def test_mix_in_point_nonzero_for_estimated_tracks(self, analyzer):
        """Estimated tracks should skip intro (mix_in_point > 0)."""
        track = TrackInfo(video_id="mix1", title="Test Song", duration=240.0)
        result = analyzer.estimate(track)
        assert result.mix_in_point > 0, "Estimated tracks should skip intro"

    def test_mix_in_varies_by_energy(self, analyzer):
        """Low-energy tracks should skip more intro than high-energy."""
        romantic = TrackInfo(video_id="r1", title="Romantic Ballad", duration=240.0)
        party = TrackInfo(video_id="p1", title="Party Anthem", duration=240.0)
        r = analyzer.estimate(romantic)
        p = analyzer.estimate(party)
        assert r.mix_in_point > p.mix_in_point, "Romantic should skip more intro than party"

    def test_mix_out_point_earlier_than_default(self, analyzer):
        """Mix out should happen before the last 16 seconds."""
        track = TrackInfo(video_id="mo1", title="Dance Hit", duration=300.0)
        result = analyzer.estimate(track)
        default_out = 300.0 - 16.0
        assert result.mix_out_point < default_out, "Should fade out earlier than default"

    def test_mix_points_ensure_minimum_play_time(self, analyzer):
        """Should guarantee at least 60s of play between mix_in and mix_out."""
        track = TrackInfo(video_id="short1", title="Short Song", duration=120.0)
        result = analyzer.estimate(track)
        play_time = result.mix_out_point - result.mix_in_point
        assert play_time >= 60.0, f"Play time should be >= 60s, got {play_time}"

    def test_mix_in_clamped_for_short_songs(self, analyzer):
        """For short songs, mix_in should not exceed 25 seconds."""
        track = TrackInfo(video_id="s1", title="Quick Song", duration=90.0)
        result = analyzer.estimate(track)
        assert result.mix_in_point <= 25.0, f"mix_in should be <= 25s, got {result.mix_in_point}"

    def test_mix_in_at_least_8_seconds(self, analyzer):
        """mix_in should be at least 8 seconds to skip label logos."""
        track = TrackInfo(video_id="lbl1", title="Normal Song", duration=300.0)
        result = analyzer.estimate(track)
        assert result.mix_in_point >= 8.0, f"mix_in should be >= 8s, got {result.mix_in_point}"
