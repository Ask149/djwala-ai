# DjwalaAI — Launch Copy

**Live URL:** https://djwala-ai.fly.dev
**GitHub:** https://github.com/Ask149/djwala-ai

---

## Twitter/X Thread

**Suggested posting time:** Tuesday-Thursday, 10am-2pm ET
**Hashtags:** #buildinpublic #webdev
**Accounts to tag:** (add any DJ/music tech accounts you follow)

---

**1/ (Hook — must work standalone)**

Spotify radio just queues songs. YouTube autoplay is random chaos.

I built an AI auto-DJ that actually *mixes* tracks together — BPM matching, harmonic key detection, smooth crossfades.

Type any artists. Get a seamless DJ set. Free.

https://djwala-ai.fly.dev

**2/**

The problem: You're hosting a party and the music keeps awkwardly cutting between songs.

Or you're on a road trip and Spotify's "radio" is just... a playlist with silence between tracks.

There's no *flow*. No transitions. No mixing.

**3/**

DjwalaAI fixes this:

- Finds tracks from your artists on YouTube
- Detects BPM and musical key for each track
- Orders them for optimal DJ flow (Camelot wheel)
- Crossfades between tracks with cosine curves at smart mix points

It's like hiring a DJ who knows every song.

**4/**

It gets better. Pick a mood instead of typing artists:

- House Party
- Road Trip
- Late Night
- Chill Vibes
- Workout
- Bollywood Hits
- Hip Hop
- Latin

One tap. Instant mix. Zero friction.

**5/**

Party Mode: hit P for a fullscreen dark overlay. Cast it to your TV at a party.

Synced Lyrics: hit L for real-time lyrics that scroll with the music.

Visual Timeline: see your entire set laid out — BPM, key, crossfade zones.

**6/**

Built this as a weekend project that kept growing:

- Python + FastAPI backend
- Vanilla JS frontend (no build step)
- YouTube IFrame API for playback
- Dual iframes for crossfading
- librosa for audio analysis
- 133 tests

Fully open source: https://github.com/Ask149/djwala-ai

**7/**

Try it right now — no signup, no login, completely free:

https://djwala-ai.fly.dev

Or share a mix with friends:
https://djwala-ai.fly.dev/?mood=house-party

Would love feedback on the mixing quality and what moods/genres to add next.

---

## Hacker News — Show HN

**Title:**

```
Show HN: DjwalaAI – Type any artists, get a seamless DJ mix with BPM and key matching
```

**Suggested posting time:** Monday-Wednesday, 8-10am ET

**First comment:**

Hey HN! I built this because Spotify radio and YouTube autoplay don't actually *mix* music — they just queue songs with dead air between them.

DjwalaAI finds tracks from your artists on YouTube, analyzes each one (BPM, musical key via chroma detection, energy curve), orders them using the Camelot wheel for harmonic compatibility, and crossfades between them with cosine curves at energy-aware mix points.

You can type artists, start from a specific song, or pick a mood preset (House Party, Late Night, etc.) for a zero-typing experience.

Some fun details:
- Dual YouTube iframes swap between foreground/background for gapless crossfading
- Smart mix points skip dead intros and cut before outros fade out
- Genre-aware BPM estimation as fallback when audio analysis isn't available
- Party Mode (press P) for a fullscreen dark overlay — great for casting to a TV
- Synced lyrics (press L) via LRCLIB

Tech: Python/FastAPI backend, vanilla JS frontend, librosa for audio analysis, SQLite cache. 133 tests. No build step, no frameworks.

Try it: https://djwala-ai.fly.dev
Code: https://github.com/Ask149/djwala-ai

Would especially love feedback on the mixing transitions — are the crossfade durations right? Does the track ordering feel natural?

---

## Reddit — r/SideProject

**Title:**

```
I built an AI auto-DJ that actually mixes tracks together (not just a playlist)
```

**Suggested posting time:** Tuesday-Thursday, 10am-1pm ET

**Post:**

I kept getting frustrated that Spotify radio and YouTube autoplay just queue songs one after another. No transitions, no flow, just awkward silence between tracks.

So I built DjwalaAI — an AI-powered auto-DJ. You type in artist names (or pick a mood like "House Party" or "Late Night") and it creates a real DJ mix:

- Finds tracks on YouTube
- Analyzes BPM, musical key, and energy for each track
- Orders them for smooth flow using the Camelot wheel (same system real DJs use)
- Crossfades between tracks at smart mix points

Some features I'm proud of:
- **Party Mode** — fullscreen dark overlay, great for casting to a TV at parties
- **Synced Lyrics** — real-time lyrics that scroll with the music
- **Visual Timeline** — see the entire set with BPM, key, and crossfade zones
- **Mood Presets** — one-tap vibes (Road Trip, Chill Vibes, Workout, etc.)
- **Shareable links** — send a mix to friends: `?mood=house-party`

Tech stack: Python/FastAPI, vanilla JS, YouTube IFrame API, librosa for audio analysis. Open source with 133 tests.

Try it (free, no signup): https://djwala-ai.fly.dev
GitHub: https://github.com/Ask149/djwala-ai

Would love feedback — especially on the mixing quality and what moods/genres to add.

---

## Reddit — r/webdev

**Title:**

```
Built a real-time DJ mixing engine in vanilla JS with dual YouTube iframes and cosine crossfades
```

**Suggested posting time:** Tuesday-Thursday, 10am-1pm ET

**Post:**

Wanted to share an interesting technical challenge I solved: real-time audio crossfading using YouTube's IFrame API (which gives you basically zero control over audio).

**The trick:** Two YouTube iframes that swap between foreground and background. As one track approaches its mix-out point, the second iframe loads the next track and starts fading in with a cosine curve while the first fades out with a sine curve. This creates smooth, natural-sounding crossfades.

The backend (Python/FastAPI) does the heavy lifting:
- **BPM detection** via librosa's beat tracking
- **Key detection** via chroma feature analysis → Camelot wheel mapping
- **Smart mix points** — skip dead intros (energy-based) and cut before outro decay
- **Track ordering** — sorts by Camelot compatibility + BPM proximity for harmonic flow

Some other things that were fun to build:
- Genre-aware fallback estimation when audio analysis fails (detects "reggaeton" vs "drill" etc. from title keywords)
- Synced lyrics via LRCLIB API with LRC timestamp parsing
- A position monitor that runs every 500ms to trigger crossfades at the right moment
- WebSocket-based queue updates for real-time status

The whole frontend is vanilla JS — no React, no build step, just a single `app.js` class. The mixing engine is a separate `mix-engine.js` module.

133 tests, deployed on Fly.io.

Live: https://djwala-ai.fly.dev
Source: https://github.com/Ask149/djwala-ai

Happy to dive deeper into any of the mixing/analysis algorithms if anyone's curious.

---

## Share Links for Social

Copy-paste ready:

```
House Party mix: https://djwala-ai.fly.dev/?mood=house-party
Road Trip mix:   https://djwala-ai.fly.dev/?mood=road-trip
Late Night mix:  https://djwala-ai.fly.dev/?mood=late-night
Chill Vibes mix: https://djwala-ai.fly.dev/?mood=chill-vibes
Workout mix:     https://djwala-ai.fly.dev/?mood=workout
Bollywood mix:   https://djwala-ai.fly.dev/?mood=bollywood
Hip Hop mix:     https://djwala-ai.fly.dev/?mood=hip-hop
Latin mix:       https://djwala-ai.fly.dev/?mood=latin

Custom mix:      https://djwala-ai.fly.dev/?mode=artists&q=Drake,The+Weeknd
Song start:      https://djwala-ai.fly.dev/?mode=song&q=Blinding+Lights
```
