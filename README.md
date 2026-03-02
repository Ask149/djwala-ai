# 🎧 DjwalaAI

**Type any artists. Get a seamless DJ mix.**

AI-powered auto-DJ that finds tracks on YouTube and mixes them with real DJ techniques — BPM matching, harmonic mixing (Camelot wheel), and smooth crossfades. Like having a DJ at your party. Free, no signup.

**[Try it live →](https://djwala-ai.fly.dev)**

---

## Why?

Spotify radio and YouTube autoplay just queue songs. There's no flow, no transitions, no mixing. DjwalaAI actually blends tracks together like a real DJ would — detecting tempo, matching keys, and crossfading at the right moments.

## Features

- **Artist Mode** — Enter comma-separated artists, get a mixed set across all of them
- **Song Mode** — Start from a specific song, auto-discover similar tracks via YouTube Mix
- **BPM Detection** — Analyzes each track's tempo for smooth speed-matched transitions
- **Harmonic Mixing** — Uses the Camelot wheel to find key-compatible transitions
- **Smart Mix Points** — Energy-aware intro skip and outro cutoff for natural blends
- **Cosine Crossfades** — Smooth, natural-sounding transitions between tracks
- **Share Mixes** — One-click shareable links that auto-start for the recipient
- **Mix Length Control** — Slider from short mix clips to full songs
- **BYOK** — Bring your own YouTube API key for unlimited use

## How It Works

1. **Search** — Enter artist names or a song title
2. **Analyze** — AI detects BPM, musical key (Camelot), and energy curve for each track
3. **Order** — Tracks sorted for optimal DJ flow (key compatibility + BPM proximity)
4. **Mix** — Played with smooth cosine/sine crossfades at energy-aware mix points

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, yt-dlp, librosa |
| Frontend | Vanilla JS, YouTube IFrame API |
| Analysis | BPM detection, chroma-based key detection, Camelot wheel |
| Mixing | Dual YouTube iframes, cosine crossfade in browser |
| Cache | SQLite (avoids re-analyzing tracks) |
| Deploy | Fly.io |

## Quick Start

```bash
# Clone and install
git clone https://github.com/Ask149/djwala-ai.git
cd djwala-ai
uv sync

# Run locally
uv run uvicorn djwala.main:app --port 8888

# Open http://localhost:8888
```

## Tests

```bash
uv run pytest tests/ -v
# 127 tests passing
```

## Deploy

```bash
fly deploy
```

See `FLY_DEPLOYMENT.md` for details.

## Share a Mix

Share links auto-start mixes for the recipient:

```
https://djwala-ai.fly.dev/?mode=artists&q=Drake,The+Weeknd
https://djwala-ai.fly.dev/?mode=song&q=Blinding+Lights
```

---

Built with ❤️ and too many late nights.
