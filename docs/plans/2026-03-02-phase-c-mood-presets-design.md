# Phase C: Mood/Genre Presets — Design Doc

**Date:** 2026-03-02
**Status:** Approved
**Goal:** Lower friction entry — zero-typing start for new users

---

## Problem

Current entry requires knowing artist names or song titles. New users who just want background music for a party/drive/workout bounce because they have to think of what to type. Phase C removes that barrier entirely.

---

## Solution

8 mood preset buttons visible on the landing page. One tap → session starts immediately with YouTube search queries mapped to that mood. Shareable via `?mood=house-party` URLs.

---

## Presets

| ID | Label | Search Queries |
|---|---|---|
| `house-party` | 🎉 House Party | "house party hits", "club bangers 2024" |
| `road-trip` | 🚗 Road Trip | "road trip songs", "driving music hits" |
| `late-night` | 🌙 Late Night | "late night r&b", "midnight vibes" |
| `chill-vibes` | ☕ Chill Vibes | "chill lofi beats", "relaxing music" |
| `workout` | 💪 Workout | "workout music", "gym motivation songs" |
| `bollywood` | 🎵 Bollywood Hits | "bollywood party songs", "hindi hits" |
| `hip-hop` | 🔥 Hip Hop | "hip hop hits 2024", "rap bangers" |
| `latin` | 💃 Latin | "reggaeton hits", "latin party music" |

Preset map lives server-side so queries can be tuned without redeploying frontend.

---

## UI

- **Location:** Landing page, between input area and "How it works" section
- **Heading:** "Or pick a vibe"
- **Layout:** 8 pill buttons in a responsive grid (4×2 desktop, 2×4 mobile)
- **Each pill:** Emoji + label (e.g., "🎉 House Party")
- **Behavior:** Grid hides when a session is active (same pattern as how-it-works)
- **On tap:** Starts session immediately; input area shows the mood label as context

---

## Backend

- New `InputMode.MOOD` enum value
- `/start` endpoint accepts `mode=mood&query=house-party`
- `YouTubeSearch.build_queries()` handles mood mode: looks up preset ID → returns mapped search queries
- Preset map is a dict constant in the backend (not a separate API)

---

## Share URLs

- `?mood=house-party` → auto-starts mood session on load
- Share button generates mood URL when in mood mode
- Existing `?mode=artists&q=` and `?mode=song&q=` unchanged

---

## Analytics

- Track `mood_start` event with `{ mood: "house-party" }`
- Reveals which presets are popular (informs future preset additions)

---

## Out of Scope

- Custom mood creation
- Mood mixing (combining presets)
- Mood-specific visuals/themes
- Backend preset management API

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| YouTube search queries, not artist lists | More variety, surfaces trending tracks, not locked to specific artists |
| 8 presets | Good coverage without being overwhelming |
| Visible on landing page, not behind a tab | Zero friction — the whole point is discoverability |
| One tap starts session | Remove every possible click between "I want music" and hearing music |
| Preset map server-side | Can tune search queries without cache-busting frontend |
| Shareable mood URLs | Same virality pattern as Phase A share links |
