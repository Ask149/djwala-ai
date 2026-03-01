# DjwalaAI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an AI-powered auto-DJ web app that searches YouTube, analyzes tracks, and mixes them on the fly via two YouTube IFrame players with intelligent crossfading.

**Architecture:** Python FastAPI backend handles YouTube search (yt-dlp), audio analysis (librosa), and DJ logic (playlist ordering, mix-point selection). Frontend uses two YouTube IFrame players with JS-driven crossfading. WebSocket connects backend brain to frontend mix engine for real-time mix commands.

**Tech Stack:** Python 3.11+, FastAPI, yt-dlp, librosa, SQLite, Pydantic, HTML/CSS/JS, YouTube IFrame API

**Design doc:** `docs/plans/2026-02-27-djwala-ai-design.md`

---

## Task 1: Project Scaffolding & Data Models

**Files:**
- Create: `pyproject.toml`
- Create: `src/djwala/__init__.py`
- Create: `src/djwala/models.py`
- Create: `src/djwala/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `static/index.html`
- Create: `.gitignore`

**Step 1: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
*.db
*.sqlite
.env
dist/
*.egg-info/
tmp_audio/
```

**Step 2: Create `pyproject.toml`**

```toml
[project]
name = "djwala"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "yt-dlp>=2024.0",
    "librosa>=0.10",
    "pydantic>=2.0",
    "websockets>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]

[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Create `src/djwala/__init__.py`**

```python
"""DjwalaAI — AI-powered auto-DJ mixing from YouTube."""
```

**Step 4: Create `src/djwala/models.py`**

```python
"""Data models for DjwalaAI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InputMode(str, Enum):
    SEED = "seed"
    VIBE = "vibe"
    ARTISTS = "artists"


@dataclass
class TrackInfo:
    """Basic track info from YouTube search (before analysis)."""
    video_id: str
    title: str
    duration: float  # seconds
    channel: str = ""
    genre_hint: str = ""


@dataclass
class TrackAnalysis:
    """Full DJ analysis of a track."""
    video_id: str
    title: str
    duration: float
    bpm: float
    key: str                          # e.g., "Am"
    camelot: str                      # e.g., "8A"
    energy_curve: list[float] = field(default_factory=list)  # per-second energy
    structure: list[dict] = field(default_factory=list)      # [{"label": "intro", "start": 0, "end": 15.2}]
    mix_in_point: float = 0.0        # seconds — where to start playing this track
    mix_out_point: float = 0.0       # seconds — where to start fading out
    drop_timestamp: float = 0.0      # biggest energy spike
    has_vocals: bool = False
    genre_hint: str = ""


@dataclass
class MixCommand:
    """Command sent to frontend to execute a crossfade."""
    action: str                       # "fade_to_next"
    current_fade_start: float         # seconds into current track to begin fade
    next_video_id: str
    next_seek_to: float               # seconds — where to seek incoming track
    fade_duration: float              # seconds — length of crossfade
    next_title: str = ""


@dataclass
class SessionRequest:
    """User request to start a DJ session."""
    mode: InputMode
    query: str                        # YouTube URL, vibe text, or comma-separated artists
```

**Step 5: Create `src/djwala/main.py`**

```python
"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="DjwalaAI", version="0.1.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 6: Create `tests/__init__.py` and `tests/conftest.py`**

`tests/__init__.py`: empty file

```python
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
        structure=[
            {"label": "intro", "start": 0, "end": 18.0},
            {"label": "verse", "start": 18.0, "end": 55.0},
            {"label": "chorus", "start": 55.0, "end": 90.0},
            {"label": "outro", "start": 180.0, "end": 213.0},
        ],
        mix_in_point=2.0,
        mix_out_point=195.0,
        drop_timestamp=55.0,
        has_vocals=True,
    )
```

**Step 7: Create placeholder `static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DjwalaAI</title>
</head>
<body>
    <h1>DjwalaAI</h1>
    <p>Coming soon.</p>
</body>
</html>
```

**Step 8: Install and verify**

Run:
```bash
cd /Users/ashishkshirsagar/Projects/djwalaAI
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
python -c "from djwala.models import TrackAnalysis; print('Models OK')"
```

Expected: install succeeds, pytest collects 0 tests (no test files yet), import works.

**Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with models and FastAPI skeleton"
```

---

## Task 2: Analysis Cache (SQLite)

**Files:**
- Create: `src/djwala/cache.py`
- Create: `tests/test_cache.py`

**Step 1: Write the failing tests**

```python
# tests/test_cache.py
"""Tests for analysis cache."""

import os
import pytest
from djwala.cache import AnalysisCache
from djwala.models import TrackAnalysis


@pytest.fixture
def cache(tmp_path):
    db_path = tmp_path / "test.db"
    return AnalysisCache(str(db_path))


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
        structure=[{"label": "intro", "start": 0, "end": 16}],
        mix_in_point=2.0,
        mix_out_point=220.0,
        drop_timestamp=64.0,
        has_vocals=False,
        genre_hint="house",
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'djwala.cache'`

**Step 3: Implement `src/djwala/cache.py`**

```python
"""SQLite cache for track analysis results."""

from __future__ import annotations

import json
import sqlite3
from djwala.models import TrackAnalysis


class AnalysisCache:
    """Simple SQLite-backed cache for TrackAnalysis objects."""

    def __init__(self, db_path: str = "djwala_cache.db"):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_table()

    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS track_analysis (
                video_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def store(self, analysis: TrackAnalysis) -> None:
        data = json.dumps({
            "video_id": analysis.video_id,
            "title": analysis.title,
            "duration": analysis.duration,
            "bpm": analysis.bpm,
            "key": analysis.key,
            "camelot": analysis.camelot,
            "energy_curve": analysis.energy_curve,
            "structure": analysis.structure,
            "mix_in_point": analysis.mix_in_point,
            "mix_out_point": analysis.mix_out_point,
            "drop_timestamp": analysis.drop_timestamp,
            "has_vocals": analysis.has_vocals,
            "genre_hint": analysis.genre_hint,
        })
        self._conn.execute(
            "INSERT OR REPLACE INTO track_analysis (video_id, data) VALUES (?, ?)",
            (analysis.video_id, data),
        )
        self._conn.commit()

    def get(self, video_id: str) -> TrackAnalysis | None:
        row = self._conn.execute(
            "SELECT data FROM track_analysis WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        if row is None:
            return None
        d = json.loads(row["data"])
        return TrackAnalysis(**d)

    def has(self, video_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM track_analysis WHERE video_id = ? LIMIT 1",
            (video_id,),
        ).fetchone()
        return row is not None

    def close(self):
        self._conn.close()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cache.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/djwala/cache.py tests/test_cache.py
git commit -m "feat: SQLite analysis cache with store/get/has"
```

---

## Task 3: YouTube Search Service

**Files:**
- Create: `src/djwala/youtube.py`
- Create: `tests/test_youtube.py`

**Step 1: Write the failing tests**

Note: YouTube search hits the network. We test the query-building and result-parsing logic with mocks. One optional integration test (marked slow) hits YouTube for real.

```python
# tests/test_youtube.py
"""Tests for YouTube search service."""

import pytest
from unittest.mock import patch, MagicMock
from djwala.youtube import YouTubeSearch
from djwala.models import InputMode


class TestQueryBuilding:
    """Test that correct search queries are generated."""

    def test_vibe_query(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.VIBE, "deep house chill")
        assert len(queries) >= 1
        assert "deep house chill" in queries[0].lower()

    def test_artist_queries(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Rufus Du Sol, Bob Moses")
        assert len(queries) >= 2
        assert any("rufus du sol" in q.lower() for q in queries)
        assert any("bob moses" in q.lower() for q in queries)

    def test_seed_query_from_title(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(
            InputMode.SEED,
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        # Should generate queries — exact content depends on title extraction
        assert len(queries) >= 1


class TestResultParsing:
    """Test that yt-dlp results are parsed into TrackInfo."""

    def test_parse_entry(self):
        yt = YouTubeSearch()
        entry = {
            "id": "abc123",
            "title": "Artist - Track Name [Deep House]",
            "duration": 245,
            "channel": "Some Channel",
        }
        track = yt._parse_entry(entry)
        assert track.video_id == "abc123"
        assert track.title == "Artist - Track Name [Deep House]"
        assert track.duration == 245.0
        assert track.channel == "Some Channel"

    def test_parse_entry_skips_too_short(self):
        yt = YouTubeSearch()
        entry = {"id": "x", "title": "Short", "duration": 30, "channel": ""}
        track = yt._parse_entry(entry)
        assert track is None  # < 60 seconds = probably not a full song

    def test_parse_entry_skips_too_long(self):
        yt = YouTubeSearch()
        entry = {"id": "x", "title": "Mix", "duration": 7200, "channel": ""}
        track = yt._parse_entry(entry)
        assert track is None  # > 600 seconds = probably a mix/compilation

    def test_genre_hint_from_title(self):
        yt = YouTubeSearch()
        entry = {
            "id": "abc",
            "title": "Track Name [Progressive House]",
            "duration": 300,
            "channel": "Ch",
        }
        track = yt._parse_entry(entry)
        assert "progressive house" in track.genre_hint.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_youtube.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'djwala.youtube'`

**Step 3: Implement `src/djwala/youtube.py`**

```python
"""YouTube search service using yt-dlp."""

from __future__ import annotations

import re
from djwala.models import TrackInfo, InputMode

# Genre keywords commonly found in music video titles
GENRE_KEYWORDS = [
    "house", "deep house", "progressive house", "tech house",
    "techno", "melodic techno", "trance", "psytrance",
    "drum and bass", "dnb", "dubstep", "ambient",
    "lo-fi", "lofi", "hip hop", "r&b", "pop", "indie",
    "edm", "electronic", "dance", "disco", "funk",
]

# Min/max duration for a single track (seconds)
MIN_DURATION = 60
MAX_DURATION = 600


class YouTubeSearch:
    """Search YouTube for tracks using yt-dlp."""

    def build_queries(self, mode: InputMode, query: str) -> list[str]:
        """Build search queries based on input mode."""
        if mode == InputMode.VIBE:
            return [f"{query} full track", f"{query} official audio"]

        if mode == InputMode.ARTISTS:
            artists = [a.strip() for a in query.split(",") if a.strip()]
            queries = []
            for artist in artists:
                queries.append(f"{artist} official audio")
                queries.append(f"{artist} full track")
            return queries

        if mode == InputMode.SEED:
            # Extract video info first, then build queries from title
            return self._queries_from_seed(query)

        return [query]

    def _queries_from_seed(self, url: str) -> list[str]:
        """Extract title from seed URL, build related search queries."""
        import yt_dlp

        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception:
                # Fallback: just use the URL as a query
                return [url]

        title = info.get("title", "")
        artist = info.get("artist") or info.get("channel", "")

        # Strip common suffixes like (Official Video), [HD], etc.
        clean_title = re.sub(r"\s*[\[\(].*?[\]\)]", "", title).strip()

        queries = []
        if artist:
            queries.append(f"{artist} similar tracks")
            queries.append(f"tracks like {artist}")
        if clean_title:
            queries.append(f"songs like {clean_title}")
        # Fallback
        if not queries:
            queries.append(title)

        return queries

    def search(self, mode: InputMode, query: str, max_results: int = 20) -> list[TrackInfo]:
        """Search YouTube and return candidate tracks."""
        import yt_dlp

        queries = self.build_queries(mode, query)
        seen_ids: set[str] = set()
        tracks: list[TrackInfo] = []

        per_query = max(5, max_results // len(queries))

        for q in queries:
            if len(tracks) >= max_results:
                break

            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": True,
                "default_search": f"ytsearch{per_query}",
            }

            with yt_dlp.YoutubeDL(opts) as ydl:
                try:
                    result = ydl.extract_info(q, download=False)
                except Exception:
                    continue

                entries = result.get("entries", []) if result else []
                for entry in entries:
                    if not entry or entry.get("id") in seen_ids:
                        continue
                    track = self._parse_entry(entry)
                    if track and track.video_id not in seen_ids:
                        seen_ids.add(track.video_id)
                        tracks.append(track)

        return tracks[:max_results]

    def _parse_entry(self, entry: dict) -> TrackInfo | None:
        """Parse a yt-dlp entry into TrackInfo. Returns None if invalid."""
        video_id = entry.get("id", "")
        title = entry.get("title", "")
        duration = float(entry.get("duration") or 0)
        channel = entry.get("channel", "") or entry.get("uploader", "")

        if duration < MIN_DURATION or duration > MAX_DURATION:
            return None

        genre_hint = self._extract_genre(title)

        return TrackInfo(
            video_id=video_id,
            title=title,
            duration=duration,
            channel=channel,
            genre_hint=genre_hint,
        )

    def _extract_genre(self, title: str) -> str:
        """Extract genre hint from title using bracket content and keywords."""
        # Check bracketed content first: [Deep House], (Progressive House)
        brackets = re.findall(r"[\[\(](.*?)[\]\)]", title)
        for bracket in brackets:
            for genre in GENRE_KEYWORDS:
                if genre.lower() in bracket.lower():
                    return bracket.strip()

        # Check title text
        title_lower = title.lower()
        for genre in sorted(GENRE_KEYWORDS, key=len, reverse=True):
            if genre in title_lower:
                return genre

        return ""
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_youtube.py -v`
Expected: All tests pass (seed query test may need yt-dlp installed)

**Step 5: Commit**

```bash
git add src/djwala/youtube.py tests/test_youtube.py
git commit -m "feat: YouTube search service with three input modes"
```

---

## Task 4: Audio Analyzer

**Files:**
- Create: `src/djwala/analyzer.py`
- Create: `tests/test_analyzer.py`

**Step 1: Write the failing tests**

Note: Full audio analysis needs real audio files. We test individual analysis functions with synthetic audio, and the download+analyze pipeline with mocks.

```python
# tests/test_analyzer.py
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


class TestDropDetection:
    def test_finds_energy_spike(self, analyzer):
        # Low energy for 5 seconds, then high energy for 5 seconds
        energy_curve = [0.1] * 5 + [0.9] * 5
        drop = analyzer._find_drop(energy_curve)
        assert 4 <= drop <= 6  # drop should be around second 5


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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analyzer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'djwala.analyzer'`

**Step 3: Implement `src/djwala/analyzer.py`**

```python
"""Audio analyzer — extracts DJ parameters from audio."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import librosa
import numpy as np

from djwala.models import TrackAnalysis, TrackInfo

# Key name lookup: chroma index → key name
KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Camelot wheel mapping: (key_name, mode) → camelot code
# mode: "major" or "minor"
CAMELOT_WHEEL = {
    ("C", "major"): "8B", ("A", "minor"): "8A",
    ("G", "major"): "9B", ("E", "minor"): "9A",
    ("D", "major"): "10B", ("B", "minor"): "10A",
    ("A", "major"): "11B", ("F#", "minor"): "11A",
    ("E", "major"): "12B", ("C#", "minor"): "12A",
    ("B", "major"): "1B", ("G#", "minor"): "1A",
    ("F#", "major"): "2B", ("D#", "minor"): "2A",
    ("Gb", "major"): "2B", ("Eb", "minor"): "2A",
    ("Db", "major"): "3B", ("Bb", "minor"): "3A",
    ("Ab", "major"): "4B", ("F", "minor"): "4A",
    ("Eb", "major"): "5B", ("C", "minor"): "5A",
    ("Bb", "major"): "6B", ("G", "minor"): "6A",
    ("F", "major"): "7B", ("D", "minor"): "7A",
}


class AudioAnalyzer:
    """Extracts DJ-relevant parameters from audio."""

    def __init__(self, tmp_dir: str | None = None):
        self._tmp_dir = tmp_dir or tempfile.mkdtemp(prefix="djwala_")

    def analyze(self, track: TrackInfo) -> TrackAnalysis:
        """Download audio from YouTube and analyze it."""
        audio_path = self._download_audio(track.video_id)
        try:
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
            return self._analyze_audio(y, sr, track)
        finally:
            # Clean up downloaded audio
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def _download_audio(self, video_id: str) -> str:
        """Download audio from YouTube video, return path to audio file."""
        import yt_dlp

        output_path = os.path.join(self._tmp_dir, f"{video_id}.%(ext)s")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        wav_path = os.path.join(self._tmp_dir, f"{video_id}.wav")
        if not os.path.exists(wav_path):
            # Try common extensions
            for ext in ["m4a", "webm", "mp3", "opus"]:
                p = os.path.join(self._tmp_dir, f"{video_id}.{ext}")
                if os.path.exists(p):
                    return p
            raise FileNotFoundError(f"Downloaded audio not found for {video_id}")
        return wav_path

    def _analyze_audio(self, y: np.ndarray, sr: int, track: TrackInfo) -> TrackAnalysis:
        """Run all analysis on loaded audio."""
        bpm = self._detect_bpm(y, sr)
        key, camelot = self._detect_key(y, sr)
        energy_curve = self._compute_energy_curve(y, sr)
        structure = self._detect_structure(y, sr)
        drop_timestamp = self._find_drop(energy_curve)
        mix_in = self._find_mix_in(energy_curve)
        mix_out = self._find_mix_out(energy_curve, track.duration)
        has_vocals = self._detect_vocals(y, sr)

        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=track.duration,
            bpm=bpm,
            key=key,
            camelot=camelot,
            energy_curve=energy_curve,
            structure=structure,
            mix_in_point=mix_in,
            mix_out_point=mix_out,
            drop_timestamp=float(drop_timestamp),
            has_vocals=has_vocals,
            genre_hint=track.genre_hint,
        )

    def _detect_bpm(self, y: np.ndarray, sr: int) -> float:
        """Detect BPM using librosa beat tracking."""
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0])
        return round(float(tempo), 1)

    def _detect_key(self, y: np.ndarray, sr: int) -> tuple[str, str]:
        """Detect musical key using chroma features."""
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        # Find the strongest pitch class
        key_idx = int(np.argmax(chroma_avg))
        key_name = KEY_NAMES[key_idx]

        # Simple major/minor detection using the relative minor relationship
        # Compare energy of major third vs minor third
        major_third = chroma_avg[(key_idx + 4) % 12]
        minor_third = chroma_avg[(key_idx + 3) % 12]

        if minor_third > major_third:
            mode = "minor"
            key_str = f"{key_name}m"
        else:
            mode = "major"
            key_str = key_name

        camelot = CAMELOT_WHEEL.get((key_name, mode), "1A")

        return key_str, camelot

    def _compute_energy_curve(self, y: np.ndarray, sr: int) -> list[float]:
        """Compute per-second RMS energy."""
        hop_length = sr  # one value per second
        rms = librosa.feature.rms(y=y, frame_length=sr, hop_length=hop_length)[0]
        # Normalize to 0-1
        max_rms = rms.max() if rms.max() > 0 else 1.0
        normalized = (rms / max_rms).tolist()
        return [round(v, 3) for v in normalized]

    def _detect_structure(self, y: np.ndarray, sr: int) -> list[dict]:
        """Detect song structure (intro, verse, chorus, outro) using novelty."""
        # Use spectral features for segmentation
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        bound_frames = librosa.segment.agglomerative(mfcc, k=6)

        # Convert frames to timestamps
        times = librosa.frames_to_time(bound_frames, sr=sr)
        duration = len(y) / sr

        # Build segments with simple labeling
        labels = ["intro", "buildup", "verse", "chorus", "breakdown", "outro"]
        segments = []
        all_times = [0.0] + sorted(times.tolist()) + [duration]

        for i in range(len(all_times) - 1):
            label = labels[i] if i < len(labels) else f"section_{i}"
            segments.append({
                "label": label,
                "start": round(all_times[i], 1),
                "end": round(all_times[i + 1], 1),
            })

        return segments

    def _find_drop(self, energy_curve: list[float]) -> float:
        """Find the timestamp of the biggest energy increase (the drop)."""
        if len(energy_curve) < 2:
            return 0.0

        max_diff = 0.0
        drop_idx = 0
        for i in range(1, len(energy_curve)):
            diff = energy_curve[i] - energy_curve[i - 1]
            if diff > max_diff:
                max_diff = diff
                drop_idx = i

        return float(drop_idx)

    def _find_mix_in(self, energy_curve: list[float]) -> float:
        """Find optimal point to start playing this track (skip silence/quiet intro)."""
        threshold = 0.1
        for i, energy in enumerate(energy_curve):
            if energy > threshold:
                return max(0.0, float(i) - 1.0)  # start 1 second before
        return 0.0

    def _find_mix_out(self, energy_curve: list[float], duration: float) -> float:
        """Find optimal point to start fading out (where energy drops near end)."""
        if not energy_curve:
            return max(0.0, duration - 16.0)

        # Look at last 30% of the track
        start_idx = int(len(energy_curve) * 0.7)
        avg_energy = sum(energy_curve[start_idx:]) / max(1, len(energy_curve) - start_idx)

        # Find where energy drops below 70% of the ending average
        threshold = avg_energy * 0.7
        for i in range(start_idx, len(energy_curve)):
            if energy_curve[i] < threshold:
                return float(i)

        # Fallback: 16 seconds before end
        return max(0.0, duration - 16.0)

    def _detect_vocals(self, y: np.ndarray, sr: int) -> bool:
        """Simple vocal detection using harmonic/percussive separation."""
        y_harmonic, y_percussive = librosa.effects.hpss(y)
        harmonic_energy = np.mean(np.abs(y_harmonic))
        percussive_energy = np.mean(np.abs(y_percussive))

        # If harmonic content is significantly stronger, likely has vocals
        if percussive_energy > 0:
            ratio = harmonic_energy / percussive_energy
            return ratio > 1.5
        return False
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analyzer.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/djwala/analyzer.py tests/test_analyzer.py
git commit -m "feat: audio analyzer with BPM, key, energy, structure detection"
```

---

## Task 5: DJ Brain -- Camelot Wheel & Compatibility

**Files:**
- Create: `src/djwala/brain.py`
- Create: `tests/test_brain.py`

**Step 1: Write the failing tests**

```python
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
        structure=[],
        mix_in_point=2.0,
        mix_out_point=duration - 16.0,
        drop_timestamp=60.0,
        has_vocals=False,
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_brain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'djwala.brain'`

**Step 3: Implement `src/djwala/brain.py`**

```python
"""DJ Brain — playlist ordering, mix decisions, crossfade logic."""

from __future__ import annotations

from djwala.models import TrackAnalysis, MixCommand


class DJBrain:
    """Core DJ intelligence: ordering, compatibility, mix decisions."""

    BPM_TOLERANCE = 0.06  # 6% BPM difference allowed

    def keys_compatible(self, camelot_a: str, camelot_b: str) -> bool:
        """Check if two Camelot keys are harmonically compatible.

        Compatible = same key, adjacent numbers (same letter), or
        same number (different letter, i.e., relative major/minor).
        """
        num_a, letter_a = int(camelot_a[:-1]), camelot_a[-1]
        num_b, letter_b = int(camelot_b[:-1]), camelot_b[-1]

        # Same key
        if camelot_a == camelot_b:
            return True

        # Same number, different letter (relative major/minor)
        if num_a == num_b:
            return True

        # Adjacent numbers, same letter (wrapping 12 → 1)
        if letter_a == letter_b:
            diff = abs(num_a - num_b)
            if diff == 1 or diff == 11:  # 11 = wrapping (12→1 or 1→12)
                return True

        return False

    def bpm_compatible(self, bpm_a: float, bpm_b: float) -> bool:
        """Check if two BPMs are close enough to mix."""
        if bpm_a == 0 or bpm_b == 0:
            return True  # unknown BPM, allow it
        ratio = abs(bpm_a - bpm_b) / min(bpm_a, bpm_b)
        return ratio <= self.BPM_TOLERANCE

    def order_playlist(self, tracks: list[TrackAnalysis]) -> list[TrackAnalysis]:
        """Order tracks for smooth DJ flow.

        Strategy:
        1. Sort by BPM (gradual progression)
        2. Within BPM clusters, prefer Camelot-compatible neighbors
        3. Shape energy arc (build up, peak, wind down)
        """
        if len(tracks) <= 1:
            return tracks

        # Start with BPM sort
        sorted_tracks = sorted(tracks, key=lambda t: t.bpm)

        # Greedy reorder: pick next track that's BPM-close AND key-compatible
        ordered = [sorted_tracks.pop(0)]
        while sorted_tracks:
            current = ordered[-1]
            best_idx = 0
            best_score = float("inf")

            for i, candidate in enumerate(sorted_tracks):
                score = self._transition_score(current, candidate)
                if score < best_score:
                    best_score = score
                    best_idx = i

            ordered.append(sorted_tracks.pop(best_idx))

        return ordered

    def _transition_score(self, current: TrackAnalysis, candidate: TrackAnalysis) -> float:
        """Score how well candidate follows current. Lower = better."""
        # BPM difference (normalized)
        bpm_diff = abs(current.bpm - candidate.bpm) / max(current.bpm, 1)

        # Key compatibility bonus
        key_penalty = 0.0 if self.keys_compatible(current.camelot, candidate.camelot) else 0.5

        # Energy continuity (prefer gradual change)
        current_energy = sum(current.energy_curve) / max(len(current.energy_curve), 1)
        candidate_energy = sum(candidate.energy_curve) / max(len(candidate.energy_curve), 1)
        energy_diff = abs(current_energy - candidate_energy)

        return bpm_diff + key_penalty + energy_diff * 0.3

    def crossfade_duration(self, outgoing: TrackAnalysis, incoming: TrackAnalysis) -> float:
        """Calculate crossfade duration based on energy and BPM."""
        avg_energy_out = sum(outgoing.energy_curve) / max(len(outgoing.energy_curve), 1)
        avg_energy_in = sum(incoming.energy_curve) / max(len(incoming.energy_curve), 1)
        avg_energy = (avg_energy_out + avg_energy_in) / 2

        avg_bpm = (outgoing.bpm + incoming.bpm) / 2

        # High energy + high BPM = shorter crossfade
        # Low energy + low BPM = longer crossfade
        if avg_energy > 0.6 or avg_bpm > 135:
            return 8.0
        elif avg_energy < 0.35 or avg_bpm < 115:
            return 18.0
        else:
            return 14.0

    def plan_mix(self, outgoing: TrackAnalysis, incoming: TrackAnalysis) -> MixCommand:
        """Plan the mix transition between two tracks."""
        fade_duration = self.crossfade_duration(outgoing, incoming)

        return MixCommand(
            action="fade_to_next",
            current_fade_start=outgoing.mix_out_point,
            next_video_id=incoming.video_id,
            next_seek_to=incoming.mix_in_point,
            fade_duration=fade_duration,
            next_title=incoming.title,
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_brain.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/djwala/brain.py tests/test_brain.py
git commit -m "feat: DJ brain with Camelot matching, BPM compat, playlist ordering"
```

---

## Task 6: Session Manager & Backend API

**Files:**
- Create: `src/djwala/session.py`
- Modify: `src/djwala/main.py`
- Create: `tests/test_api.py`

**Step 1: Write the failing tests**

```python
# tests/test_api.py
"""Tests for the API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from djwala.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_session(client):
    resp = await client.post("/session", json={
        "mode": "vibe",
        "query": "deep house chill",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "searching"


async def test_get_session_queue(client):
    # Create a session first
    resp = await client.post("/session", json={
        "mode": "vibe",
        "query": "test",
    })
    session_id = resp.json()["session_id"]

    resp = await client.get(f"/session/{session_id}/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert "tracks" in data
    assert "status" in data


async def test_get_nonexistent_session(client):
    resp = await client.get("/session/nonexistent/queue")
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`
Expected: FAIL — missing endpoints

**Step 3: Implement `src/djwala/session.py`**

```python
"""Session manager — orchestrates search, analysis, and mix planning."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum

from djwala.analyzer import AudioAnalyzer
from djwala.brain import DJBrain
from djwala.cache import AnalysisCache
from djwala.models import InputMode, MixCommand, TrackAnalysis, TrackInfo
from djwala.youtube import YouTubeSearch


class SessionStatus(str, Enum):
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    READY = "ready"
    PLAYING = "playing"
    ERROR = "error"


@dataclass
class Session:
    session_id: str
    mode: InputMode
    query: str
    status: SessionStatus = SessionStatus.SEARCHING
    candidates: list[TrackInfo] = field(default_factory=list)
    queue: list[TrackAnalysis] = field(default_factory=list)
    current_index: int = 0
    error: str = ""


class SessionManager:
    """Manages DJ sessions — search, analyze, queue."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._youtube = YouTubeSearch()
        self._analyzer = AudioAnalyzer()
        self._brain = DJBrain()
        self._cache = AnalysisCache()

    def create_session(self, mode: InputMode, query: str) -> Session:
        session_id = str(uuid.uuid4())[:8]
        session = Session(
            session_id=session_id,
            mode=mode,
            query=query,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def build_queue(self, session_id: str) -> None:
        """Search YouTube, analyze tracks, build ordered queue."""
        session = self._sessions.get(session_id)
        if not session:
            return

        try:
            # Step 1: Search YouTube
            session.status = SessionStatus.SEARCHING
            candidates = await asyncio.to_thread(
                self._youtube.search, session.mode, session.query
            )
            session.candidates = candidates

            if not candidates:
                session.status = SessionStatus.ERROR
                session.error = "No tracks found"
                return

            # Step 2: Analyze tracks (first batch)
            session.status = SessionStatus.ANALYZING
            analyzed = []
            batch_size = min(5, len(candidates))

            for track in candidates[:batch_size]:
                if self._cache.has(track.video_id):
                    analysis = self._cache.get(track.video_id)
                else:
                    try:
                        analysis = await asyncio.to_thread(
                            self._analyzer.analyze, track
                        )
                        self._cache.store(analysis)
                    except Exception:
                        continue  # skip tracks that fail analysis
                analyzed.append(analysis)

            if not analyzed:
                session.status = SessionStatus.ERROR
                session.error = "Could not analyze any tracks"
                return

            # Step 3: Order playlist
            session.queue = self._brain.order_playlist(analyzed)
            session.status = SessionStatus.READY

        except Exception as e:
            session.status = SessionStatus.ERROR
            session.error = str(e)

    def get_mix_command(self, session_id: str) -> MixCommand | None:
        """Get the next mix command for the current position."""
        session = self._sessions.get(session_id)
        if not session or not session.queue:
            return None

        idx = session.current_index
        if idx + 1 >= len(session.queue):
            return None  # no next track

        outgoing = session.queue[idx]
        incoming = session.queue[idx + 1]
        return self._brain.plan_mix(outgoing, incoming)

    def advance(self, session_id: str) -> None:
        """Move to the next track."""
        session = self._sessions.get(session_id)
        if session and session.current_index + 1 < len(session.queue):
            session.current_index += 1

    async def analyze_more(self, session_id: str) -> None:
        """Continue analyzing remaining candidates in the background."""
        session = self._sessions.get(session_id)
        if not session:
            return

        analyzed_ids = {t.video_id for t in session.queue}
        for track in session.candidates:
            if track.video_id in analyzed_ids:
                continue
            if self._cache.has(track.video_id):
                analysis = self._cache.get(track.video_id)
            else:
                try:
                    analysis = await asyncio.to_thread(
                        self._analyzer.analyze, track
                    )
                    self._cache.store(analysis)
                except Exception:
                    continue
            session.queue = self._brain.order_playlist(
                session.queue + [analysis]
            )
```

**Step 4: Update `src/djwala/main.py` with full API**

```python
"""FastAPI application entry point."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from djwala.session import SessionManager

app = FastAPI(title="DjwalaAI", version="0.1.0")
manager = SessionManager()


class SessionCreate(BaseModel):
    mode: str
    query: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/session")
async def create_session(req: SessionCreate):
    from djwala.models import InputMode
    try:
        mode = InputMode(req.mode)
    except ValueError:
        raise HTTPException(400, f"Invalid mode: {req.mode}")

    session = manager.create_session(mode, req.query)
    # Start building queue in background
    asyncio.create_task(manager.build_queue(session.session_id))

    return {
        "session_id": session.session_id,
        "status": session.status.value,
    }


@app.get("/session/{session_id}/queue")
async def get_queue(session_id: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    tracks = []
    for t in session.queue:
        tracks.append({
            "video_id": t.video_id,
            "title": t.title,
            "bpm": t.bpm,
            "key": t.key,
            "camelot": t.camelot,
            "duration": t.duration,
            "mix_in_point": t.mix_in_point,
            "mix_out_point": t.mix_out_point,
            "energy": round(sum(t.energy_curve) / max(len(t.energy_curve), 1), 2),
        })

    return {
        "session_id": session_id,
        "status": session.status.value,
        "current_index": session.current_index,
        "tracks": tracks,
        "error": session.error,
    }


@app.get("/track/{video_id}")
async def get_track(video_id: str):
    from djwala.cache import AnalysisCache
    cache = AnalysisCache()
    analysis = cache.get(video_id)
    if not analysis:
        raise HTTPException(404, "Track not analyzed")
    return {
        "video_id": analysis.video_id,
        "title": analysis.title,
        "bpm": analysis.bpm,
        "key": analysis.key,
        "camelot": analysis.camelot,
        "duration": analysis.duration,
        "mix_in_point": analysis.mix_in_point,
        "mix_out_point": analysis.mix_out_point,
        "drop_timestamp": analysis.drop_timestamp,
        "has_vocals": analysis.has_vocals,
        "structure": analysis.structure,
    }


@app.websocket("/session/{session_id}/live")
async def websocket_live(websocket: WebSocket, session_id: str):
    session = manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "get_mix_command":
                mix_cmd = manager.get_mix_command(session_id)
                if mix_cmd:
                    await websocket.send_json({
                        "action": mix_cmd.action,
                        "current_fade_start": mix_cmd.current_fade_start,
                        "next_video_id": mix_cmd.next_video_id,
                        "next_seek_to": mix_cmd.next_seek_to,
                        "fade_duration": mix_cmd.fade_duration,
                        "next_title": mix_cmd.next_title,
                    })
                else:
                    await websocket.send_json({"action": "no_more_tracks"})

            elif action == "track_ended":
                manager.advance(session_id)
                # Trigger background analysis of more tracks
                asyncio.create_task(manager.analyze_more(session_id))
                await websocket.send_json({"action": "advanced"})

            elif action == "request_queue":
                session = manager.get_session(session_id)
                await websocket.send_json({
                    "action": "queue_update",
                    "current_index": session.current_index,
                    "queue_length": len(session.queue),
                })

    except WebSocketDisconnect:
        pass


app.mount("/static", StaticFiles(directory="static"), name="static")
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: All tests pass (the background tasks won't complete in test, but session creation and queue endpoint should work)

**Step 6: Commit**

```bash
git add src/djwala/session.py src/djwala/main.py tests/test_api.py
git commit -m "feat: session manager and full REST/WebSocket API"
```

---

## Task 7: Frontend -- YouTube IFrame Players & Mix Engine

**Files:**
- Modify: `static/index.html`
- Create: `static/js/mix-engine.js`
- Create: `static/js/app.js`
- Create: `static/css/style.css`

**Step 1: Create `static/css/style.css`**

```css
/* static/css/style.css */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.container {
    max-width: 700px;
    width: 100%;
    padding: 2rem 1rem;
}

h1 {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.subtitle { color: #666; margin-bottom: 2rem; }

/* Input Section */
.input-section {
    background: #14141f;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 2rem;
}

.mode-tabs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.mode-tab {
    padding: 0.5rem 1rem;
    background: #1e1e2e;
    border: 1px solid #333;
    border-radius: 8px;
    color: #999;
    cursor: pointer;
    font-size: 0.9rem;
}

.mode-tab.active {
    background: #2a2a4a;
    border-color: #667eea;
    color: #e0e0e0;
}

.search-row {
    display: flex;
    gap: 0.5rem;
}

.search-input {
    flex: 1;
    padding: 0.75rem 1rem;
    background: #1e1e2e;
    border: 1px solid #333;
    border-radius: 8px;
    color: #e0e0e0;
    font-size: 1rem;
}

.search-input:focus { outline: none; border-color: #667eea; }

.go-btn {
    padding: 0.75rem 1.5rem;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 1rem;
    cursor: pointer;
}

.go-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Now Playing */
.now-playing {
    background: #14141f;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    display: none;
}

.now-playing.active { display: block; }

.now-playing h3 { color: #667eea; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 0.5rem; }
.now-playing .track-title { font-size: 1.2rem; margin-bottom: 0.25rem; }
.now-playing .track-meta { color: #666; font-size: 0.85rem; }
.now-playing .next-up { color: #999; font-size: 0.85rem; margin-top: 0.75rem; }

/* Status */
.status-bar {
    text-align: center;
    padding: 1rem;
    color: #666;
    font-size: 0.9rem;
    display: none;
}

.status-bar.active { display: block; }

/* Queue */
.queue {
    background: #14141f;
    border-radius: 12px;
    padding: 1rem;
    display: none;
}

.queue.active { display: block; }

.queue h3 { color: #667eea; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 0.75rem; padding: 0 0.5rem; }

.queue-item {
    display: flex;
    align-items: center;
    padding: 0.5rem;
    border-radius: 8px;
    gap: 0.75rem;
    font-size: 0.9rem;
}

.queue-item.current { background: #1e1e3a; }
.queue-item .idx { color: #555; width: 1.5rem; text-align: right; }
.queue-item .title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.queue-item .bpm { color: #667eea; font-size: 0.8rem; width: 4rem; text-align: right; }
.queue-item .key { color: #764ba2; font-size: 0.8rem; width: 2.5rem; text-align: right; }

/* Hidden YouTube players */
.players-container {
    position: fixed;
    top: -9999px;
    left: -9999px;
    width: 1px;
    height: 1px;
    overflow: hidden;
}
```

**Step 2: Create `static/js/mix-engine.js`**

```javascript
// static/js/mix-engine.js
// Mix Engine — manages two YouTube IFrame players and crossfading

class MixEngine {
    constructor(onTrackChange) {
        this.deckA = null;
        this.deckB = null;
        this.activeDeck = 'A';
        this.isFading = false;
        this.fadeInterval = null;
        this.onTrackChange = onTrackChange || (() => {});
        this._playersReady = { A: false, B: false };
        this._pendingPlay = null;
    }

    init() {
        // Create player divs
        const container = document.querySelector('.players-container');
        const divA = document.createElement('div');
        divA.id = 'yt-player-a';
        const divB = document.createElement('div');
        divB.id = 'yt-player-b';
        container.appendChild(divA);
        container.appendChild(divB);

        // Load YouTube IFrame API
        const tag = document.createElement('script');
        tag.src = 'https://www.youtube.com/iframe_api';
        document.head.appendChild(tag);

        window.onYouTubeIframeAPIReady = () => {
            this.deckA = new YT.Player('yt-player-a', {
                height: '1', width: '1',
                playerVars: { autoplay: 0, controls: 0 },
                events: {
                    onReady: () => { this._playersReady.A = true; this._checkPending(); },
                    onStateChange: (e) => this._onStateChange('A', e),
                },
            });
            this.deckB = new YT.Player('yt-player-b', {
                height: '1', width: '1',
                playerVars: { autoplay: 0, controls: 0 },
                events: {
                    onReady: () => { this._playersReady.B = true; this._checkPending(); },
                    onStateChange: (e) => this._onStateChange('B', e),
                },
            });
        };
    }

    _checkPending() {
        if (this._pendingPlay && this._playersReady.A && this._playersReady.B) {
            const { videoId, seekTo } = this._pendingPlay;
            this._pendingPlay = null;
            this.playOnDeck(videoId, seekTo);
        }
    }

    getActiveDeck() {
        return this.activeDeck === 'A' ? this.deckA : this.deckB;
    }

    getInactiveDeck() {
        return this.activeDeck === 'A' ? this.deckB : this.deckA;
    }

    playOnDeck(videoId, seekTo = 0) {
        if (!this._playersReady.A || !this._playersReady.B) {
            this._pendingPlay = { videoId, seekTo };
            return;
        }

        const deck = this.getActiveDeck();
        deck.setVolume(100);
        deck.loadVideoById({ videoId, startSeconds: seekTo });
    }

    getCurrentTime() {
        const deck = this.getActiveDeck();
        return deck ? deck.getCurrentTime() : 0;
    }

    crossfadeTo(nextVideoId, seekTo, fadeDuration) {
        if (this.isFading) return;
        this.isFading = true;

        const outgoing = this.getActiveDeck();
        const incoming = this.getInactiveDeck();

        // Load next track on inactive deck
        incoming.setVolume(0);
        incoming.loadVideoById({ videoId: nextVideoId, startSeconds: seekTo });

        const steps = 50; // number of volume steps
        const interval = (fadeDuration * 1000) / steps;
        let step = 0;

        this.fadeInterval = setInterval(() => {
            step++;
            const progress = step / steps;

            // Cosine curve for smooth crossfade
            const outVol = Math.round(Math.cos(progress * Math.PI / 2) * 100);
            const inVol = Math.round(Math.sin(progress * Math.PI / 2) * 100);

            outgoing.setVolume(outVol);
            incoming.setVolume(inVol);

            if (step >= steps) {
                clearInterval(this.fadeInterval);
                outgoing.stopVideo();
                this.activeDeck = this.activeDeck === 'A' ? 'B' : 'A';
                this.isFading = false;
                this.onTrackChange();
            }
        }, interval);
    }

    _onStateChange(deck, event) {
        // YT.PlayerState.ENDED = 0
        if (event.data === 0 && !this.isFading) {
            const deckLabel = deck;
            const isActive = (deckLabel === this.activeDeck);
            if (isActive) {
                this.onTrackChange();
            }
        }
    }

    destroy() {
        if (this.fadeInterval) clearInterval(this.fadeInterval);
        if (this.deckA) this.deckA.destroy();
        if (this.deckB) this.deckB.destroy();
    }
}
```

**Step 3: Create `static/js/app.js`**

```javascript
// static/js/app.js
// Main application — connects UI, WebSocket, and MixEngine

class DjwalaApp {
    constructor() {
        this.sessionId = null;
        this.ws = null;
        this.queue = [];
        this.currentIndex = 0;
        this.mixCommand = null;
        this.positionTimer = null;

        this.engine = new MixEngine(() => this.onTrackEnded());

        this.els = {
            modeTabs: document.querySelectorAll('.mode-tab'),
            searchInput: document.querySelector('.search-input'),
            goBtn: document.querySelector('.go-btn'),
            nowPlaying: document.querySelector('.now-playing'),
            trackTitle: document.querySelector('.track-title'),
            trackMeta: document.querySelector('.track-meta'),
            nextUp: document.querySelector('.next-up'),
            statusBar: document.querySelector('.status-bar'),
            statusText: document.querySelector('.status-text'),
            queueSection: document.querySelector('.queue'),
            queueList: document.querySelector('.queue-list'),
        };

        this.mode = 'vibe';
        this.bindEvents();
        this.engine.init();
    }

    bindEvents() {
        this.els.modeTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                this.els.modeTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.mode = tab.dataset.mode;
                this.updatePlaceholder();
            });
        });

        this.els.goBtn.addEventListener('click', () => this.startSession());
        this.els.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.startSession();
        });
    }

    updatePlaceholder() {
        const placeholders = {
            seed: 'Paste a YouTube URL...',
            vibe: 'Describe a vibe... (e.g., "deep house chill")',
            artists: 'Artist names, comma separated...',
        };
        this.els.searchInput.placeholder = placeholders[this.mode] || '';
    }

    async startSession() {
        const query = this.els.searchInput.value.trim();
        if (!query) return;

        this.els.goBtn.disabled = true;
        this.setStatus('Searching YouTube...');

        try {
            const resp = await fetch('/session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: this.mode, query }),
            });
            const data = await resp.json();
            this.sessionId = data.session_id;

            // Poll for queue readiness
            this.pollQueue();
        } catch (err) {
            this.setStatus('Error: ' + err.message);
            this.els.goBtn.disabled = false;
        }
    }

    async pollQueue() {
        const poll = async () => {
            try {
                const resp = await fetch(`/session/${this.sessionId}/queue`);
                const data = await resp.json();

                if (data.status === 'error') {
                    this.setStatus('Error: ' + data.error);
                    this.els.goBtn.disabled = false;
                    return;
                }

                if (data.status === 'searching') {
                    this.setStatus('Searching YouTube...');
                    setTimeout(poll, 1000);
                    return;
                }

                if (data.status === 'analyzing') {
                    this.setStatus('Analyzing tracks...');
                    setTimeout(poll, 2000);
                    return;
                }

                if (data.status === 'ready' && data.tracks.length > 0) {
                    this.queue = data.tracks;
                    this.currentIndex = 0;
                    this.connectWebSocket();
                    this.startPlaying();
                    return;
                }

                setTimeout(poll, 1000);
            } catch {
                setTimeout(poll, 2000);
            }
        };
        poll();
    }

    connectWebSocket() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${location.host}/session/${this.sessionId}/live`);

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWSMessage(data);
        };
    }

    handleWSMessage(data) {
        if (data.action === 'fade_to_next') {
            this.mixCommand = data;
        } else if (data.action === 'advanced') {
            this.currentIndex++;
            this.updateNowPlaying();
            this.updateQueue();
        } else if (data.action === 'no_more_tracks') {
            this.setStatus('No more tracks -- set complete!');
        }
    }

    startPlaying() {
        this.hideStatus();
        this.els.goBtn.disabled = false;

        const track = this.queue[0];
        this.engine.playOnDeck(track.video_id, track.mix_in_point);
        this.updateNowPlaying();
        this.updateQueue();

        // Request first mix command
        this.requestMixCommand();

        // Start position monitoring
        this.startPositionMonitor();
    }

    requestMixCommand() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'get_mix_command' }));
        }
    }

    startPositionMonitor() {
        if (this.positionTimer) clearInterval(this.positionTimer);

        this.positionTimer = setInterval(() => {
            if (!this.mixCommand || this.engine.isFading) return;

            const currentTime = this.engine.getCurrentTime();
            if (currentTime >= this.mixCommand.current_fade_start) {
                // Time to crossfade!
                this.engine.crossfadeTo(
                    this.mixCommand.next_video_id,
                    this.mixCommand.next_seek_to,
                    this.mixCommand.fade_duration,
                );
                this.mixCommand = null;
            }
        }, 500);
    }

    onTrackEnded() {
        // Tell backend we've moved to next track
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'track_ended' }));
            this.requestMixCommand();
        }
    }

    updateNowPlaying() {
        const track = this.queue[this.currentIndex];
        if (!track) return;

        this.els.nowPlaying.classList.add('active');
        this.els.trackTitle.textContent = track.title;
        this.els.trackMeta.textContent = `${track.bpm} BPM · ${track.camelot}`;

        const next = this.queue[this.currentIndex + 1];
        if (next) {
            this.els.nextUp.textContent = `Next: ${next.title}`;
        } else {
            this.els.nextUp.textContent = 'Last track in queue';
        }
    }

    updateQueue() {
        this.els.queueSection.classList.add('active');
        this.els.queueList.innerHTML = '';

        this.queue.forEach((track, i) => {
            const item = document.createElement('div');
            item.className = 'queue-item' + (i === this.currentIndex ? ' current' : '');
            item.innerHTML = `
                <span class="idx">${i + 1}</span>
                <span class="title">${track.title}</span>
                <span class="bpm">${track.bpm}</span>
                <span class="key">${track.camelot}</span>
            `;
            this.els.queueList.appendChild(item);
        });
    }

    setStatus(text) {
        this.els.statusBar.classList.add('active');
        this.els.statusText.textContent = text;
    }

    hideStatus() {
        this.els.statusBar.classList.remove('active');
    }
}

// Start the app
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DjwalaApp();
});
```

**Step 4: Update `static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DjwalaAI</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div class="container">
        <h1>DjwalaAI</h1>
        <p class="subtitle">AI-powered auto-DJ from YouTube</p>

        <div class="input-section">
            <div class="mode-tabs">
                <button class="mode-tab" data-mode="seed">Seed Song</button>
                <button class="mode-tab active" data-mode="vibe">Vibe</button>
                <button class="mode-tab" data-mode="artists">Artists</button>
            </div>
            <div class="search-row">
                <input type="text" class="search-input" placeholder="Describe a vibe... (e.g., &quot;deep house chill&quot;)">
                <button class="go-btn">DJ!</button>
            </div>
        </div>

        <div class="status-bar">
            <span class="status-text">Ready</span>
        </div>

        <div class="now-playing">
            <h3>Now Playing</h3>
            <div class="track-title"></div>
            <div class="track-meta"></div>
            <div class="next-up"></div>
        </div>

        <div class="queue">
            <h3>Queue</h3>
            <div class="queue-list"></div>
        </div>
    </div>

    <div class="players-container"></div>

    <script src="/static/js/mix-engine.js"></script>
    <script src="/static/js/app.js"></script>
</body>
</html>
```

**Step 5: Verify manually**

Run:
```bash
cd /Users/ashishkshirsagar/Projects/djwalaAI
source .venv/bin/activate
uvicorn src.djwala.main:app --reload --port 8000
```

Open `http://localhost:8000/static/index.html` in browser. Verify:
- Page loads with styled UI
- Three mode tabs work
- Input field placeholder changes per mode

**Step 6: Commit**

```bash
git add static/
git commit -m "feat: frontend with YouTube IFrame players, mix engine, and queue UI"
```

---

## Task 8: Integration & End-to-End Smoke Test

**Files:**
- Create: `tests/test_integration.py`
- Create: `scripts/run.sh`

**Step 1: Create `scripts/run.sh`**

```bash
#!/usr/bin/env bash
# Start DjwalaAI server
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
echo "Starting DjwalaAI on http://localhost:8000"
echo "Open http://localhost:8000/static/index.html"
uvicorn src.djwala.main:app --reload --port 8000
```

**Step 2: Create `tests/test_integration.py`**

```python
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
        structure=[],
        mix_in_point=2.0,
        mix_out_point=224.0,
        drop_timestamp=60.0,
        has_vocals=False,
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
        session = manager.create_session(InputMode.VIBE, "deep house")
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
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 4: Make run script executable and commit**

```bash
chmod +x scripts/run.sh
git add tests/test_integration.py scripts/run.sh
git commit -m "feat: integration tests and run script"
```

---

## Summary

| Task | Component | Files |
|------|-----------|-------|
| 1 | Scaffolding & Models | `pyproject.toml`, `models.py`, `main.py` |
| 2 | Analysis Cache | `cache.py`, `test_cache.py` |
| 3 | YouTube Search | `youtube.py`, `test_youtube.py` |
| 4 | Audio Analyzer | `analyzer.py`, `test_analyzer.py` |
| 5 | DJ Brain | `brain.py`, `test_brain.py` |
| 6 | API & Session | `session.py`, `main.py`, `test_api.py` |
| 7 | Frontend | `index.html`, `mix-engine.js`, `app.js`, `style.css` |
| 8 | Integration | `test_integration.py`, `run.sh` |

**Total: 8 tasks, ~20 files, TDD throughout.**
