# Music Player UI + iOS Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a sticky bottom player bar with play/pause, skip, progress bar, thumbnail, and crossfade indicator. Fix iOS audio by making the play button the user gesture.

**Architecture:** All changes are frontend-only (4 files). The player bar is a fixed-position element at the bottom of the viewport. Playback is deferred until the user taps ▶, which provides the iOS user gesture. Both YouTube decks are "warmed up" on first play to enable crossfade on iOS.

**Tech Stack:** Vanilla JS, CSS, HTML. YouTube IFrame API. No build step. No new dependencies.

**Design doc:** `docs/plans/2026-03-02-music-player-ui-design.md`

---

## Task 1: mix-engine.js — playsinline + new methods

**Files:**
- Modify: `static/js/mix-engine.js`

**Why:** Add iOS-critical `playsinline: 1`, plus pause/resume/getDuration/isPaused methods needed by the player bar, plus `warmUpDecks()` for iOS dual-deck unlock.

**Step 1: Add `playsinline: 1` to both player configs**

In the `init()` method, change both playerVars objects (lines 34 and 42):

```javascript
// Line 34 — deckA
playerVars: { autoplay: 0, controls: 0, playsinline: 1 },

// Line 42 — deckB
playerVars: { autoplay: 0, controls: 0, playsinline: 1 },
```

**Step 2: Add new methods after `getCurrentTime()` (after line 81)**

```javascript
    getDuration() {
        const deck = this.getActiveDeck();
        return deck ? deck.getDuration() : 0;
    }

    isPaused() {
        const deck = this.getActiveDeck();
        return deck ? deck.getPlayerState() === 2 : false; // 2 = YT.PlayerState.PAUSED
    }

    pause() {
        if (this.isFading) return; // Don't pause during crossfade (it's only ~5s)
        const deck = this.getActiveDeck();
        if (deck) deck.pauseVideo();
    }

    resume() {
        if (this.isFading) return;
        const deck = this.getActiveDeck();
        if (deck) deck.playVideo();
    }

    warmUpDecks(videoId, seekTo) {
        // Play on active deck (normal)
        const active = this.getActiveDeck();
        active.setVolume(100);
        active.loadVideoById({ videoId, startSeconds: seekTo });

        // Warm up inactive deck for iOS — load muted, pause once it starts
        const inactive = this.getInactiveDeck();
        inactive.setVolume(0);
        inactive.loadVideoById({ videoId, startSeconds: 0 });
        this._warmUpPending = true;
    }
```

**Step 3: Update `_onStateChange` to handle warm-up (replace lines 119-128)**

```javascript
    _onStateChange(deck, event) {
        // Handle warm-up: pause inactive deck once it starts playing
        if (this._warmUpPending && event.data === 1) { // YT.PlayerState.PLAYING
            const isActive = (deck === this.activeDeck);
            if (!isActive) {
                this.getInactiveDeck().pauseVideo();
                this._warmUpPending = false;
            }
        }

        // YT.PlayerState.ENDED = 0
        if (event.data === 0 && !this.isFading) {
            const isActive = (deck === this.activeDeck);
            if (isActive) {
                this.onTrackChange();
            }
        }
    }
```

**Step 4: Add `_warmUpPending` init in constructor (after line 13)**

```javascript
        this._warmUpPending = false;
```

**Step 5: Verify — run existing tests**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/ -x -q`
Expected: All 111 tests pass (no backend changes)

**Step 6: Commit**

```bash
git add static/js/mix-engine.js
git commit -m "feat: add playsinline, pause/resume, warmUpDecks to mix engine"
```

---

## Task 2: index.html — player bar HTML + cache bump

**Files:**
- Modify: `static/index.html`

**Step 1: Add player bar HTML before the closing `</body>` tag (before line 89)**

Insert after `</div>` (end of settings overlay, line 87) and before `</body>`:

```html
    <div class="player-bar" id="playerBar">
        <div class="player-bar-inner">
            <img class="player-thumb" id="playerThumb" src="" alt="">
            <div class="player-info">
                <div class="player-title" id="playerTitle"></div>
                <div class="player-meta" id="playerMeta"></div>
            </div>
            <div class="player-controls">
                <button class="player-btn prev-btn" id="prevBtn" style="display:none">⏮</button>
                <button class="player-btn play-btn" id="playBtn">▶</button>
                <button class="player-btn next-btn" id="nextBtn">⏭</button>
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

**Step 2: Bump cache version on CSS and JS links**

Change lines 8, 44, 45 from `?v=8` to `?v=9`:

```html
    <link rel="stylesheet" href="/static/css/style.css?v=9">
    ...
    <script src="/static/js/mix-engine.js?v=9"></script>
    <script src="/static/js/app.js?v=9"></script>
```

**Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: add player bar HTML structure, bump cache to v9"
```

---

## Task 3: style.css — player bar styles

**Files:**
- Modify: `static/css/style.css`

**Step 1: Add container bottom padding (modify `.container` rule at line 14)**

Add to the existing `.container` rule:

```css
.container {
    max-width: 700px;
    width: 100%;
    padding: 2rem 1rem 7rem; /* added bottom padding for player bar */
}
```

**Step 2: Add player bar styles at end of file (after line 417)**

```css
/* Player Bar */
.player-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #14141f;
    border-top: 1px solid #333;
    z-index: 50;
    padding: 0.5rem 1rem;
    padding-bottom: calc(0.5rem + env(safe-area-inset-bottom, 0px));
    display: none;
    flex-direction: column;
    gap: 0.4rem;
}

.player-bar.active { display: flex; }

.player-bar-inner {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.player-thumb {
    width: 48px;
    height: 48px;
    border-radius: 6px;
    object-fit: cover;
    background: #1e1e2e;
    flex-shrink: 0;
}

.player-info {
    flex: 1;
    min-width: 0;
}

.player-title {
    font-size: 0.9rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.player-meta {
    color: #666;
    font-size: 0.75rem;
    margin-top: 0.15rem;
}

.player-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
}

.player-btn {
    background: none;
    border: none;
    color: #e0e0e0;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0.4rem;
    border-radius: 50%;
    transition: background 0.2s;
    min-width: 40px;
    min-height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.player-btn:hover { background: rgba(255,255,255,0.1); }
.player-btn:active { background: rgba(255,255,255,0.15); }

.play-btn {
    font-size: 1.5rem;
    background: linear-gradient(135deg, #667eea, #764ba2);
    min-width: 48px;
    min-height: 48px;
}

.play-btn:hover { opacity: 0.9; background: linear-gradient(135deg, #667eea, #764ba2); }

/* Ready state — pulsing play button */
.player-bar.ready .play-btn {
    animation: pulse-play 2s ease-in-out infinite;
}

@keyframes pulse-play {
    0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(102, 126, 234, 0.4); }
    50% { transform: scale(1.08); box-shadow: 0 0 16px 4px rgba(102, 126, 234, 0.3); }
}

/* Progress row */
.player-progress-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.player-time {
    font-size: 0.65rem;
    color: #666;
    font-variant-numeric: tabular-nums;
    min-width: 2.5rem;
}

.player-time:last-child { text-align: right; }

.player-progress {
    flex: 1;
    height: 3px;
    background: #333;
    border-radius: 2px;
    position: relative;
    overflow: hidden;
}

.player-progress-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, #667eea, #764ba2);
    border-radius: 2px;
    transition: width 0.5s linear;
}

.player-crossfade-zone {
    position: absolute;
    top: 0;
    height: 100%;
    background: rgba(118, 75, 162, 0.3);
    border-radius: 2px;
    display: none;
}

.player-crossfade-zone.active {
    animation: pulse-fade 1s ease-in-out infinite;
}

@keyframes pulse-fade {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 0.7; }
}

/* Mobile adjustments for player bar */
@media (max-width: 480px) {
    .player-bar { padding: 0.4rem 0.75rem; padding-bottom: calc(0.4rem + env(safe-area-inset-bottom, 0px)); }
    .player-thumb { width: 40px; height: 40px; }
    .player-title { font-size: 0.8rem; }
    .play-btn { min-width: 44px; min-height: 44px; font-size: 1.3rem; }
    .player-btn { min-width: 36px; min-height: 36px; font-size: 1rem; }
}
```

**Step 3: Update the mobile `.container` padding too (in the `@media (max-width: 480px)` block)**

Change `.container` padding in the mobile media query (around line 168):

```css
    .container {
        padding: 1.25rem 0.75rem 7rem;
    }
```

**Step 4: Commit**

```bash
git add static/css/style.css
git commit -m "feat: add player bar styles with crossfade indicator and iOS pulse"
```

---

## Task 4: app.js — deferred playback, player controls, progress bar

**Files:**
- Modify: `static/js/app.js`

This is the largest task. Changes are:
1. Add player bar element refs
2. Add `playerState` tracking
3. Bind player bar button events
4. Modify `startPlaying()` to defer
5. Add `onPlayTap()`, `onSkipTap()`, `showPlayerBar()`, `updatePlayerInfo()`
6. Update `startPositionMonitor()` for progress bar + crossfade zone
7. Add `formatTime()` helper
8. Update `onTrackEnded()` to update player info

**Step 1: Add player bar element refs in constructor (extend `this.els` object, after line 30)**

Add these lines inside the `this.els` object:

```javascript
            playerBar: document.getElementById('playerBar'),
            playerThumb: document.getElementById('playerThumb'),
            playerTitle: document.getElementById('playerTitle'),
            playerMeta: document.getElementById('playerMeta'),
            playBtn: document.getElementById('playBtn'),
            nextBtn: document.getElementById('nextBtn'),
            playerElapsed: document.getElementById('playerElapsed'),
            playerRemaining: document.getElementById('playerRemaining'),
            progressFill: document.getElementById('playerProgressFill'),
            crossfadeZone: document.getElementById('playerCrossfadeZone'),
```

**Step 2: Add `playerState` in constructor (after `this.positionTimer`, around line 12)**

```javascript
        this.playerState = 'hidden';
```

**Step 3: Add player button event listeners in `bindEvents()` (after line 49)**

```javascript
        this.els.playBtn.addEventListener('click', () => this.onPlayTap());
        this.els.nextBtn.addEventListener('click', () => this.onSkipTap());
```

**Step 4: Replace `startPlaying()` method (lines 212-226)**

```javascript
    startPlaying() {
        this.hideStatus();
        this.els.goBtn.disabled = false;
        this.updateNowPlaying();
        this.updateQueue();
        this.showPlayerBar('ready');
    }
```

**Step 5: Add new methods after `startPlaying()` — `showPlayerBar`, `updatePlayerInfo`, `onPlayTap`, `onSkipTap`, `formatTime`**

```javascript
    showPlayerBar(state) {
        this.playerState = state;
        const bar = this.els.playerBar;
        const playBtn = this.els.playBtn;

        if (state === 'hidden') {
            bar.classList.remove('active', 'ready');
            return;
        }

        bar.classList.add('active');
        bar.classList.toggle('ready', state === 'ready');

        if (state === 'ready') {
            playBtn.textContent = '▶';
            this.els.playerTitle.textContent = 'Tap play to start';
            this.els.playerMeta.textContent = '';
            // Show thumbnail of first track
            const track = this.queue[this.currentIndex];
            if (track) {
                this.els.playerThumb.src = `https://img.youtube.com/vi/${track.video_id}/mqdefault.jpg`;
            }
        } else if (state === 'playing') {
            playBtn.textContent = '⏸';
            this.updatePlayerInfo();
        } else if (state === 'paused') {
            playBtn.textContent = '▶';
        }
    }

    updatePlayerInfo() {
        const track = this.queue[this.currentIndex];
        if (!track) return;
        this.els.playerTitle.textContent = track.title;
        this.els.playerMeta.textContent = `${track.bpm} BPM · ${track.camelot}`;
        this.els.playerThumb.src = `https://img.youtube.com/vi/${track.video_id}/mqdefault.jpg`;
    }

    onPlayTap() {
        if (this.playerState === 'ready') {
            // First play — fresh user gesture for iOS
            const track = this.queue[this.currentIndex];
            this.engine.warmUpDecks(track.video_id, track.mix_in_point);
            this.requestMixCommand();
            this.startPositionMonitor();
            this.showPlayerBar('playing');
        } else if (this.playerState === 'paused') {
            this.engine.resume();
            this.showPlayerBar('playing');
        } else if (this.playerState === 'playing') {
            this.engine.pause();
            this.showPlayerBar('paused');
        }
    }

    onSkipTap() {
        if (this.playerState === 'ready') return;
        if (this.engine.isFading) return;

        if (this.mixCommand) {
            this.engine.crossfadeTo(
                this.mixCommand.next_video_id,
                this.mixCommand.next_seek_to,
                this.mixCommand.fade_duration,
            );
            this.mixCommand = null;
        } else {
            // No mix command yet — tell backend to advance
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ action: 'track_ended' }));
            }
        }
    }

    formatTime(seconds) {
        if (!seconds || seconds < 0) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
```

**Step 6: Replace `startPositionMonitor()` method (lines 234-251)**

```javascript
    startPositionMonitor() {
        if (this.positionTimer) clearInterval(this.positionTimer);

        this.positionTimer = setInterval(() => {
            if (this.playerState !== 'playing') return;

            const currentTime = this.engine.getCurrentTime();
            const duration = this.engine.getDuration();

            // Update progress bar
            if (duration > 0) {
                const pct = (currentTime / duration) * 100;
                this.els.progressFill.style.width = `${pct}%`;
                this.els.playerElapsed.textContent = this.formatTime(currentTime);
                this.els.playerRemaining.textContent = `-${this.formatTime(duration - currentTime)}`;
            }

            // Show crossfade zone when mix command is known
            if (this.mixCommand && duration > 0) {
                const fadeStartPct = (this.mixCommand.current_fade_start / duration) * 100;
                this.els.crossfadeZone.style.left = `${fadeStartPct}%`;
                this.els.crossfadeZone.style.width = `${100 - fadeStartPct}%`;
                this.els.crossfadeZone.style.display = 'block';
            }

            // Trigger crossfade at mix point
            if (this.mixCommand && !this.engine.isFading) {
                if (currentTime >= this.mixCommand.current_fade_start) {
                    this.engine.crossfadeTo(
                        this.mixCommand.next_video_id,
                        this.mixCommand.next_seek_to,
                        this.mixCommand.fade_duration,
                    );
                    this.mixCommand = null;
                }
            }

            // Update crossfade zone pulse
            this.els.crossfadeZone.classList.toggle('active', this.engine.isFading);
        }, 500);
    }
```

**Step 7: Update `onTrackEnded()` to refresh player info (lines 253-259)**

```javascript
    onTrackEnded() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'track_ended' }));
            this.requestMixCommand();
        }
        // Reset crossfade zone and progress for next track
        this.els.crossfadeZone.style.display = 'none';
        this.els.crossfadeZone.classList.remove('active');
        this.els.progressFill.style.width = '0%';
    }
```

**Step 8: Update `refreshQueue()` to also update player info (line 149-150)**

After the existing `this.updateNowPlaying()` and `this.updateQueue()` calls, add:

```javascript
        if (this.playerState === 'playing') {
            this.updatePlayerInfo();
        }
```

**Step 9: Verify — run existing tests**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/ -x -q`
Expected: All 111 tests pass (no backend changes)

**Step 10: Commit**

```bash
git add static/js/app.js
git commit -m "feat: add player bar controls, deferred playback for iOS, progress bar"
```

---

## Task 5: Manual verification + deploy

**Step 1: Start local server**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m djwala`

**Step 2: Browser verification checklist**

Open `http://localhost:8000` in browser and verify:

- [ ] Page loads — no console errors
- [ ] Player bar is hidden initially
- [ ] Enter artists, click "DJ!" — player bar appears in "ready" state with pulsing ▶
- [ ] Thumbnail shows for first track
- [ ] Click ▶ — music plays, button changes to ⏸
- [ ] Progress bar fills over time
- [ ] Elapsed and remaining time update
- [ ] Click ⏸ — music pauses, button changes to ▶
- [ ] Click ▶ again — music resumes
- [ ] Crossfade zone appears on progress bar when mix command arrives
- [ ] Crossfade zone pulses during active crossfade
- [ ] After crossfade, new track info + thumbnail update
- [ ] Click ⏭ — triggers early crossfade (if mix command available)
- [ ] Queue scrolls without player bar blocking content
- [ ] Mobile: player bar fits well, buttons are tappable (44px+ touch targets)

**Step 3: Deploy**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && fly deploy`

**Step 4: Production verification**

Open `https://djwala-ai.fly.dev` and run the same checklist above.

**Step 5: iOS testing (if device available)**

- [ ] Open on iPhone Safari
- [ ] Enter artists, tap "DJ!" — player bar appears
- [ ] Tap ▶ — music plays (this is the iOS fix!)
- [ ] Crossfade works (both decks play)

---

## Dependency Graph

```
Task 1 (mix-engine.js) ─┐
Task 2 (index.html)  ───┼──→ Task 4 (app.js) ──→ Task 5 (test + deploy)
Task 3 (style.css)   ───┘
```

Tasks 1, 2, 3 are independent and can be done in parallel.
Task 4 depends on all three.
Task 5 depends on Task 4.
