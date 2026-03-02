# Mix Length Slider — Design Document

**Date:** 2026-03-01
**Status:** Implemented

## Summary

Added a "Short Mix ↔ Full Song" slider (0-100, default 50) to the settings modal.
Users control how much of each song plays in their DJ mix.

## How It Works

- Slider value stored in `localStorage` as `djwala_mix_length`
- Sent in `POST /session` body as `mix_length: int` (0-100)
- Used by `analyzer.py:estimate()` to interpolate mix-in/mix-out percentages
- Genre energy level applies ±2-3% adjustment on top
- Same clamping: 8-25s mix_in, 60s minimum play time

## Slider Behavior

| Slider | mix_in % | mix_out % | Effect |
|--------|----------|-----------|--------|
| 0 (Short) | 15% | 70% | Hear ~55% of each song |
| 50 (Default) | 8.5% | 83.5% | Hear ~75% of each song |
| 100 (Full) | 2% | 97% | Hear ~95% of each song |

## Files Changed

- `src/djwala/main.py` — SessionCreate model + Field validation
- `src/djwala/session.py` — Session dataclass + create_session + wiring
- `src/djwala/analyzer.py` — estimate() slider interpolation
- `static/index.html` — Slider HTML in settings modal
- `static/js/app.js` — Slider logic, localStorage, POST body
- `static/css/style.css` — Slider styles
- `tests/test_api.py` — 3 new tests
- `tests/test_analyzer.py` — 6 new tests
