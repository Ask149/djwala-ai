# PWA + Session Persistence + Error Recovery — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make DjwalaAI installable (PWA), survive page refreshes (session persistence), and handle YouTube playback failures gracefully (error recovery with auto-skip).

**Architecture:** All three features are frontend-only (no backend changes needed). PWA adds `manifest.json` + `sw.js`. Session persistence uses `localStorage` with backend validation. Error recovery adds `onError` to YouTube IFrame players in `MixEngine`.

**Tech Stack:** Vanilla JS, Service Worker API, `localStorage`, YouTube IFrame API error events

---

### Task 1: PWA — manifest.json + icons

**Files:**
- Create: `static/manifest.json`
- Create: `static/icons/icon.svg` (single SVG icon used at all sizes)
- Modify: `static/index.html` — add manifest link + Apple meta tags

**Step 1: Create icon SVG**

Create `static/icons/icon.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="96" fill="#0a0a0f"/>
  <text x="256" y="350" font-size="300" text-anchor="middle" font-family="Apple Color Emoji, Segoe UI Emoji, sans-serif">🎧</text>
</svg>
```

**Step 2: Create manifest.json**

Create `static/manifest.json`:

```json
{
  "name": "DjwalaAI — AI-Powered Auto-DJ",
  "short_name": "DjwalaAI",
  "description": "Type any artists. Get a seamless DJ mix with BPM matching and smooth crossfades. Free.",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#0a0a0f",
  "background_color": "#0a0a0f",
  "icons": [
    {
      "src": "/static/icons/icon.svg",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any"
    }
  ]
}
```

**Step 3: Add manifest link and Apple meta tags to index.html**

In `static/index.html`, in the `<head>` section, after the `<meta name="theme-color">` tag (line 25), add:

```html
<link rel="manifest" href="/static/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="/static/icons/icon.svg">
```

**Step 4: Bump cache busters**

Update `?v=15` to `?v=16` on all three asset references in `index.html` (style.css, mix-engine.js, app.js).

**Step 5: Commit**

```bash
git add static/icons/icon.svg static/manifest.json static/index.html
git commit -m "feat: add PWA manifest and app icon for installability"
```

---

### Task 2: PWA — Service Worker

**Files:**
- Create: `static/sw.js`
- Modify: `static/index.html` — register service worker
- Modify: `src/djwala/main.py` — add route for `/sw.js` (service worker scope)

**Step 1: Add `/sw.js` route to main.py**

Service workers must be served from the scope they control. Since our app is at `/`, the SW must be served from `/sw.js` (not `/static/sw.js`).

In `src/djwala/main.py`, after the `@app.get("/")` route (around line 78), add:

```python
@app.get("/sw.js")
async def service_worker():
    """Serve service worker from root for correct scope."""
    from fastapi.responses import FileResponse
    sw = STATIC_DIR / "sw.js"
    if sw.is_file():
        return FileResponse(sw, media_type="application/javascript")
    raise HTTPException(404, "sw.js not found")
```

**Step 2: Create service worker**

Create `static/sw.js`:

```javascript
// DjwalaAI Service Worker — minimal, for PWA installability + asset caching
const CACHE_NAME = 'djwala-v16';
const SHELL_ASSETS = [
    '/',
    '/static/css/style.css?v=16',
    '/static/js/mix-engine.js?v=16',
    '/static/js/app.js?v=16',
    '/static/icons/icon.svg',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(SHELL_ASSETS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Don't cache API calls, WebSocket, analytics, YouTube, or external requests
    if (url.pathname.startsWith('/session') ||
        url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/analytics') ||
        url.pathname.startsWith('/health') ||
        url.origin !== self.location.origin) {
        return; // Let the browser handle it normally
    }

    // Network-first for app shell assets
    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Cache successful responses
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
```

**Step 3: Register service worker in index.html**

In `static/index.html`, before the closing `</body>` tag (after the party overlay), add:

```html
<script>
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
}
</script>
```

**Step 4: Run existing tests**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && .venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All 141 tests PASS (no test behavior changed)

**Step 5: Commit**

```bash
git add static/sw.js src/djwala/main.py static/index.html
git commit -m "feat: add service worker for PWA install and asset caching"
```

---

### Task 3: Error Recovery — MixEngine onError

**Files:**
- Modify: `static/js/mix-engine.js` — add `onError` callback and handler

**Step 1: Add `onError` to MixEngine constructor**

In `static/js/mix-engine.js`, update the constructor (line 5-15) to accept and store an `onError` callback:

```javascript
constructor(onTrackChange, onError) {
    this.deckA = null;
    this.deckB = null;
    this.activeDeck = 'A';
    this.isFading = false;
    this.fadeInterval = null;
    this.onTrackChange = onTrackChange || (() => {});
    this.onError = onError || (() => {});
    this._playersReady = { A: false, B: false };
    this._pendingPlay = null;
    this._warmUpPending = false;
}
```

**Step 2: Wire `onError` event to both YouTube players**

In the `init()` method, add `onError` to both player event configs. Update deckA creation (around line 33):

```javascript
this.deckA = new YT.Player('yt-player-a', {
    height: '1', width: '1',
    playerVars: { autoplay: 0, controls: 0, playsinline: 1 },
    events: {
        onReady: () => { this._playersReady.A = true; this._checkPending(); },
        onStateChange: (e) => this._onStateChange('A', e),
        onError: (e) => this._onError('A', e),
    },
});
```

Update deckB creation (around line 41):

```javascript
this.deckB = new YT.Player('yt-player-b', {
    height: '1', width: '1',
    playerVars: { autoplay: 0, controls: 0, playsinline: 1 },
    events: {
        onReady: () => { this._playersReady.B = true; this._checkPending(); },
        onStateChange: (e) => this._onStateChange('B', e),
        onError: (e) => this._onError('B', e),
    },
});
```

**Step 3: Add `_onError` handler method**

After `_onStateChange` method (around line 172), add:

```javascript
_onError(deck, event) {
    // Only handle errors on the active deck (ignore warm-up errors on inactive)
    const isActive = (deck === this.activeDeck);
    if (!isActive) return;

    console.warn(`[MixEngine] YouTube error on deck ${deck}: code ${event.data}`);
    this.onError(event.data);
}
```

**Step 4: Commit**

```bash
git add static/js/mix-engine.js
git commit -m "feat: add onError callback to MixEngine for YouTube playback failures"
```

---

### Task 4: Error Recovery — App.js auto-skip + toast

**Files:**
- Modify: `static/js/app.js` — handle errors, show toast, auto-skip
- Modify: `static/css/style.css` — toast notification styles

**Step 1: Update MixEngine instantiation with onError**

In `static/js/app.js`, update the `MixEngine` constructor call in the `DjwalaApp` constructor (around line 208):

```javascript
this.engine = new MixEngine(
    () => this.onTrackEnded(),
    (errorCode) => this.onPlaybackError(errorCode)
);
```

**Step 2: Add error tracking state**

In the `DjwalaApp` constructor, after `this.playerState = 'hidden';` (line 206), add:

```javascript
this.consecutiveErrors = 0;
```

**Step 3: Add `onPlaybackError` method**

After `onTrackEnded()` method (around line 880), add:

```javascript
onPlaybackError(errorCode) {
    this.consecutiveErrors++;
    console.warn(`[DjwalaAI] Playback error ${errorCode}, consecutive: ${this.consecutiveErrors}`);

    if (this.consecutiveErrors >= 3) {
        this.showToast('Multiple tracks unavailable. Try a different search.', 5000);
        this.showPlayerBar('ready');
        return;
    }

    const track = this.queue[this.currentIndex];
    const name = track ? track.title : 'Track';
    this.showToast(`${name} unavailable, skipping...`);

    // Auto-advance to next track
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ action: 'track_ended' }));
        this.requestMixCommand();
    }
}
```

**Step 4: Add `showToast` method**

After `onPlaybackError`, add:

```javascript
showToast(message, duration = 3000) {
    // Remove existing toast
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => toast.classList.add('visible'));

    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
```

**Step 5: Reset error counter on successful playback**

In `startPositionMonitor()`, inside the `setInterval` callback, after `const currentTime = this.engine.getCurrentTime();` (around line 776), add:

```javascript
// Reset consecutive error counter on successful playback
if (currentTime > 1 && this.consecutiveErrors > 0) {
    this.consecutiveErrors = 0;
}
```

**Step 6: Add toast CSS**

In `static/css/style.css`, at the end of the file, add:

```css
/* Toast notifications */
.toast {
    position: fixed;
    bottom: 100px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: rgba(30, 30, 45, 0.95);
    color: rgba(255, 255, 255, 0.9);
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    font-size: 0.85rem;
    z-index: 300;
    opacity: 0;
    transition: opacity 0.3s, transform 0.3s;
    pointer-events: none;
    max-width: 90vw;
    text-align: center;
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(8px);
}

.toast.visible {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
}
```

**Step 7: Commit**

```bash
git add static/js/app.js static/css/style.css
git commit -m "feat: auto-skip on YouTube errors with toast notification"
```

---

### Task 5: Session Persistence — Save and Restore

**Files:**
- Modify: `static/js/app.js` — save session state, restore on load

**Step 1: Add `saveSession` method**

In `static/js/app.js`, after `updatePageTitle()` method (around line 1471), add:

```javascript
saveSession() {
    if (!this.sessionId) return;
    const data = {
        sessionId: this.sessionId,
        mode: this.mode,
        query: this.els.searchInput.value.trim(),
        moodId: this.moodId || null,
        currentIndex: this.currentIndex,
    };
    localStorage.setItem('djwala_session', JSON.stringify(data));
}

clearSavedSession() {
    localStorage.removeItem('djwala_session');
}
```

**Step 2: Add `restoreSession` method**

After `clearSavedSession`, add:

```javascript
async restoreSession() {
    const raw = localStorage.getItem('djwala_session');
    if (!raw) return false;

    let saved;
    try {
        saved = JSON.parse(raw);
    } catch {
        this.clearSavedSession();
        return false;
    }

    if (!saved.sessionId) {
        this.clearSavedSession();
        return false;
    }

    // Verify session still exists on backend
    try {
        const resp = await fetch(`/session/${saved.sessionId}/queue`);
        if (!resp.ok) {
            this.clearSavedSession();
            return false;
        }

        const data = await resp.json();
        if (data.status !== 'ready' || !data.tracks || data.tracks.length === 0) {
            this.clearSavedSession();
            return false;
        }

        // Restore state
        this.sessionId = saved.sessionId;
        this.mode = saved.mode || 'artists';
        this.moodId = saved.moodId || null;
        this.queue = data.tracks;
        this.currentIndex = data.current_index;

        // Restore UI
        if (saved.mode && saved.mode !== 'artists') {
            this.setMode(saved.mode);
        }
        if (saved.query) {
            this.els.searchInput.value = saved.query;
        }

        // Hide landing page elements
        const hiw = document.getElementById('howItWorks');
        if (hiw) hiw.classList.add('hidden');
        this.els.moodGrid.classList.add('hidden');

        // Show chips
        if (saved.mode === 'artists' && saved.query) {
            this.showArtistChips(this.parseArtists(saved.query));
        } else if (saved.query) {
            this.showArtistChips([saved.query]);
        }

        // Show queue, timeline, player bar
        this.connectWebSocket();
        this.startPlaying();
        return true;
    } catch {
        this.clearSavedSession();
        return false;
    }
}
```

**Step 3: Call `saveSession` at key points**

3a. In `startSession()`, after `this.sessionId = data.session_id;` (around line 402), add:

```javascript
this.saveSession();
```

3b. In `startMoodSession()`, before `this.startSession();` (around line 350), add — no, `startSession` already saves. But `startMoodSession` sets `this.mode = 'mood'` which needs to be saved. The save happens inside `startSession` after `this.sessionId` is set, so it will capture the mood state. This is fine.

3c. In `refreshQueue()`, after `this.currentIndex = data.current_index;` (around line 459), add:

```javascript
this.saveSession();
```

3d. In `onTrackEnded()`, after the refreshQueue/deck update block (end of method, around line 879), add:

```javascript
this.saveSession();
```

**Step 4: Clear saved session when starting a new one**

In `startSession()`, at the very beginning of the method (after the `if (!query) return;` check), add:

```javascript
this.clearSavedSession();
```

**Step 5: Call `restoreSession` on page load**

In the constructor, replace the `this.loadFromURLParams();` call (line 294) with:

```javascript
this.initRestore();
```

Add the `initRestore` method after `loadFromURLParams`:

```javascript
async initRestore() {
    // URL params take priority (shared links)
    const params = new URLSearchParams(window.location.search);
    if (params.has('mood') || params.has('mode') || params.has('q')) {
        this.clearSavedSession();
        this.loadFromURLParams();
        return;
    }

    // Try to restore previous session
    const restored = await this.restoreSession();
    if (!restored) {
        // No session to restore — normal landing page
    }
}
```

**Step 6: Commit**

```bash
git add static/js/app.js
git commit -m "feat: persist and restore sessions across page refreshes"
```

---

### Task 6: Final polish + bump + deploy

**Step 1: Bump cache busters to v=16**

Verify all three asset references in `static/index.html` use `?v=16`. Also update the `CACHE_NAME` in `static/sw.js` if it doesn't match.

**Step 2: Update README test count**

In `README.md`, update the test count from `133` to `141`:

```markdown
```bash
uv run pytest tests/ -v
# 141 tests passing
```

**Step 3: Run full test suite**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && .venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All 141 tests PASS (no backend logic changed, so no new tests needed)

**Step 4: Commit**

```bash
git add static/index.html static/sw.js README.md
git commit -m "chore: bump cache to v16, update README test count"
```

**Step 5: Deploy**

```bash
cd /Users/ashishkshirsagar/Projects/djwalaAI && fly deploy
```

**Step 6: Verify deployment**

1. Open https://djwala-ai.fly.dev
2. Check DevTools → Application → Manifest (should show DjwalaAI)
3. Check DevTools → Application → Service Workers (should be registered)
4. Start a mix → refresh page → session should restore
5. Check that YouTube error recovery works (hard to test without a blocked video, but verify no console errors from the new code)
