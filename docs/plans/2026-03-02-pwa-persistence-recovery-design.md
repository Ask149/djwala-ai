# PWA + Session Persistence + Error Recovery — Design Doc

**Date:** 2026-03-02
**Status:** Approved
**Goal:** Make the app installable, survive page refreshes, and handle YouTube playback failures gracefully

---

## Feature 1: PWA (Progressive Web App)

### Problem

Users can't "install" DjwalaAI on their phone or desktop. It's just a browser tab that gets lost. PWA makes it feel like a real app and increases return visits.

### Solution

Minimal PWA — just enough for install eligibility and faster repeat loads. No offline support (app requires YouTube).

### Components

**`static/manifest.json`:**
- `name`: "DjwalaAI"
- `short_name`: "DjwalaAI"
- `description`: "AI-Powered Auto-DJ — seamless music mixes"
- `start_url`: "/"
- `display`: "standalone"
- `theme_color`: "#0a0a0f"
- `background_color`: "#0a0a0f"
- Icons: generate 192x192 and 512x512 PNG icons from the 🎧 emoji

**`static/sw.js`:**
- Cache app shell on install: `index.html`, `style.css`, `app.js`, `mix-engine.js`, `og-image.png`
- Serve cached assets with network-first strategy (try network, fall back to cache)
- No API/YouTube caching
- Cache version string for easy invalidation

**`index.html` changes:**
- Add `<link rel="manifest" href="/static/manifest.json">`
- Add `<meta name="apple-mobile-web-app-capable" content="yes">`
- Add `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">`
- Register service worker in a `<script>` block

### Out of Scope

- Offline page / offline playback
- Push notifications
- Background sync

---

## Feature 2: Session Persistence

### Problem

Refreshing the page kills the current session. User loses their queue, position, and has to start over.

### Solution

Save minimal session state to `localStorage`. On reload, attempt to restore from backend. If backend session expired, gracefully fall back to landing page.

### What to Save

```json
{
  "sessionId": "abc123",
  "mode": "artists",
  "query": "Drake, The Weeknd",
  "moodId": null,
  "currentIndex": 2
}
```

Key: `djwala_session` in `localStorage`.

### What NOT to Save

- Full queue (backend has it; could be large)
- Playback position within a track (YouTube iFrame resume is fragile)
- WebSocket state (will reconnect)

### Restore Flow

1. Page load → check `localStorage` for `djwala_session`
2. If found → `fetch(/session/{id}/queue)` to verify backend still has it
3. Backend responds `ready` with tracks → restore UI:
   - Set `this.queue`, `this.currentIndex`, `this.mode`
   - Show queue, deck, player bar in "ready" state
   - User taps play to resume (starts current track from beginning)
4. Backend returns error or empty → clear saved state, show normal landing page

### Save Triggers

- Session starts (`startSession`, `startMoodSession`)
- Track changes (`refreshQueue` when `currentIndex` updates)

### Clear Triggers

- New session started (replaces old)
- Backend session not found on restore attempt
- No explicit "clear session" button needed

---

## Feature 3: Error Recovery (Auto-skip)

### Problem

When YouTube can't play a video (blocked, age-restricted, region-locked, removed), the app silently fails. No error handling, no recovery.

### Solution

Add `onError` handling to both YouTube players. Auto-skip to next track with a brief notification. Stop after 3 consecutive errors to prevent infinite loops.

### YouTube Error Codes

| Code | Meaning |
|------|---------|
| 2 | Invalid video ID |
| 5 | HTML5 player error |
| 100 | Video not found / removed |
| 101 | Embedding not allowed |
| 150 | Same as 101 (embedding blocked) |

### MixEngine Changes

- Add `onError` callback parameter to constructor (alongside existing `onTrackChange`)
- Wire `onError` event handler to both `deckA` and `deckB` YouTube players
- Only fire for the active deck (ignore inactive deck errors during warm-up)

### App.js Changes

- Track `this.consecutiveErrors` counter (default 0)
- On error:
  1. Increment `consecutiveErrors`
  2. If `consecutiveErrors >= 3` → show "Multiple tracks unavailable" error, stop
  3. Otherwise → show brief toast "Track unavailable, skipping..." (auto-dismiss 3s)
  4. Send `track_ended` to backend → advance → play next track
- Reset `consecutiveErrors = 0` when a track starts playing successfully (detected via position monitor: `currentTime > 1`)

### Toast UI

- Simple `<div class="toast">` appended to body
- Auto-dismiss after 3 seconds
- CSS: fixed bottom-center, dark background, subtle slide-up animation
- No new HTML needed — created dynamically in JS

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| No offline support in PWA | App fundamentally requires YouTube streaming |
| Network-first caching | Always serve fresh content, cache is just a speed boost |
| Don't save full queue to localStorage | Backend has it; avoids stale data and storage limits |
| Resume from track start, not mid-track | YouTube iFrame position restore is unreliable |
| 3 consecutive errors cutoff | Prevents infinite skip loops while tolerating occasional failures |
| Toast for errors, not modal | Non-intrusive; user is listening to music, don't break the flow |
