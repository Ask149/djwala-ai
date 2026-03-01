"""Tests for analysis cache."""

import pytest
from djwala.cache import AnalysisCache
from djwala.models import TrackAnalysis


@pytest.fixture
def cache(tmp_path):
    db_path = tmp_path / "test.db"
    c = AnalysisCache(str(db_path))
    yield c
    c.close()


@pytest.fixture
def analysis():
    return TrackAnalysis(
        video_id="abc123",
        title="Test Track",
        duration=240.0,
        bpm=128.0,
        key="Am",
        camelot="8A",
        energy_curve=[0.5] * 240,
        mix_in_point=2.0,
        mix_out_point=220.0,
    )


def test_get_nonexistent_returns_none(cache):
    assert cache.get("nonexistent") is None


def test_store_and_retrieve(cache, analysis):
    cache.store(analysis)
    result = cache.get("abc123")
    assert result is not None
    assert result.video_id == "abc123"
    assert result.bpm == 128.0
    assert result.key == "Am"
    assert result.camelot == "8A"
    assert result.mix_in_point == 2.0
    assert result.mix_out_point == 220.0


def test_store_overwrites(cache, analysis):
    cache.store(analysis)
    analysis.bpm = 130.0
    cache.store(analysis)
    result = cache.get("abc123")
    assert result.bpm == 130.0


def test_has(cache, analysis):
    assert not cache.has("abc123")
    cache.store(analysis)
    assert cache.has("abc123")
