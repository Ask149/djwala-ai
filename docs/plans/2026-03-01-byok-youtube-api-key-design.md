# BYOK YouTube API Key — Design Document

**Date:** 2026-03-01
**Status:** Approved

## Problem

DjwalaAI's YouTube search (yt-dlp) is blocked on production (Fly.io datacenter IPs). Users need a way to provide their own YouTube API key for reliable access.

## Solution

BYOK — users optionally provide their own YouTube API key via browser UI, stored in localStorage, sent in POST /session body.

## Decisions

| Decision | Choice |
|----------|--------|
| Target user | Both casual + power users |
| Key storage | Browser localStorage |
| UI | Gear icon + failure banner |
| Transport | In POST /session body |

## Files Modified

- `src/djwala/session.py` — Session dataclass + create_session + build_queue
- `src/djwala/main.py` — SessionCreate model + endpoint
- `src/djwala/youtube.py` — search() fallback chain
- `static/index.html` — Settings gear + modal
- `static/js/app.js` — Settings logic + localStorage + error banner
- `static/css/style.css` — Settings + banner styles
- `tests/test_api.py` — 2 new tests
- `tests/test_youtube.py` — 1 new test
