# DjwalaAI — Design Document

**Date:** 2026-02-27  
**Status:** Approved

## Overview

AI-powered auto-DJ web app that builds playlists from YouTube, analyzes tracks via audio analysis, and mixes them seamlessly using two YouTube IFrame players with intelligent crossfading — all on the fly.

## Input Modes

1. **Seed Song** — User provides a YouTube URL. System parses artist/genre from title, searches YouTube for similar tracks.
2. **Vibe Search** — User describes a vibe (e.g., "deep house chill 120bpm"). System searches YouTube, curates a queue.
3. **Artist Mix** — User provides artist names (e.g., "Rufus Du Sol, Bob Moses"). System finds their tracks on YouTube, interleaves them.

Discovery is YouTube-only — no external music APIs.

## Architecture

```
┌──────────────── Frontend (Browser) ─────────────────┐
│                                                      │
│   ┌──────────┐          ┌──────────┐                │
│   │  Deck A  │          │  Deck B  │  ← YT IFrame  │
│   │ (IFrame) │          │ (IFrame) │     Players    │
│   └────┬─────┘          └────┬─────┘                │
│        └──────┬──────────────┘                      │
│         ┌─────┴──────┐                              │
│         │ Mix Engine │ ← volume curves, timing      │
│         └─────┬──────┘                              │
│         ┌─────┴──────┐                              │
│         │   Queue UI │                              │
│         └─────┬──────┘                              │
└───────────────┼──────────────────────────────────────┘
                │ REST + WebSocket
┌───────────────┼──────────────────────────────────────┐
│               │        Backend (FastAPI)              │
│         ┌─────┴──────┐                               │
│         │  DJ Brain  │ ← ordering, mix decisions     │
│         └─────┬──────┘                               │
│        ┌──────┴──────────────┐                       │
│   ┌────┴─────┐      ┌───────┴────┐                  │
│   │ Analyzer │      │  YT Search │                   │
│   │ (librosa)│      │  (yt-dlp)  │                   │
│   └──────────┘      └────────────┘                   │
│         ┌────────────────────┐                       │
│         │  Cache (SQLite)    │                        │
│         └────────────────────┘                       │
└──────────────────────────────────────────────────────┘
```

### Components

| Component | Responsibility | Tech |
|---|---|---|
| **YT Search Service** | Find tracks from seed/vibe/artists via YouTube | `yt-dlp` |
| **Audio Analyzer** | Download audio → extract DJ params → cache → discard audio | `yt-dlp` + `librosa` |
| **DJ Brain** | Order playlist (BPM, key, energy) + decide mix points & crossfade timing | Pure Python |
| **Mix Engine** | Two YouTube IFrame players, volume crossfading, seek, timing | JS + YouTube IFrame API |

## Data Flow

1. User inputs seed song / vibe / artist names
2. Backend searches YouTube → 20-30 candidate videos
3. Backend analyzes first 3 tracks in parallel (~20s cold start)
4. DJ Brain orders playlist by BPM gradient, harmonic key (Camelot wheel), energy arc
5. Frontend loads Track 1 on Deck A, seeks to optimal start, plays
6. While playing: backend analyzes next 2-3 tracks ahead (pipeline)
7. Backend → Frontend (WebSocket): mix command with timing, seek point, fade duration
8. Mix Engine crossfades: Deck A volume ↓, Deck B volume ↑ (cosine curve)
9. Deck A done → repeat from step 6

## Track Analysis — Per Song

```
video_id:       str       # YouTube video ID
title:          str       # Parsed from YouTube
bpm:            float     # e.g., 124.0
key:            str       # e.g., "Am" → Camelot "8A"
energy_curve:   list      # Energy values over time (per-second)
structure:      list      # [{"label": "intro", "start": 0, "end": 15.2}, ...]
mix_in_point:   float     # Timestamp (seconds) — where to start playing this track
mix_out_point:  float     # Timestamp (seconds) — where to start fading out
drop_timestamp: float     # Where the biggest energy spike is
has_vocals:     bool      # Avoid overlapping two vocal sections
duration:       float     # Total length in seconds
genre_hint:     str       # From YouTube title/description parsing
```

Cached in SQLite keyed by `video_id`. Never re-analyzed.

## DJ Brain Logic

### Playlist Ordering
- Sort by BPM (gradual progression, max ±5% between consecutive tracks)
- Within BPM range, prefer Camelot wheel neighbors (e.g., 8A → 8B or 7A or 9A)
- Energy arc: start mellow, build, peak around 60-70% through, gentle wind down

### Mix Point Selection
- **Outgoing track:** Start fade where energy drops in the last ~20% OR at the detected outro
- **Incoming track:** Seek past silence/long intro, land on first strong beat or detected intro end
- **Fallback:** If structure detection fails, fade last 16 seconds → first 16 seconds

### Crossfade Duration
- Chill/ambient: 16-20 seconds
- Standard house/techno: 10-16 seconds
- High energy/drops: 6-10 seconds
- Based on genre + energy level of both tracks

## API

```
POST /session              → { mode: "seed"|"vibe"|"artists", query: "..." }
                           ← { session_id, initial_queue }

GET  /session/{id}/queue   ← full queue with analysis status per track

WS   /session/{id}/live    → real-time mix commands:
                              { action: "fade_to_next", deck_b_seek: 15.2,
                                fade_start: 222.0, fade_duration: 14 }
                              { action: "queue_updated", next_track: {...} }

GET  /track/{video_id}     ← cached analysis for a track
```

## Frontend UI

Minimal — no waveforms or DJ knobs. Just:
- Now playing (track name, progress, BPM/key)
- Next up (track name, countdown to mix)
- Queue (list with analysis status, BPM, key, energy bar)
- Input controls (seed song / vibe search / artist mix)

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Audio analysis | librosa |
| YouTube interaction | yt-dlp |
| Cache | SQLite |
| Frontend | HTML/CSS/JS, YouTube IFrame API |
| Communication | REST + WebSocket |

## Extensibility Points

- **Persistence:** SQLite cache is already in place; add user tables, saved playlists later
- **Playback upgrade:** Swap YouTube IFrame for backend audio pipeline (Path B) for beat-matched mixing
- **Audio effects:** EQ, filters, loops — requires Path B upgrade
- **External discovery:** Plug in Last.fm/Spotify for better recommendations alongside YouTube search

## Decisions & Trade-offs

| Decision | Why |
|---|---|
| YouTube IFrame for playback | Legal, simple, no audio proxying. Trade-off: radio-style crossfade, not beat-synced |
| YouTube search only for discovery | Single platform, no extra API keys. Trade-off: less intelligent recommendations than Spotify/Last.fm |
| Metadata + audio analysis | YouTube metadata alone covers ~3/9 DJ params. Audio analysis via librosa fills the rest |
| Backend-driven mix timing | Brain lives server-side so we can improve it without touching frontend |
| SQLite cache | Simple, file-based, zero config. Swap to Postgres later if needed |
