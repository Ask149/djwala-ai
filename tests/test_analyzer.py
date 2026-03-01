"""Tests for audio analyzer."""

import numpy as np
import pytest
from djwala.analyzer import AudioAnalyzer


@pytest.fixture
def analyzer():
    return AudioAnalyzer()


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
