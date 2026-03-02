# Phase B: Visual Mix Timeline + Party Mode — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a visual mix timeline showing tracks as colored blocks with BPM/key labels and crossfade zones, plus a fullscreen "Party Mode" optimized for TV casting.

**Architecture:** Pure frontend — no backend changes. The timeline renders from the existing `this.queue` array (each track has `title`, `bpm`, `camelot`, `duration`, `mix_in_point`, `mix_out_point`, `energy`, `video_id`). Party Mode is a CSS class toggle on `<body>` that hides the input section and shows a fullscreen view with large album art.

**Tech Stack:** Vanilla JS, CSS, HTML — no build tools, no dependencies.

---

### Task 1: Mix Timeline HTML + CSS

**Files:**
- Modify: `static/index.html` — add timeline container between now-playing and queue
- Modify: `static/css/style.css` — add timeline styles

**Step 1: Add timeline HTML**

In `static/index.html`, after the `<div class="now-playing">...</div>` block and before `<div class="queue">`, add:

```html
<div class="mix-timeline" id="mixTimeline">
    <div class="timeline-tracks" id="timelineTracks"></div>
    <div class="timeline-playhead" id="timelinePlayhead"></div>
</div>
```

**Step 2: Add timeline CSS**

In `static/css/style.css`, add after the `.now-playing` section:

```css
/* Mix Timeline */
.mix-timeline {
    position: relative;
    background: #14141f;
    border-radius: 12px;
    padding: 1rem;
    margin-bottom: 1rem;
    display: none;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
}

.mix-timeline.active { display: block; }

.timeline-tracks {
    display: flex;
    align-items: stretch;
    min-height: 72px;
    gap: 0;
    position: relative;
}

.timeline-track {
    position: relative;
    min-width: 100px;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    cursor: default;
    transition: opacity 0.3s;
    overflow: hidden;
}

.timeline-track.past { opacity: 0.35; }
.timeline-track.current { box-shadow: 0 0 0 2px #667eea; }

.timeline-track-title {
    font-size: 0.75rem;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 0.25rem;
}

.timeline-track-meta {
    font-size: 0.65rem;
    color: rgba(255,255,255,0.6);
    white-space: nowrap;
}

.timeline-crossfade {
    position: absolute;
    right: 0;
    top: 0;
    bottom: 0;
    background: rgba(0,0,0,0.3);
    border-left: 1px dashed rgba(255,255,255,0.2);
}

.timeline-playhead {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #fff;
    border-radius: 1px;
    z-index: 2;
    pointer-events: none;
    transition: left 0.5s linear;
    display: none;
}

.timeline-playhead.active { display: block; }

@media (max-width: 480px) {
    .timeline-track { min-width: 80px; padding: 0.4rem 0.5rem; }
    .timeline-track-title { font-size: 0.7rem; }
    .timeline-track-meta { font-size: 0.6rem; }
}
```

**Step 3: Bump cache busters**

Update `?v=11` to `?v=12` on all three asset references in `index.html`.

**Step 4: Commit**

```bash
git add static/index.html static/css/style.css
git commit -m "feat(B1): add mix timeline HTML + CSS skeleton"
```

---

### Task 2: Timeline Rendering Logic

**Files:**
- Modify: `static/js/app.js` — add `renderTimeline()` and `updateTimelinePlayhead()` methods

**Step 1: Add timeline element refs in constructor**

In the `this.els` object, add:
```js
mixTimeline: document.getElementById('mixTimeline'),
timelineTracks: document.getElementById('timelineTracks'),
timelinePlayhead: document.getElementById('timelinePlayhead'),
```

**Step 2: Add `renderTimeline()` method**

After `updateQueue()`, add:

```js
renderTimeline() {
    const container = this.els.timelineTracks;
    container.innerHTML = '';
    this.els.mixTimeline.classList.add('active');

    // Color palette for tracks (cycles)
    const colors = [
        'rgba(102,126,234,0.35)', // blue
        'rgba(118,75,162,0.35)',   // purple
        'rgba(74,222,128,0.35)',   // green
        'rgba(251,191,36,0.35)',   // amber
        'rgba(244,114,182,0.35)', // pink
        'rgba(56,189,248,0.35)',  // sky
    ];

    // Calculate total duration for proportional widths
    const totalDuration = this.queue.reduce((sum, t) => sum + (t.duration || 180), 0);

    this.queue.forEach((track, i) => {
        const dur = track.duration || 180;
        const widthPct = (dur / totalDuration) * 100;

        const el = document.createElement('div');
        el.className = 'timeline-track';
        if (i < this.currentIndex) el.classList.add('past');
        if (i === this.currentIndex) el.classList.add('current');
        el.style.width = `${widthPct}%`;
        el.style.minWidth = '80px';
        el.style.background = colors[i % colors.length];

        const titleEl = document.createElement('div');
        titleEl.className = 'timeline-track-title';
        titleEl.textContent = track.title;

        const metaEl = document.createElement('div');
        metaEl.className = 'timeline-track-meta';
        metaEl.textContent = `${track.bpm} BPM · ${track.camelot}`;

        el.appendChild(titleEl);
        el.appendChild(metaEl);

        // Add crossfade zone indicator
        if (track.mix_out_point && track.duration) {
            const fadeStart = track.mix_out_point;
            const fadePct = ((track.duration - fadeStart) / track.duration) * 100;
            if (fadePct > 0 && fadePct < 50) {
                const fadeEl = document.createElement('div');
                fadeEl.className = 'timeline-crossfade';
                fadeEl.style.width = `${fadePct}%`;
                el.appendChild(fadeEl);
            }
        }

        container.appendChild(el);
    });
}
```

**Step 3: Call `renderTimeline()` from existing rendering points**

In `startPlaying()`, after `this.updateQueue()`, add:
```js
this.renderTimeline();
```

In `refreshQueue()`, after `this.updateQueue()`, add:
```js
this.renderTimeline();
```

**Step 4: Add playhead updates in `startPositionMonitor()`**

Inside the existing `setInterval` callback in `startPositionMonitor()`, after the progress bar update block, add:

```js
// Update timeline playhead
this.updateTimelinePlayhead(currentTime, duration);
```

**Step 5: Add `updateTimelinePlayhead()` method**

```js
updateTimelinePlayhead(currentTime, duration) {
    const playhead = this.els.timelinePlayhead;
    const container = this.els.timelineTracks;
    if (!container.children.length) return;

    // Calculate position: sum of past tracks + current progress within current track
    let accWidth = 0;
    for (let i = 0; i < this.currentIndex; i++) {
        accWidth += container.children[i].offsetWidth;
    }

    const currentTrackEl = container.children[this.currentIndex];
    if (currentTrackEl && duration > 0) {
        const progress = Math.min(currentTime / duration, 1);
        accWidth += currentTrackEl.offsetWidth * progress;
    }

    playhead.style.left = `${accWidth}px`;
    playhead.classList.add('active');

    // Auto-scroll to keep playhead visible
    const timeline = this.els.mixTimeline;
    const scrollLeft = timeline.scrollLeft;
    const viewWidth = timeline.clientWidth;
    if (accWidth > scrollLeft + viewWidth - 40 || accWidth < scrollLeft) {
        timeline.scrollLeft = accWidth - viewWidth / 3;
    }
}
```

**Step 6: Reset playhead on track end**

In `onTrackEnded()`, add:
```js
this.els.timelinePlayhead.classList.remove('active');
```

**Step 7: Commit**

```bash
git add static/js/app.js
git commit -m "feat(B1): render mix timeline with tracks, crossfade zones, playhead"
```

---

### Task 3: Party Mode — HTML + CSS + Toggle

**Files:**
- Modify: `static/index.html` — add party mode button + party overlay
- Modify: `static/css/style.css` — party mode fullscreen styles
- Modify: `static/js/app.js` — toggle logic + party URL param

**Step 1: Add party mode button in the player bar controls**

In `static/index.html`, inside `.player-controls`, after the next button, add:

```html
<button class="player-btn party-btn" id="partyBtn" title="Party Mode">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
</button>
```

**Step 2: Add party overlay HTML**

Before the closing `</body>`, add:

```html
<div class="party-overlay" id="partyOverlay">
    <div class="party-content">
        <img class="party-art" id="partyArt" src="" alt="">
        <div class="party-title" id="partyTitle"></div>
        <div class="party-meta" id="partyMeta"></div>
        <div class="party-next" id="partyNext"></div>
    </div>
    <button class="party-exit" id="partyExit" title="Exit Party Mode">✕</button>
    <div class="party-timeline" id="partyTimeline">
        <div class="party-progress-fill" id="partyProgressFill"></div>
    </div>
</div>
```

**Step 3: Add party mode CSS**

```css
/* Party Mode */
.party-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: #000;
    z-index: 200;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    cursor: none;
}

.party-overlay.active {
    display: flex;
    animation: partyFadeIn 0.5s ease;
}

@keyframes partyFadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.party-overlay.active .party-content {
    animation: partySlideUp 0.6s ease;
}

@keyframes partySlideUp {
    from { opacity: 0; transform: translateY(30px); }
    to { opacity: 1; transform: translateY(0); }
}

.party-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    max-width: 80vw;
}

.party-art {
    width: min(480px, 60vw);
    height: min(480px, 60vw);
    border-radius: 12px;
    object-fit: cover;
    box-shadow: 0 20px 60px rgba(102,126,234,0.3);
}

.party-title {
    font-size: clamp(1.5rem, 4vw, 3rem);
    font-weight: 700;
    color: #fff;
    max-width: 80vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.party-meta {
    font-size: clamp(1rem, 2vw, 1.5rem);
    color: rgba(255,255,255,0.5);
}

.party-next {
    font-size: clamp(0.85rem, 1.5vw, 1.1rem);
    color: rgba(255,255,255,0.3);
}

.party-exit {
    position: fixed;
    top: 1.5rem;
    right: 1.5rem;
    background: rgba(255,255,255,0.1);
    border: none;
    border-radius: 50%;
    width: 48px;
    height: 48px;
    color: rgba(255,255,255,0.5);
    font-size: 1.5rem;
    cursor: pointer;
    transition: all 0.2s;
    opacity: 0;
    z-index: 201;
}

.party-overlay:hover .party-exit,
.party-overlay.show-controls .party-exit { opacity: 1; }

.party-exit:hover { background: rgba(255,255,255,0.2); color: #fff; }

.party-timeline {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: rgba(255,255,255,0.1);
}

.party-progress-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, #667eea, #764ba2);
    transition: width 0.5s linear;
}

/* Show cursor on mouse move */
.party-overlay.show-controls { cursor: default; }
```

**Step 4: Add party mode JS — element refs**

In constructor `this.els`, add:
```js
partyBtn: document.getElementById('partyBtn'),
partyOverlay: document.getElementById('partyOverlay'),
partyArt: document.getElementById('partyArt'),
partyTitle: document.getElementById('partyTitle'),
partyMeta: document.getElementById('partyMeta'),
partyNext: document.getElementById('partyNext'),
partyExit: document.getElementById('partyExit'),
partyProgressFill: document.getElementById('partyProgressFill'),
```

**Step 5: Bind party events in `bindEvents()`**

```js
this.els.partyBtn.addEventListener('click', () => this.togglePartyMode());
this.els.partyExit.addEventListener('click', () => this.togglePartyMode());
```

**Step 6: Add party mode methods**

```js
togglePartyMode() {
    this.partyMode = !this.partyMode;
    this.els.partyOverlay.classList.toggle('active', this.partyMode);

    if (this.partyMode) {
        this.updatePartyView();
        // Hide cursor after inactivity
        this._partyMouseTimer = null;
        this.els.partyOverlay.addEventListener('mousemove', this._partyMouseHandler = () => {
            this.els.partyOverlay.classList.add('show-controls');
            clearTimeout(this._partyMouseTimer);
            this._partyMouseTimer = setTimeout(() => {
                this.els.partyOverlay.classList.remove('show-controls');
            }, 3000);
        });
        // ESC to exit
        this._partyEscHandler = (e) => { if (e.key === 'Escape') this.togglePartyMode(); };
        document.addEventListener('keydown', this._partyEscHandler);
    } else {
        this.els.partyOverlay.removeEventListener('mousemove', this._partyMouseHandler);
        document.removeEventListener('keydown', this._partyEscHandler);
    }
}

updatePartyView() {
    if (!this.partyMode) return;
    const track = this.queue[this.currentIndex];
    if (!track) return;

    this.els.partyArt.src = `https://img.youtube.com/vi/${track.video_id}/maxresdefault.jpg`;
    this.els.partyArt.onerror = () => {
        this.els.partyArt.src = `https://img.youtube.com/vi/${track.video_id}/hqdefault.jpg`;
    };
    this.els.partyTitle.textContent = track.title;
    this.els.partyMeta.textContent = `${track.bpm} BPM · ${track.camelot}`;

    const next = this.queue[this.currentIndex + 1];
    this.els.partyNext.textContent = next ? `Next: ${next.title}` : '';
}
```

**Step 7: Update party view in position monitor**

In `startPositionMonitor()` interval, add after timeline playhead update:
```js
// Update party mode progress
if (this.partyMode && duration > 0) {
    const pct = (currentTime / duration) * 100;
    this.els.partyProgressFill.style.width = `${pct}%`;
}
```

**Step 8: Update party view on track change**

In `refreshQueue()`, after `this.renderTimeline()`, add:
```js
this.updatePartyView();
```

In `onTrackEnded()`, add:
```js
this.els.partyProgressFill.style.width = '0%';
```

**Step 9: Commit**

```bash
git add static/index.html static/css/style.css static/js/app.js
git commit -m "feat(B2): add Party Mode — fullscreen view with album art for TV casting"
```

---

### Task 4: Final Integration + Tests

**Step 1: Bump cache busters to v=12**

**Step 2: Run existing tests**

```bash
.venv/bin/python -m pytest tests/ -v --tb=short
```

Expected: 129 passed (no backend changes, so all existing tests still pass).

**Step 3: Manual verification**

- Load https://djwala-ai.fly.dev
- Start a mix
- Verify timeline renders with colored track blocks
- Verify playhead moves
- Verify crossfade zones appear on tracks
- Click party mode button → fullscreen
- Verify album art, title, BPM/key
- Move mouse → controls appear
- Press ESC → exits
- Verify progress bar at bottom

**Step 4: Deploy**

```bash
fly deploy
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(B): Phase B complete — visual mix timeline + party mode"
```
