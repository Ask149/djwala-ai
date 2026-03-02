# DJ Deck UI — Design Doc

**Date:** 2026-03-02  
**Status:** Approved  
**Goal:** Make the mixing visible — attract users via screenshots, first-visit conversion, and party mode wow factor

---

## Problem

DjwalaAI does impressive things (BPM matching, harmonic mixing, cosine crossfades) but the UI doesn't show any of it. The interface looks like a text-based search tool. DJing is visual — turntables, waveforms, lights, energy. The magic is invisible.

## Solution: The Waveform DJ Deck

When a mix is playing, the center of the screen becomes a visual DJ deck — two waveform bars (outgoing + incoming track), album art for both tracks, a crossfader indicator, and a dynamic color background extracted from album art.

## Design Approach

**Primary:** Approach A — Waveform DJ Deck (visual dual-deck with simulated waveforms)  
**Secondary:** Elements of Approach B — Album Art Theater (dynamic color extraction from thumbnails)

---

## Section 1: DJ Deck Layout

### Before Mix (Landing State)

No changes. Input, mood pills, how-it-works stay as-is. The DJ deck only appears when music plays.

### During Mix: The DJ Deck

Replaces the current "Now Playing" text box. Appears between input section and queue.

```
┌─────────────────────────────────────────────┐
│                  DJ DECK                     │
│                                              │
│  ┌─────────┐                   ┌─────────┐  │
│  │ Album   │   ◄── crossfade   │ Album   │  │
│  │ Art A   │       indicator   │ Art B   │  │
│  │ (out)   │        ──●──      │ (in)    │  │
│  └─────────┘                   └─────────┘  │
│                                              │
│  ▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁  ▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁    │
│  ← outgoing waveform  incoming waveform →    │
│                                              │
│  "Blinding Lights"      "Save Your Tears"    │
│   128 BPM · 4B           120 BPM · 5A        │
│                                              │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░ crossfade progress      │
└─────────────────────────────────────────────┘
```

### Key Elements

| Element | What | Why |
|---------|------|-----|
| Two album arts | YouTube thumbnails for outgoing + incoming | Visual anchor — eyes go to images first |
| Simulated waveforms | Procedurally generated bars seeded from BPM/energy | "DJ credibility" signal — makes screenshots look pro |
| Crossfader indicator | Animated dot sliding left→right during crossfade | Shows the mix happening in real-time |
| Track labels | Title + BPM + Camelot key for both tracks | Communicates technical depth |
| Crossfade progress bar | Fills during the transition zone | Builds anticipation |

### Visual States

1. **Single track playing** — Only left deck active, right deck shows "Next up" dimmed
2. **Crossfade in progress** — Both decks active, waveforms overlap, crossfader animates
3. **Transition complete** — New track slides to left, next queued track appears dimmed on right

### Waveform Generation (Simulated)

No Web Audio access (YouTube IFrame API). Waveforms are procedurally generated from track metadata:

- **BPM** → bar spacing/rhythm
- **Energy** → bar height range
- **video_id hash** → seeded random for bar heights (deterministic per track)
- Animated playhead glow sweeps across at real playback speed
- Bar heights pulse ±5% at BPM interval (60/BPM seconds per beat)

---

## Section 2: Dynamic Background & Color Theming

### Album Art Color Extraction

Extract dominant color from YouTube thumbnail → tint the page.

**Method:**
1. Load thumbnail into hidden canvas (10×10px for dominant color cluster)
2. Find most saturated color cluster
3. Cache per video_id
4. Fallback: current purple gradient (#667eea → #764ba2)

### Background States

```
IDLE (no mix):       solid #0a0a0f (current)
PLAYING:             radial-gradient(ellipse at center, rgba(dominant_color, 0.12) 0%, #0a0a0f 70%)
CROSSFADING:         crossfade between outgoing color → incoming color (3-5s transition)
```

### Additional Color Touches

| Element | Effect |
|---------|--------|
| Album art shadow | box-shadow uses dominant color — art "glows" |
| Waveform bars | Tinted with dominant color |
| Player bar | Thin top border picks up dominant color |
| Mood pills (when active) | Background tint matches mood vibe color |

### CORS Note

YouTube thumbnails don't set CORS headers. Need a backend proxy:
- Add `/api/thumb?v={video_id}` — fetches thumbnail and returns image (~10 lines backend)
- Alternative: fallback palette mapping energy/mood to predefined colors (zero backend)

---

## Section 3: Party Mode — The TV Showpiece

### Party Mode Layout (Fullscreen)

```
┌──────────────────────────────────────────────────────┐
│              (dynamic color glow fills screen)       │
│                                                      │
│          ┌──────────┐      ┌──────────┐              │
│          │ Album A  │      │ Album B  │              │
│          │  (large) │      │ (large)  │              │
│          └──────────┘      └──────────┘              │
│                                                      │
│    ▁▂▃▅▇█▇▅▃▂▁▂▃▅▇█▇▅▃▂▁▂▃▅▇█▇▅▃▂▁▂▃▅▇█▇▅▃▂▁     │
│              (waveforms span full width)              │
│                                                      │
│              "Blinding Lights"                        │
│            128 BPM · Camelot 4B                       │
│                                                      │
│         "I said ooh, I'm blinding"                    │
│              (synced lyrics)                          │
│                                                      │
│   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░     │
└──────────────────────────────────────────────────────┘
```

### Normal → Party Mode Differences

| Element | Normal Mode | Party Mode |
|---------|------------|------------|
| Album art | ~80px thumbnails | ~30vh |
| Waveforms | Contained in deck card | Full-width, 64px height |
| Background | Subtle radial glow | Full-screen color wash, deeper saturation |
| Track info | Small labels | Large centered text (clamp 1.5rem–3rem) |
| Lyrics | Side panel | Centered below track info |
| Crossfader | Small knob indicator | Hidden (visual clutter on TV) |
| Queue/input | Visible | Hidden (fullscreen takeover) |

### Crossfade Transition (The "Record Your Screen" Moment)

1. **Pre-crossfade:** Single album art centered, waveform pulsing
2. **Crossfade begins:** Second album art slides in from right
3. **Mid-crossfade:** Waveforms merge in center, background color blends
4. **Crossfade complete:** Old art fades out left, new art centers

### Idle Animation

- Waveform bars pulse gently to estimated BPM
- Album art: slow scale(1.0 → 1.02) breathing animation
- Background glow subtly pulses

---

## Section 4: Mobile Responsiveness

### Mobile DJ Deck (< 480px)

```
┌───────────────────────┐
│  ┌────┐       ┌────┐  │
│  │Art │  ●──  │Art │  │
│  │ A  │       │ B  │  │
│  └────┘       └────┘  │
│  Blinding..  Save Your │
│  128·4B      120·5A    │
│  ▁▃▅▇▅▃▁▁▃▅▇▅▃▂▁▂▃▅  │
│  ▓▓▓▓▓▓▓▓░░░░░░░░░░  │
└───────────────────────┘
```

| Element | Desktop | Mobile |
|---------|---------|--------|
| Album art | 80×80px | 56×56px |
| Waveform height | 48px | 32px |
| Track labels | Full title + BPM + key | Truncated + combined line |
| Crossfader | Knob indicator | Thin animated line |
| Deck padding | 1.5rem | 0.75rem |

### Mobile Party Mode

- **Single album art** (not side-by-side — not enough width)
- Crossfade: outgoing art fades/shrinks, incoming fades in (overlay transition)
- Waveform: full-width, 40px height
- Lyrics: 2 lines max visible
- Exit button: always slightly visible (no hover on touch)

### Breakpoints

```
> 768px     Desktop — full side-by-side deck
481-768px   Tablet — same layout, slightly compressed
≤ 480px     Mobile — compact deck, overlay transitions in party mode
```

---

## Section 5: Implementation Scope

### New Components

| Component | Technology | Lines (est.) |
|-----------|-----------|-------------|
| DJ Deck HTML | HTML | ~60 |
| DJ Deck CSS + responsive | CSS | ~230 |
| Waveform renderer | Canvas API | ~120 JS |
| Color extraction | Hidden canvas sampling | ~40 JS |
| Crossfader animation | CSS transitions + JS | ~60 JS |
| Party mode deck view | CSS | ~80 |
| Thumbnail proxy (backend) | FastAPI endpoint | ~10 Python |

**Total:** ~370 CSS, ~220 JS, ~60 HTML, ~10 Python

### Integration Points

| Existing Event | New Behavior |
|---------------|-------------|
| onTrackStart(track) | Show deck, load art, generate waveform, extract color, set background |
| onCrossfadeBegin(out, in) | Activate right deck, start crossfader, begin color blend |
| onCrossfadeEnd() | Shift incoming to left deck, dim right to "next up" |
| togglePartyMode() | Scale deck to fullscreen layout, enlarge waveforms |
| positionMonitor (500ms) | Update waveform playhead, crossfade progress |

### What Does NOT Change

- Backend logic — zero changes
- Mix engine — zero changes
- Queue/input UI — stays the same
- Lyrics system — repositioned in party mode only
- Keyboard shortcuts — unchanged
- Existing 140 tests — unaffected

### Priority Order

| Priority | Feature | Impact |
|----------|---------|--------|
| P0 | DJ Deck card (album arts + track info + crossfade indicator) | Core visual identity |
| P0 | Simulated waveforms (Canvas, BPM-synced pulse) | Screenshot moment |
| P1 | Dynamic background color from thumbnails | Premium feel |
| P1 | Party mode deck (fullscreen waveforms + large art) | TV showpiece |
| P2 | Mobile deck layout | Group chat conversions |
| P2 | Crossfade transition animations | "Record your screen" moment |

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Simulated waveforms over real | No Web Audio access via YouTube IFrame API |
| Procedural generation seeded from track data | Deterministic per track, looks convincing |
| Backend thumbnail proxy over fallback palette | Cleaner, enables true color extraction |
| No new JS framework | Existing vanilla JS works fine for this scope |
| Party mode: hide crossfader knob | Visual clutter on TV at a distance |
| Mobile: overlay transitions not side-by-side | Not enough screen width for dual art |
