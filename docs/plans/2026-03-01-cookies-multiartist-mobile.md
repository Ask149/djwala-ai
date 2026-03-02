# YouTube Cookies + Multi-Artist + Mobile UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Three improvements to DjwalaAI: (1) YouTube cookies on Fly.io for real audio analysis, (2) multi-artist comma-separated input with fair track distribution, (3) mobile-responsive UX polish.

**Architecture:** Feature 1 is ops/infra (export cookies, upload to Fly.io volume, verify). Feature 2 touches `youtube.py` (already supports comma-split in `build_queries`), `session.py` (query distribution), and frontend (UX hints). Feature 3 is CSS-only responsive changes. All features are independent and can be committed separately.

**Tech Stack:** yt-dlp cookies, Fly.io volumes, Python/FastAPI, vanilla JS, CSS media queries

---

## Feature 1: YouTube Cookies on Fly.io

### Task 1: Export YouTube cookies locally and verify format

**Files:**
- Create: `/data/youtube-cookies.txt` (on Fly.io volume — not in repo)
- Reference: `src/djwala/analyzer.py:96-106` (existing cookie path checks)

**Context:**
The analyzer already checks three cookie paths (lines 98-101):
```python
cookie_paths = [
    "/data/youtube-cookies.txt",           # Production (Fly.io volume)
    "~/.config/djwala/youtube-cookies.txt", # User config
    "youtube-cookies.txt",                  # Current directory
]
```
No code changes needed. This is purely an ops task.

**Step 1: Export cookies from browser**

Using a browser extension like "Get cookies.txt LOCALLY" (Chrome) or "cookies.txt" (Firefox):
1. Log into YouTube in Chrome/Firefox
2. Navigate to `youtube.com`
3. Export cookies in Netscape format to `youtube-cookies.txt`

Run locally to verify:
```bash
# Verify cookie file format (should be Netscape tab-separated)
head -5 youtube-cookies.txt
# Expected: lines starting with .youtube.com, tab-separated fields
```

**Step 2: Test cookies locally**

```bash
# Create local cookie path
mkdir -p ~/.config/djwala/
cp youtube-cookies.txt ~/.config/djwala/youtube-cookies.txt

# Test with a quick Python script
uv run python -c "
from djwala.analyzer import AudioAnalyzer
from djwala.models import TrackInfo
a = AudioAnalyzer()
t = TrackInfo(video_id='dQw4w9WgXcQ', title='Test', duration=213.0)
result = a.analyze(t)
print(f'BPM: {result.bpm}, Key: {result.key}, Camelot: {result.camelot}')
print('SUCCESS: Real analysis works with cookies')
"
```

Expected: Real BPM/key values (not 120.0/Am/8A)

**Step 3: Upload cookies to Fly.io volume**

```bash
# SSH into the Fly.io machine
fly ssh console -a djwala-ai

# Inside the machine, verify /data exists
ls -la /data/

# Exit SSH
exit

# Upload the cookie file to the volume
# Option A: Use fly sftp
fly sftp shell -a djwala-ai
put youtube-cookies.txt /data/youtube-cookies.txt
exit

# Option B: If sftp doesn't work, use a temporary secret
# Encode as base64, set as secret, decode on startup
```

**Step 4: Verify cookies work on Fly.io**

```bash
# Create a test session and check if BPMs are real (not all 120.0)
curl -s -X POST https://djwala-ai.fly.dev/session \
  -H "Content-Type: application/json" \
  -d '{"mode":"artists","query":"Arijit Singh"}'

# Wait 15s for analysis, then check queue
sleep 15
curl -s https://djwala-ai.fly.dev/session/<SESSION_ID>/queue | python3 -m json.tool

# SUCCESS if: BPMs vary (not all 120.0), keys vary (not all Am/8A)
```

**Step 5: No commit needed** — cookie file is on Fly.io volume, not in repo.

---

## Feature 2: Multi-Artist Support

### Task 2: Write failing tests for multi-artist query distribution

**Files:**
- Modify: `tests/test_youtube.py` — add multi-artist distribution tests
- Reference: `src/djwala/youtube.py:76-85` (build_queries already splits on comma)

**Context:**
`build_queries()` already splits on comma (line 78): `artists = [a.strip() for a in query.split(",") if a.strip()]`.
`_search_with_ytdlp()` already has per-artist caps (lines 136-138). The search infrastructure is ALREADY multi-artist capable.

The real gap is: the frontend placeholder says "comma separated" but there's no visual feedback showing the split worked. And the backend search distribution logic should be verified with tests.

**Step 1: Write the failing tests**

Add to `tests/test_youtube.py`:

```python
class TestMultiArtistDistribution:
    """Test that multi-artist queries distribute results fairly."""

    def test_build_queries_single_artist(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Arijit Singh")
        # Should have suffix variants for one artist
        assert len(queries) >= 3
        assert all("arijit singh" in q.lower() for q in queries)

    def test_build_queries_three_artists(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Arijit Singh, Pritam, AP Dhillon")
        # Should have queries for all three artists
        arijit = [q for q in queries if "arijit" in q.lower()]
        pritam = [q for q in queries if "pritam" in q.lower()]
        ap = [q for q in queries if "ap dhillon" in q.lower()]
        assert len(arijit) >= 1
        assert len(pritam) >= 1
        assert len(ap) >= 1

    def test_build_queries_whitespace_handling(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "  Arijit Singh ,, , Pritam  ")
        # Should handle extra whitespace and empty entries
        assert any("arijit" in q.lower() for q in queries)
        assert any("pritam" in q.lower() for q in queries)
        # Should NOT have empty artist queries
        assert all(len(q.strip()) > 0 for q in queries)

    def test_build_queries_empty_input(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "")
        assert queries == []

    def test_build_queries_only_commas(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, ",,,")
        assert queries == []
```

**Step 2: Run tests to verify they pass (these test existing behavior)**

Run: `uv run pytest tests/test_youtube.py::TestMultiArtistDistribution -v`

Expected: All PASS (the `build_queries` method already handles these cases).
If any FAIL, that's a real bug to fix in Step 3.

**Step 3: Commit tests**

```bash
git add tests/test_youtube.py
git commit -m "test: add multi-artist query distribution tests"
```

---

### Task 3: Add artist chip display to frontend

**Files:**
- Modify: `static/js/app.js` — parse and display artist chips
- Modify: `static/css/style.css` — add chip styles
- Modify: `static/index.html` — bump cache version to `?v=4`

**Context:**
Currently the input is plain text. When the user types "Arijit Singh, Pritam, AP Dhillon" and clicks DJ, there's no visual confirmation that the app understood 3 separate artists. Adding small "chip" tags below the input shows the parsed artists.

**Step 1: Add chip styles to CSS**

Add to end of `static/css/style.css`:

```css
/* Artist chips */
.artist-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
}

.artist-chips:empty { display: none; }

.artist-chip {
    background: #1e1e3a;
    color: #667eea;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.8rem;
    border: 1px solid #333;
}
```

**Step 2: Add chip container to HTML**

In `static/index.html`, add after the `.search-row` div (inside `.input-section`):

```html
<div class="artist-chips"></div>
```

Update cache-bust versions from `?v=3` to `?v=4` on all three static includes.

**Step 3: Add chip rendering logic to app.js**

In `static/js/app.js`, add a method to `DjwalaApp` and call it on session start:

```javascript
parseArtists(query) {
    return query.split(',').map(a => a.trim()).filter(a => a.length > 0);
}

showArtistChips(artists) {
    const container = document.querySelector('.artist-chips');
    container.innerHTML = '';
    artists.forEach(artist => {
        const chip = document.createElement('span');
        chip.className = 'artist-chip';
        chip.textContent = artist;
        container.appendChild(chip);
    });
}
```

In `startSession()`, after getting the query, add:
```javascript
const artists = this.parseArtists(query);
this.showArtistChips(artists);
```

Also add `artistChips: document.querySelector('.artist-chips')` to `this.els`.

**Step 4: Verify locally**

```bash
uv run uvicorn djwala.main:app --host 0.0.0.0 --port 8001 --reload
```

Open browser, type "Arijit Singh, Pritam, AP Dhillon", verify chips appear.

**Step 5: Run all tests**

```bash
uv run pytest --tb=short -q
```

Expected: 81+ tests pass (76 existing + 5 new from Task 2).

**Step 6: Commit**

```bash
git add static/js/app.js static/css/style.css static/index.html
git commit -m "feat: show artist chips on multi-artist input"
```

---

## Feature 3: Mobile UX Polish

### Task 4: Add responsive CSS for mobile viewports

**Files:**
- Modify: `static/css/style.css` — add media queries
- Modify: `static/index.html` — bump cache version to `?v=5` (or `?v=4` if done before Task 3)

**Context:**
The current CSS works on mobile but isn't optimized. Key issues:
- `.container` has `max-width: 700px` and `padding: 2rem 1rem` — OK but could be tighter
- `.search-input` and `.go-btn` are in a flex row — on narrow screens the button may be too small
- `.queue-item` has multiple spans that overflow on small screens
- Title `h1` at `2rem` is fine
- The `.players-container` is already `position: fixed; top: -9999px` — invisible, no issues

**Step 1: Add responsive media queries to CSS**

Add at the end of `static/css/style.css`:

```css
/* Responsive — mobile */
@media (max-width: 480px) {
    .container {
        padding: 1.25rem 0.75rem;
    }

    h1 { font-size: 1.5rem; }
    .subtitle { font-size: 0.85rem; margin-bottom: 1.25rem; }

    .input-section { padding: 1rem; }

    .search-row {
        flex-direction: column;
    }

    .search-input {
        font-size: 0.95rem;
        padding: 0.85rem 0.75rem;
    }

    .go-btn {
        width: 100%;
        padding: 0.85rem;
        font-size: 1rem;
    }

    .now-playing { padding: 1rem; }
    .now-playing .track-title { font-size: 1rem; }

    .queue-item {
        font-size: 0.8rem;
        gap: 0.5rem;
    }

    .queue-item .title {
        min-width: 0;
    }

    .queue-item .bpm { width: 3rem; font-size: 0.75rem; }
    .queue-item .key { width: 2rem; font-size: 0.75rem; }
}

/* Tablet */
@media (min-width: 481px) and (max-width: 768px) {
    .container {
        padding: 1.5rem 1rem;
    }

    .search-input {
        font-size: 0.95rem;
    }
}
```

**Step 2: Add touch-friendly tap targets**

Ensure all interactive elements meet the 44px minimum touch target. Update existing `.go-btn`:

In the existing `.go-btn` rule, add `min-height: 44px;`

**Step 3: Update cache-bust versions in index.html**

Bump `?v=N` to the next version on all static includes.

**Step 4: Test with Playwright at mobile viewport**

```bash
# Start local server
uv run uvicorn djwala.main:app --host 0.0.0.0 --port 8001 --reload &

# Use Playwright to take screenshots at mobile viewport sizes
# (done via MCP browser tool with resize to 375x812 for iPhone SE)
```

Verify:
- Input field stacks vertically on mobile
- DJ button is full width
- Queue items don't overflow
- Text is readable

**Step 5: Run all tests**

```bash
uv run pytest --tb=short -q
```

Expected: All tests pass (CSS changes don't affect backend tests).

**Step 6: Commit**

```bash
git add static/css/style.css static/index.html
git commit -m "feat: mobile-responsive UX — stack input on small screens, tap targets"
```

---

## Summary

| Task | Feature | Type | Files Changed | Estimated Time |
|------|---------|------|---------------|----------------|
| 1 | YouTube Cookies | Ops/Infra | None (Fly.io volume) | 30 min |
| 2 | Multi-Artist Tests | Test | `tests/test_youtube.py` | 10 min |
| 3 | Artist Chips UI | Frontend | `app.js`, `style.css`, `index.html` | 20 min |
| 4 | Mobile Responsive | CSS | `style.css`, `index.html` | 20 min |

**Total estimated time: ~80 min**

**Commit plan: 3 commits** (Task 1 has no code to commit)
1. `test: add multi-artist query distribution tests`
2. `feat: show artist chips on multi-artist input`
3. `feat: mobile-responsive UX — stack input on small screens, tap targets`
