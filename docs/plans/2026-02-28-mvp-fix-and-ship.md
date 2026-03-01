# MVP Fix-and-Ship Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the critical search bug, cut unused features (Vibe/Seed modes, fake structure detection, genre extraction), simplify UI to Artists-only, consolidate docs, and deploy a working MVP to Fly.io.

**Architecture:** Keep existing FastAPI + yt-dlp + librosa stack. Remove dead code and fake analysis features. Simplify frontend to single-mode (Artists). Fix the root-cause search bug (extractor_args breaking yt-dlp search).

**Tech Stack:** Python 3.12, FastAPI, yt-dlp, librosa, SQLite (cache), vanilla JS frontend, Fly.io deployment

---

## Pre-flight

- **All 83 tests currently pass** (verified 2026-02-28)
- **Root cause confirmed:** `extractor_args` in `_search_with_ytdlp()` breaks search when combined with `extract_flat: True`
- **Approach:** "Fix and Ship" — minimal changes, fix the bug, cut dead code, deploy

---

### Task 1: Fix the Critical Search Bug

**Files:**
- Modify: `src/djwala/youtube.py:246-258`

**Why:** The `extractor_args` block (`player_client`, `player_skip`) in `_search_with_ytdlp()` completely breaks yt-dlp's `ytsearch` when combined with `extract_flat: True`. This is THE bug that makes the entire app non-functional. Removing these 4 lines fixes search both locally and on Fly.io (verified via SSH).

**Step 1: Run existing tests to confirm green baseline**

Run: `.venv/bin/python -m pytest tests/test_youtube.py -v`
Expected: All tests PASS

**Step 2: Remove extractor_args from search ydl_opts**

In `src/djwala/youtube.py`, lines 246-258, change the `ydl_opts` dict from:

```python
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            },
        }
```

To:

```python
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
```

**Step 3: Also remove extractor_args from _queries_from_seed (seed URL extraction)**

In `src/djwala/youtube.py`, lines 132-145, change:

```python
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            },
        }
```

To:

```python
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
```

**Step 4: Run tests to confirm nothing broke**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 83 tests PASS

---

### Task 2: Remove Duplicate Method Stub

**Files:**
- Modify: `src/djwala/youtube.py:226-229`

**Why:** `_search_with_ytdlp` is defined twice — lines 226-229 (empty stub with just docstring) and lines 231-281 (real implementation). The second definition silently overwrites the first. This is dead code that confuses readers.

**Step 1: Delete the stub**

Remove lines 226-229:
```python
    def _search_with_ytdlp(
        self, queries: list[str], mode: InputMode, query: str, max_results: int
    ) -> list[TrackInfo]:
        """Search using yt-dlp (fallback method, may be blocked in production)."""
```

Keep only the real implementation (which starts immediately after).

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

---

### Task 3: Remove Genre Extraction from youtube.py

**Files:**
- Modify: `src/djwala/youtube.py`
- Modify: `tests/test_youtube.py:79-88`

**Why:** `genre_hint` is extracted from YouTube title brackets (e.g., "[Deep House]") which is unreliable and not used by the DJ brain for mixing decisions. The brain uses BPM and Camelot key, not genre.

**Step 1: Delete `GENRE_KEYWORDS` constant (lines 22-29)**

Remove:
```python
GENRE_KEYWORDS = [
    "house", "deep house", "progressive house", "tech house",
    "techno", "melodic techno", "trance", "psytrance",
    "drum and bass", "dnb", "dubstep", "ambient",
    "lo-fi", "lofi", "hip hop", "r&b", "pop", "indie",
    "edm", "electronic", "dance", "disco", "funk",
    "bollywood", "punjabi", "desi", "bhangra",
]
```

**Step 2: Delete `_extract_genre()` method (lines 320-335)**

Remove the entire method.

**Step 3: Remove genre_hint from `_parse_entry()` (line 297 and 304)**

Change `_parse_entry` to not call `_extract_genre` and not set `genre_hint`:

```python
    def _parse_entry(self, entry: dict) -> TrackInfo | None:
        """Parse a yt-dlp entry dict into TrackInfo. Returns None if invalid."""
        video_id = entry.get('id', '')
        title = entry.get('title', '')
        duration = entry.get('duration')
        channel = entry.get('channel', '') or entry.get('uploader', '')

        if not duration or duration < MIN_DURATION or duration > MAX_DURATION:
            return None

        if self._is_compilation(title):
            return None

        return TrackInfo(
            video_id=video_id,
            title=title,
            duration=float(duration),
            channel=channel,
        )
```

**Step 4: Remove genre_hint from `_search_with_api()` (line 216)**

Delete the line:
```python
                    track.genre_hint = self._extract_genre(track.title)
```

**Step 5: Update test — remove `test_genre_hint_from_title`**

In `tests/test_youtube.py`, delete lines 79-88:
```python
    def test_genre_hint_from_title(self):
        yt = YouTubeSearch()
        entry = {
            'id': 'abc',
            'title': 'Track Name [Progressive House]',
            'duration': 300,
            'channel': 'Ch',
        }
        track = yt._parse_entry(entry)
        assert "progressive house" in track.genre_hint.lower()
```

**Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: 82 tests PASS (1 removed)

---

### Task 4: Remove Dead Fields from Models

**Files:**
- Modify: `src/djwala/models.py`
- Modify: `tests/conftest.py`

**Why:** `structure`, `drop_timestamp`, `has_vocals`, `genre_hint` on TrackAnalysis are either fake (structure always assigns same labels regardless of content), unused by the brain, or removed upstream (genre_hint from Task 3). Also remove `genre_hint` from TrackInfo and delete dead `SessionRequest` class.

**Step 1: Remove `genre_hint` from TrackInfo**

In `src/djwala/models.py`, change TrackInfo from:
```python
@dataclass
class TrackInfo:
    """Basic track info from YouTube search (before analysis)."""
    video_id: str
    title: str
    duration: float
    channel: str = ""
    genre_hint: str = ""
```

To:
```python
@dataclass
class TrackInfo:
    """Basic track info from YouTube search (before analysis)."""
    video_id: str
    title: str
    duration: float
    channel: str = ""
```

**Step 2: Remove `structure`, `drop_timestamp`, `has_vocals`, `genre_hint` from TrackAnalysis**

Change TrackAnalysis from:
```python
@dataclass
class TrackAnalysis:
    """Full DJ analysis of a track."""
    video_id: str
    title: str
    duration: float
    bpm: float
    key: str
    camelot: str
    energy_curve: list[float] = field(default_factory=list)
    structure: list[dict] = field(default_factory=list)
    mix_in_point: float = 0.0
    mix_out_point: float = 0.0
    drop_timestamp: float = 0.0
    has_vocals: bool = False
    genre_hint: str = ""
```

To:
```python
@dataclass
class TrackAnalysis:
    """Full DJ analysis of a track."""
    video_id: str
    title: str
    duration: float
    bpm: float
    key: str
    camelot: str
    energy_curve: list[float] = field(default_factory=list)
    mix_in_point: float = 0.0
    mix_out_point: float = 0.0
```

**Step 3: Delete dead `SessionRequest` class**

Remove the entire class at lines 54-58:
```python
@dataclass
class SessionRequest:
    """User request to start a DJ session."""
    mode: InputMode
    query: str
```

**Step 4: Update test fixtures in conftest.py**

Change `sample_analysis` fixture to:
```python
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
```

**Step 5: Run tests (expect some failures — will fix in next tasks)**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: Some tests may fail due to removed fields referenced elsewhere. Note which ones.

---

### Task 5: Remove Fake Analysis Methods from analyzer.py

**Files:**
- Modify: `src/djwala/analyzer.py:108-133, 189-265`
- Modify: `tests/test_analyzer.py:83-88`

**Why:** `_detect_structure()` always assigns the same labels ["intro", "buildup", "verse", "chorus", "breakdown", "outro"] regardless of content — it's fake. `_detect_vocals()` and `_find_drop()` are unused by the brain. Removing them simplifies the analyzer to its core value: BPM, key, energy curve, mix points.

**Step 1: Remove `_detect_structure()`, `_detect_vocals()`, `_find_drop()` methods**

Delete these three methods entirely:
- `_detect_structure` (lines 189-212)
- `_find_drop` (lines 214-227)
- `_detect_vocals` (lines 255-265)

**Step 2: Update `_analyze_audio()` to remove calls to deleted methods**

Change `_analyze_audio` from:
```python
    def _analyze_audio(self, y, sr, track):
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
```

To:
```python
    def _analyze_audio(self, y, sr, track):
        bpm = self._detect_bpm(y, sr)
        key, camelot = self._detect_key(y, sr)
        energy_curve = self._compute_energy_curve(y, sr)
        mix_in = self._find_mix_in(energy_curve)
        mix_out = self._find_mix_out(energy_curve, track.duration)

        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=track.duration,
            bpm=bpm,
            key=key,
            camelot=camelot,
            energy_curve=energy_curve,
            mix_in_point=mix_in,
            mix_out_point=mix_out,
        )
```

**Step 3: Remove `TestDropDetection` from test_analyzer.py**

Delete lines 83-88:
```python
class TestDropDetection:
    def test_finds_energy_spike(self, analyzer):
        energy_curve = [0.1] * 5 + [0.9] * 5
        drop = analyzer._find_drop(energy_curve)
        assert 4 <= drop <= 6
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: Tests pass (some may still fail from Task 4 cascading changes)

---

### Task 6: Fix Encapsulation Break and Remove Dead Fields from main.py

**Files:**
- Modify: `src/djwala/main.py:130-147`
- Modify: `src/djwala/session.py`

**Why:** `main.py` line 132 accesses `manager._cache.get(video_id)` directly (breaks encapsulation). Also, the `/track/{video_id}` endpoint returns `drop_timestamp`, `has_vocals`, and `structure` which no longer exist.

**Step 1: Add public method to SessionManager**

In `src/djwala/session.py`, add after `get_session()`:
```python
    def get_cached_analysis(self, video_id: str) -> TrackAnalysis | None:
        """Get cached analysis for a track, if available."""
        if self._cache.has(video_id):
            return self._cache.get(video_id)
        return None
```

**Step 2: Update `/track/{video_id}` endpoint in main.py**

Change from:
```python
@app.get("/track/{video_id}")
async def get_track(video_id: str):
    analysis = manager._cache.get(video_id)
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
```

To:
```python
@app.get("/track/{video_id}")
async def get_track(video_id: str):
    analysis = manager.get_cached_analysis(video_id)
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
    }
```

**Step 3: Fix STATIC_DIR to use Settings**

In `main.py` line 26, change:
```python
STATIC_DIR = Path(os.getenv("DJWALA_STATIC_DIR", Path(__file__).resolve().parent.parent.parent / "static"))
```

To:
```python
STATIC_DIR = Path(os.getenv("DJWALA_STATIC_DIR", str(Path(__file__).resolve().parent.parent.parent / "static")))
```

(Minor: ensure the default arg is a string, not a Path object — `os.getenv` expects string default)

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

---

### Task 7: Update Integration Test Fixtures

**Files:**
- Modify: `tests/test_integration.py:10-24`

**Why:** The `_mock_analysis` helper still creates TrackAnalysis with `structure`, `drop_timestamp`, `has_vocals` which no longer exist on the dataclass.

**Step 1: Update `_mock_analysis` helper**

Change from:
```python
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
```

To:
```python
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
```

**Step 2: Run ALL tests to verify everything passes**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS (count should be ~80, down from 83 due to removed tests)

---

### Task 8: Simplify Frontend — Artists Only

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/app.js`
- Modify: `static/css/style.css`

**Why:** Vibe and Seed modes add complexity but Artists mode is the core use case for Bollywood music discovery. Simplify to single input field.

**Step 1: Remove mode tabs from HTML**

In `static/index.html`, change the input-section from:
```html
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
```

To:
```html
        <div class="input-section">
            <div class="search-row">
                <input type="text" class="search-input" placeholder="Artist names, comma separated... (e.g., &quot;Arijit Singh, Pritam, AP Dhillon&quot;)">
                <button class="go-btn">DJ!</button>
            </div>
        </div>
```

**Step 2: Hardcode mode in app.js**

In `static/js/app.js`, change constructor:
```javascript
        this.mode = 'artists';  // was 'vibe'
```

Remove `modeTabs` from `this.els`:
```javascript
        this.els = {
            searchInput: document.querySelector('.search-input'),
            goBtn: document.querySelector('.go-btn'),
            // ... rest stays
        };
```

Remove the `bindEvents` tab-switching block:
```javascript
    bindEvents() {
        this.els.goBtn.addEventListener('click', () => this.startSession());
        this.els.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') this.startSession();
        });
    }
```

Remove the `updatePlaceholder()` method entirely (no longer needed).

**Step 3: Remove tab styles from CSS**

In `static/css/style.css`, remove:
```css
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
```

**Step 4: Verify the app still starts**

Run: `.venv/bin/python -m uvicorn djwala.main:app --port 8889`
Open `http://localhost:8889` in browser — verify no JS errors, single input shows.
Kill the server.

---

### Task 9: Remove Vibe/Seed Mode Backend Code

**Files:**
- Modify: `src/djwala/youtube.py`
- Modify: `src/djwala/models.py`
- Modify: `tests/test_youtube.py`

**Why:** With frontend hardcoded to Artists, the Vibe and Seed query-building code paths are dead. Keep `InputMode` as an enum with just `ARTISTS` for now (the backend `/session` endpoint still uses it).

**Step 1: Simplify InputMode enum**

In `src/djwala/models.py`, change:
```python
class InputMode(str, Enum):
    SEED = "seed"
    VIBE = "vibe"
    ARTISTS = "artists"
```

To:
```python
class InputMode(str, Enum):
    ARTISTS = "artists"
```

**Step 2: Simplify `build_queries()` in youtube.py**

Remove Vibe and Seed branches. Change from full if/elif chain to:
```python
    def build_queries(self, mode: InputMode, query: str) -> list[str]:
        """Build search queries for artist-based input."""
        artists = [a.strip() for a in query.split(",") if a.strip()]
        suffixes = self._get_suffixes(query)
        queries = []
        for artist in artists:
            artist_suffixes = self._get_suffixes(artist) if self._is_desi_query(artist) else suffixes
            for suffix in artist_suffixes:
                queries.append(f"{artist} {suffix}")
        return queries
```

**Step 3: Remove `_queries_from_seed()` and `_strip_mood_words()` and `_MOOD_WORDS`**

Delete:
- `_MOOD_WORDS` dict (lines 32-39)
- `_strip_mood_words()` static method (lines 86-90)
- `_queries_from_seed()` method (lines 130-167)

Also remove Seed/Vibe handling from `search()` method — simplify to:
```python
    def search(self, mode: InputMode, query: str, max_results: int = 20) -> list[TrackInfo]:
        """Search YouTube and return candidate tracks."""
        queries = self.build_queries(mode, query)
        try:
            return self._search_with_ytdlp(queries, mode, query, max_results)
        except Exception as e:
            if self._api_search:
                try:
                    return self._search_with_api(queries, max_results)
                except Exception:
                    raise e
            raise
```

**Step 4: Update tests — remove Vibe/Seed tests**

In `tests/test_youtube.py`:
- Remove `TestQueryBuilding::test_vibe_query` (lines 12-19)
- Remove `TestQueryBuilding::test_seed_query_from_title` (lines 28-37)
- Remove `TestMoodWordStripping` class entirely (lines 183-205)
- Remove `TestBollywoodQueries::test_vibe_bollywood_strips_party` (lines 211-220)

**Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All remaining tests PASS

---

### Task 10: Clean Up Files — Delete Screenshots, Redundant Docs, Dead Config

**Files:**
- Delete: `CURRENT_STATUS.md`, `DEPLOYMENT_COMPLETE.md`, `DEPLOYMENT_STATUS.md`, `DEPLOYMENT_SUMMARY.md`, `NEXT_STEPS.md`, `INTEGRATION_SUMMARY.md`, `YOUTUBE_COOKIES.md`, `QUICKSTART.md`
- Delete: `docker-compose.prod.yml`, `Caddyfile`
- Delete: All `djwala-*.png` screenshot files
- Keep: `FLY_DEPLOYMENT.md`, `YOUTUBE_API_SETUP.md`, `fly.toml`, `Dockerfile`, `docker-compose.yml`

**Step 1: Delete redundant docs**

```bash
rm -f CURRENT_STATUS.md DEPLOYMENT_COMPLETE.md DEPLOYMENT_STATUS.md DEPLOYMENT_SUMMARY.md NEXT_STEPS.md INTEGRATION_SUMMARY.md YOUTUBE_COOKIES.md QUICKSTART.md
```

**Step 2: Delete dead config files**

```bash
rm -f docker-compose.prod.yml Caddyfile
```

**Step 3: Delete screenshot files**

```bash
rm -f djwala-*.png
```

**Step 4: Verify nothing breaks**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests still PASS (none of these files are referenced by code)

---

### Task 11: Create README.md

**Files:**
- Create: `README.md`

**Why:** The project has no README. Create a concise one from the useful bits of the deleted docs.

**Step 1: Write README.md**

```markdown
# DjwalaAI

AI-powered auto-DJ for Bollywood and Indian music. Enter your favorite artists, get a DJ-quality mixed playlist with BPM matching, harmonic mixing (Camelot wheel), and smooth crossfades.

## Quick Start

```bash
# Install dependencies
uv sync

# Run locally
uv run uvicorn djwala.main:app --port 8888

# Open http://localhost:8888
```

## How It Works

1. **Search** — Enter artist names (e.g., "Arijit Singh, Pritam, AP Dhillon")
2. **Analyze** — Downloads audio, detects BPM, key (Camelot wheel), and energy curve
3. **Order** — Sorts tracks for smooth DJ transitions (key compatibility + BPM proximity)
4. **Mix** — Plays tracks with cosine/sine crossfades at optimal mix points

## Tech Stack

- **Backend:** Python, FastAPI, yt-dlp, librosa
- **Frontend:** Vanilla JS, YouTube IFrame API
- **Analysis:** BPM detection, chroma-based key detection, Camelot wheel mapping
- **Mixing:** Cosine crossfade, energy-aware mix points
- **Cache:** SQLite (avoids re-analyzing tracks)

## Deployment

Deployed on Fly.io. See `FLY_DEPLOYMENT.md` for details.

```bash
fly deploy
```

## Tests

```bash
uv run pytest tests/ -v
```
```

**Step 2: Verify tests still pass**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

---

### Task 12: Delete SQLite Cache DB (Development Artifact)

**Files:**
- Delete: `djwala_cache.db`
- Modify: `.gitignore`

**Why:** The cache DB contains cached analysis from development. It shouldn't be in the repo. Add it to .gitignore.

**Step 1: Delete the cache DB**

```bash
rm -f djwala_cache.db
```

**Step 2: Add to .gitignore**

Add `*.db` to `.gitignore` if not already present.

**Step 3: Verify**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

---

### Task 13: Final Verification — Full Test Suite

**Files:** None (verification only)

**Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (approximately 68-72 tests, down from 83 due to removed tests for deleted features)

**Step 2: Start the server and verify it loads**

Run: `.venv/bin/python -m uvicorn djwala.main:app --port 8889`
Open `http://localhost:8889` — verify:
- Page loads with gradient header "DjwalaAI"
- Single input field with placeholder mentioning artists
- No mode tabs visible
- No JS console errors
Kill the server.

**Step 3: Verify health endpoint**

Run: `curl http://localhost:8889/health`
Expected: `{"status":"ok"}`

---

### Task 14: Deploy to Fly.io

**Files:** None (deployment only)

**Step 1: Ensure fly.toml is correct**

Verify `fly.toml` has:
- `app = "djwala-ai"`
- Internal port 8888
- Volume mount at `/data`

**Step 2: Deploy**

Run: `fly deploy`

**Step 3: Verify production**

Run: `curl https://djwala-ai.fly.dev/health`
Expected: `{"status":"ok"}`

Open `https://djwala-ai.fly.dev/` — verify same as local.

---

## Summary of Changes

| Area | Before | After |
|------|--------|-------|
| Search bug | extractor_args breaks yt-dlp search → 0 results | Fixed — search works locally & production |
| Input modes | 3 modes (Seed, Vibe, Artists) | 1 mode (Artists) |
| Analysis | BPM, key, energy, structure (fake), vocals, drop, genre | BPM, key, energy, mix points |
| Model fields | 11 fields on TrackAnalysis | 8 fields |
| Frontend | Tab-based mode selection | Single input field |
| Documentation | 10 markdown files (4 say "yt-dlp blocked") | README.md + 2 reference docs |
| Tests | 83 tests | ~70 tests (removed tests for deleted features) |
| Screenshots | 14 PNG files in repo root | None |
