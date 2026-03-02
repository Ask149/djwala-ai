# Phase C: Mood/Genre Presets — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 8 mood preset buttons to the landing page. One tap → instant DJ session with YouTube search queries mapped to that mood. Shareable via `?mood=` URLs.

**Architecture:** New `InputMode.MOOD` enum value. Mood preset map lives in `youtube.py`. Frontend mood grid on landing page, auto-starts session on click. Share URLs support `?mood=house-party`.

**Tech Stack:** Python/FastAPI backend, vanilla JS frontend, pytest tests.

---

### Task 1: Backend — InputMode.MOOD + Preset Map + Search Logic

**Files:**
- Modify: `src/djwala/models.py:9-11` (add MOOD to InputMode)
- Modify: `src/djwala/youtube.py:76-85` (handle mood in build_queries)
- Modify: `src/djwala/session.py:92-95` (route mood to artists pipeline)
- Test: `tests/test_youtube.py` (add mood query tests)
- Test: `tests/test_api.py` (add mood session test)

**Step 1: Add MOOD to InputMode enum**

In `src/djwala/models.py`, add `MOOD = "mood"` to `InputMode`:

```python
class InputMode(str, Enum):
    ARTISTS = "artists"
    SONG = "song"
    MOOD = "mood"
```

**Step 2: Add mood preset map and handle mood in build_queries**

In `src/djwala/youtube.py`, add the preset map constant after `_DESI_HINTS`:

```python
MOOD_PRESETS = {
    "house-party": ["house party hits", "club bangers 2024"],
    "road-trip": ["road trip songs", "driving music hits"],
    "late-night": ["late night r&b", "midnight vibes"],
    "chill-vibes": ["chill lofi beats", "relaxing music"],
    "workout": ["workout music", "gym motivation songs"],
    "bollywood": ["bollywood party songs", "hindi hits"],
    "hip-hop": ["hip hop hits 2024", "rap bangers"],
    "latin": ["reggaeton hits", "latin party music"],
}
```

Update `build_queries()` to handle mood mode:

```python
def build_queries(self, mode: InputMode, query: str) -> list[str]:
    """Build search queries based on mode and input."""
    if mode == InputMode.MOOD:
        preset = MOOD_PRESETS.get(query)
        if preset:
            return list(preset)
        return [query]  # fallback: use raw query
    artists = [a.strip() for a in query.split(",") if a.strip()]
    suffixes = self._get_suffixes(query)
    queries = []
    for artist in artists:
        artist_suffixes = self._get_suffixes(artist) if self._is_desi_query(artist) else suffixes
        for suffix in artist_suffixes:
            queries.append(f"{artist} {suffix}")
    return queries
```

**Step 3: Route mood mode to artists pipeline in session.py**

In `src/djwala/session.py` `build_queue()`, mood uses the same pipeline as artists:

```python
async def build_queue(self, session_id: str) -> None:
    session = self._sessions.get(session_id)
    if not session:
        return
    if session.mode == InputMode.SONG:
        await self._build_song_queue(session)
    else:
        # Both ARTISTS and MOOD use the same pipeline
        await self._build_artists_queue(session)
```

**Step 4: Write tests**

In `tests/test_youtube.py`, add to `TestQueryBuilding`:

```python
def test_mood_queries_house_party(self):
    yt = YouTubeSearch()
    queries = yt.build_queries(InputMode.MOOD, "house-party")
    assert queries == ["house party hits", "club bangers 2024"]

def test_mood_queries_all_presets_exist(self):
    from djwala.youtube import MOOD_PRESETS
    assert len(MOOD_PRESETS) == 8
    for key, queries in MOOD_PRESETS.items():
        assert isinstance(queries, list)
        assert len(queries) >= 1
        assert all(isinstance(q, str) for q in queries)

def test_mood_queries_unknown_fallback(self):
    yt = YouTubeSearch()
    queries = yt.build_queries(InputMode.MOOD, "unknown-mood")
    assert queries == ["unknown-mood"]
```

In `tests/test_api.py`, add:

```python
@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_mood(mock_build, client):
    resp = await client.post("/session", json={
        "mode": "mood",
        "query": "house-party",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    session = manager.get_session(data["session_id"])
    assert session.mode == InputMode.MOOD
```

**Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/test_youtube.py tests/test_api.py -v --tb=short
```

---

### Task 2: Frontend — Mood Grid HTML + CSS

**Files:**
- Modify: `static/index.html:52-53` (add mood grid between input section and status bar)
- Modify: `static/css/style.css` (add mood grid styles)

**Step 1: Add mood grid HTML**

After the `artist-chips` div (line 51) and before the status-bar (line 54), add:

```html
<div class="mood-grid" id="moodGrid">
    <p class="mood-heading">Or pick a vibe</p>
    <div class="mood-pills">
        <button class="mood-pill" data-mood="house-party">🎉 House Party</button>
        <button class="mood-pill" data-mood="road-trip">🚗 Road Trip</button>
        <button class="mood-pill" data-mood="late-night">🌙 Late Night</button>
        <button class="mood-pill" data-mood="chill-vibes">☕ Chill Vibes</button>
        <button class="mood-pill" data-mood="workout">💪 Workout</button>
        <button class="mood-pill" data-mood="bollywood">🎵 Bollywood Hits</button>
        <button class="mood-pill" data-mood="hip-hop">🔥 Hip Hop</button>
        <button class="mood-pill" data-mood="latin">💃 Latin</button>
    </div>
</div>
```

**Step 2: Add mood grid CSS**

```css
/* Mood Grid */
.mood-grid {
    text-align: center;
    margin: 1.5rem 0;
}

.mood-heading {
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.mood-pills {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
    max-width: 500px;
    margin: 0 auto;
}

.mood-pill {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 999px;
    color: #ccc;
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
}

.mood-pill:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.25);
    color: #fff;
    transform: translateY(-1px);
}

.mood-pill:active {
    transform: translateY(0);
}

.mood-grid.hidden {
    display: none;
}

@media (max-width: 480px) {
    .mood-pills {
        grid-template-columns: repeat(2, 1fr);
    }
}
```

**Step 3: Bump cache version to v=13 in index.html**

---

### Task 3: Frontend — Mood Click Handler, URL Params, Share, Analytics

**Files:**
- Modify: `static/js/app.js` (mood grid refs, click handler, URL params, share)

**Step 1: Add element refs**

In the constructor `this.els` block, add:

```javascript
moodGrid: document.getElementById('moodGrid'),
moodPills: document.querySelectorAll('.mood-pill'),
```

**Step 2: Add mood click handler in bindEvents()**

```javascript
this.els.moodPills.forEach(pill => {
    pill.addEventListener('click', () => this.startMoodSession(pill.dataset.mood, pill.textContent.trim()));
});
```

**Step 3: Add startMoodSession method**

```javascript
startMoodSession(moodId, label) {
    this.mode = 'mood';
    this.moodId = moodId;
    this.els.searchInput.value = label;
    this.els.moodGrid.classList.add('hidden');
    this.trackEvent('mood_start', { mood: moodId });
    this.startSession();
}
```

**Step 4: Update startSession to handle mood mode**

In `startSession()`, the POST body already sends `this.mode` and the input value. For mood, `this.mode` will be `'mood'` and `this.els.searchInput.value` will be the label. But the backend expects the mood ID as query. Fix: when mode is mood, send `this.moodId` as query.

Update the POST body in startSession:

```javascript
const body = {
    mode: this.mode,
    query: this.mode === 'mood' ? this.moodId : query,
    mix_length: this.mixLength,
};
```

**Step 5: Hide mood grid on session start, show on reset**

In `startSession()` after validation: `this.els.moodGrid.classList.add('hidden');`

When the session ends or is reset, show it again (if applicable — check if there's a reset flow).

**Step 6: Update loadFromURLParams for `?mood=`**

```javascript
loadFromURLParams() {
    const params = new URLSearchParams(window.location.search);
    const mood = params.get('mood');

    if (mood) {
        // Find the matching pill label
        const pill = document.querySelector(`.mood-pill[data-mood="${mood}"]`);
        const label = pill ? pill.textContent.trim() : mood;
        window.history.replaceState({}, '', window.location.pathname);
        this.startMoodSession(mood, label);
        return;
    }

    const mode = params.get('mode');
    const query = params.get('q');
    if (!query) return;
    if (mode === 'song' || mode === 'artists') {
        this.setMode(mode);
    }
    this.els.searchInput.value = query;
    window.history.replaceState({}, '', window.location.pathname);
    this.startSession();
}
```

**Step 7: Update shareCurrentMix for mood mode**

```javascript
shareCurrentMix() {
    const query = this.els.searchInput.value.trim();
    if (!query) {
        this.showShareTooltip('Type something first!', false);
        return;
    }

    const url = new URL(window.location.origin);
    if (this.mode === 'mood') {
        url.searchParams.set('mood', this.moodId);
    } else {
        url.searchParams.set('mode', this.mode);
        url.searchParams.set('q', query);
    }
    // ... rest unchanged
}
```

**Step 8: Run full test suite**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

---

### Task 4: Deploy + Playwright Verification

**Step 1: Deploy**

```bash
fly deploy
```

**Step 2: Playwright tests on https://djwala-ai.fly.dev**

- Verify 8 mood pills visible on landing page
- Click "House Party" → session starts, queue loads
- Verify mood grid hides during session
- Verify share URL contains `?mood=house-party`
- Verify `?mood=chill-vibes` URL auto-starts session
