# DjwalaAI

AI-powered auto-DJ for Bollywood and Indian music. Enter your favorite artists, get a DJ-quality mixed playlist with BPM matching, harmonic mixing (Camelot wheel), and smooth crossfades.

## Quick Start

```bash
# Install dependencies
uv sync

# Run locally
uv run uvicorn djwala.main:app --port 8888

# Open http://localhost:8888
```

## How It Works

1. **Search** — Enter artist names (e.g., "Arijit Singh, Pritam, AP Dhillon")
2. **Analyze** — Downloads audio, detects BPM, key (Camelot wheel), and energy curve
3. **Order** — Sorts tracks for smooth DJ transitions (key compatibility + BPM proximity)
4. **Mix** — Plays tracks with cosine/sine crossfades at optimal mix points

## Tech Stack

- **Backend:** Python, FastAPI, yt-dlp, librosa
- **Frontend:** Vanilla JS, YouTube IFrame API
- **Analysis:** BPM detection, chroma-based key detection, Camelot wheel mapping
- **Mixing:** Cosine crossfade, energy-aware mix points
- **Cache:** SQLite (avoids re-analyzing tracks)

## Deployment

Deployed on Fly.io. See `FLY_DEPLOYMENT.md` for details.

```bash
fly deploy
```

## Tests

```bash
uv run pytest tests/ -v
```
