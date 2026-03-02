# Music Player UI + iOS Audio Fix — Design

**Date:** 2026-03-02  
**Status:** Approved  
**Approach:** Sticky bottom player bar (Approach A)

## Summary

Add a sticky bottom player bar with play/pause, skip, progress bar, thumbnail, and crossfade indicator. Simultaneously fix iOS audio playback by making the play button the user gesture that unlocks audio.

## Features (First Pass)

| Feature | Included | Notes |
|---------|----------|-------|
| Play/Pause button | ✅ | Also fixes iOS audio (user gesture) |
| Skip (next) button | ✅ | Triggers early crossfade |
| Progress bar | ✅ | Display-only, not seekable |
| Track thumbnail | ✅ | YouTube thumbnail, no API call |
| Crossfade indicator | ✅ | Zone marker on progress bar |
| Previous button | ❌ | Crossfade is destructive |
| Volume control | ❌ | System volume sufficient |
| Seek/scrub | ❌ | Breaks mix timing |

## Player Bar Structure

Fixed to bottom of viewport. Three states:

- **Hidden** — No session started (`display: none`)
- **Ready** — Tracks loaded, awaiting user tap. Pulsing ▶ button, "Tap play to start"
- **Playing** — Audio active. ▶ becomes ⏸, progress bar animating

### HTML Structure

```html
<div class="player-bar" id="playerBar">
  <div class="player-bar-inner">
    <img class="player-thumb" id="playerThumb" src="" alt="">
    <div class="player-info">
      <div class="player-title" id="playerTitle"></div>
      <div class="player-meta" id="playerMeta"></div>
    </div>
    <div class="player-controls">
      <button class="player-btn" id="prevBtn">⏮</button>
      <button class="player-btn play-btn" id="playBtn">▶</button>
      <button class="player-btn" id="nextBtn">⏭</button>
    </div>
  </div>
  <div class="player-progress-row">
    <span class="player-time" id="playerElapsed">0:00</span>
    <div class="player-progress" id="playerProgress">
      <div class="player-progress-fill" id="playerProgressFill"></div>
      <div class="player-crossfade-zone" id="playerCrossfadeZone"></div>
    </div>
    <span class="player-time" id="playerRemaining">0:00</span>
  </div>
</div>
```

### Key CSS Decisions

- `position: fixed; bottom: 0; z-index: 50`
- `background: #14141f; border-top: 1px solid #333`
- `padding-bottom: env(safe-area-inset-bottom)` for iPhone notch
- Thumbnail: `48px × 48px; border-radius: 6px; object-fit: cover`
- Progress fill: gradient `#667eea → #764ba2` with `transition: width 0.5s linear` (smooths 500ms polling)
- Container gets `padding-bottom: 100px` to avoid content hidden behind bar
- Prev button hidden via CSS for v1 (HTML present for future use)

## iOS Audio Fix

Three root causes, one elegant solution.

### Fix 1: playsinline

Add `playsinline: 1` to playerVars in both deck player configs in `mix-engine.js`. Without this, iOS attempts fullscreen, conflicting with off-screen positioning.

### Fix 2: Deferred playback

Current (broken on iOS): `"DJ!" tap → fetch → poll 15-20s → loadVideoById()` — user gesture expired.

New: `"DJ!" tap → fetch → poll → show player bar in "Ready" state → user taps ▶ → loadVideoById()` — fresh gesture.

`startPlaying()` changes from auto-play to showing the bar. New `onPlayTap()` method handles actual playback with fresh user gesture context.

### Fix 3: Warm up both decks

On first play tap, warm up the inactive deck by loading a video muted, then pausing on `PLAYING` state change. This "unlocks" both players for iOS, enabling crossfade later.

## Engine Changes (mix-engine.js)

New methods:

| Method | Behavior |
|--------|----------|
| `pause()` | Pause active deck. During crossfade: pause both + fade interval |
| `resume()` | Resume active deck. During crossfade: resume both + interval |
| `isPaused()` | `getActiveDeck().getPlayerState() === YT.PlayerState.PAUSED` |
| `getDuration()` | `getActiveDeck().getDuration()` |
| `warmUpDecks(videoId, seekTo)` | Load on active deck, load+mute+pause on inactive |

Existing methods (`playOnDeck`, `crossfadeTo`, `onTrackChange`) unchanged.

## Progress Bar

Updated every 500ms inside the existing `positionTimer` interval:

- `progressFill.style.width` = percentage of current/duration
- Elapsed time: `formatTime(currentTime)`
- Remaining time: `-formatTime(duration - currentTime)`
- `formatTime(s)`: `Math.floor(s/60) + ':' + pad(Math.floor(s%60))`
- Not seekable — display only

## Crossfade Indicator

When `mixCommand` arrives, calculate fade start as percentage of duration. Render a translucent zone on the right end of the progress bar. When crossfade is actively happening (`engine.isFading`), the zone pulses via CSS animation.

## Files Modified

- `static/index.html` — Add player bar HTML, bump cache to `?v=9`
- `static/css/style.css` — Player bar styles, container padding
- `static/js/mix-engine.js` — `playsinline: 1`, `pause()`, `resume()`, `isPaused()`, `getDuration()`, `warmUpDecks()`
- `static/js/app.js` — Player bar state management, deferred playback, progress updates, skip, play/pause

## No Backend Changes

Zero backend modifications. All changes are frontend-only.
