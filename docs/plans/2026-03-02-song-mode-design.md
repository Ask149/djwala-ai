# Song Mode — Start with a Song, Endless Related Radio

**Date:** 2026-03-02
**Status:** Approved

## Problem

Currently DjwalaAI only supports artist-based input. If a user enters a specific song name like "Tum Hi Ho", the backend treats it as an artist name, searches `"Tum Hi Ho official music video"`, `"Tum Hi Ho full song"` — and the queue fills with 20 covers/versions of the same song. No variety.

Users want: enter a song → play that song first → continue with related songs endlessly (like YouTube radio).

## Design

### Section 1: UI — Mode Toggle

A pill toggle next to the input field: `[ Artists | Song ]`

- **Default:** Artists (current behavior, unchanged)
- **Song mode:** Placeholder changes to `"Enter a song name... (e.g., 'Tum Hi Ho')"`
- Toggle sends `mode: "song"` instead of `mode: "artists"` to `POST /session`
- Queue UI, player bar, NOW PLAYING — all unchanged

### Section 2: Backend — Song Mode Search

**New model:**
- `InputMode.SONG = "song"`

**New methods in `youtube.py`:**

1. `search_song(query)` — Search YouTube for the exact song, return top 1 result as seed. Uses `ytsearch1:{query}` via yt-dlp (or API equivalent).

2. `get_mix_playlist(video_id)` — Extract YouTube Mix playlist `RD{video_id}` via yt-dlp `--flat-playlist`. Returns ~25-50 `TrackInfo` items (excluding the seed to avoid duplicates).

**Updated `build_queue()` for song mode:**

1. `search_song("Tum Hi Ho")` → seed `TrackInfo`
2. `get_mix_playlist(seed.video_id)` → 25-50 related `TrackInfo` candidates
3. Analyze seed + first 4 candidates (batch of 5)
4. Queue = `[seed]` + DJ Brain orders the other 4
5. Background: `analyze_more()` processes remaining candidates

**Key rule:** Seed song is always position 0 — DJ Brain only orders tracks 1+.

**Fallback:** If yt-dlp fails, try YouTube Data API `playlistItems.list(playlistId=f"RD{video_id}")` with BYOK key.

### Section 3: Rolling Queue + Cleanup

**When to fetch more:** After `analyze_more()` finishes all candidates, if fewer than 5 tracks remain ahead of `current_index`, fetch more.

**How to fetch more:** Call `get_mix_playlist()` using the last track in the queue's `video_id` as the new seed. Chains YouTube recommendations naturally. Deduplicate against all video IDs already seen.

**Cleanup — backend:**
- After `advance()`, if `current_index > 3`, trim oldest tracks from queue, shift `current_index` down
- Keep `seen_ids: set[str]` on the Session to prevent duplicates across fetches

**Cleanup — frontend:**
- Frontend rebuilds queue DOM from `/session/{id}/queue` responses
- Backend returns trimmed queue → DOM stays small automatically
- No frontend cleanup changes needed

**Memory profile:**
- ~3 played + current + ~10-15 upcoming ≈ 15-20 `TrackAnalysis` objects max
- `seen_ids` set is just strings — negligible even at 500+
- Energy curves (~300 floats) × 20 tracks ≈ tiny

## What's NOT Changing

- Player bar UI (just shipped)
- Crossfade/mix engine
- Artist mode (fully preserved)
- Backend API shape (`POST /session`, WebSocket, `/queue` endpoint)
- Test infrastructure

## Approach Chosen

YouTube Mix Playlist (`RD{videoId}`) via yt-dlp as primary, YouTube Data API as fallback. DJ Brain reorders for smooth mixing. Rejected alternatives:
- API search with context (not real recommendations, just "more from same artist")
- Hybrid with separate search strategy (unnecessary complexity — both yt-dlp and API can use the same Mix playlist strategy)
