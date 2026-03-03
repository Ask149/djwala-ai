# DjwalaAI — Launch Posts

**Live app:** https://djwala-ai.fly.dev
**GitHub:** https://github.com/Ask149/djwala-ai

---

## 1. Show HN

**Title:** Show HN: DjwalaAI – Type any artists, get a seamless DJ mix (free, no signup)

**Body:**

Hey HN,

I built an AI-powered auto-DJ that actually mixes tracks together — not just a playlist, but real crossfaded transitions with BPM matching and harmonic mixing.

**Try it:** https://djwala-ai.fly.dev

Type a few artist names (comma separated), pick a mood, or enter a song name. The engine finds tracks on YouTube, analyzes each one for tempo and key, orders them for optimal DJ flow using the Camelot wheel, and plays them back with smooth cosine crossfades between dual YouTube iframes.

**How it works under the hood:**

- yt-dlp searches YouTube and extracts audio metadata
- librosa detects BPM via onset envelope + autocorrelation, and musical key via chroma feature analysis
- Tracks get mapped to the Camelot wheel for harmonic compatibility — transitions only happen between compatible keys
- Mix points are chosen using energy curve analysis (skip dead intros, cut before outros fade)
- In the browser, two YouTube IFrame players alternate — one plays while the next is cued. At the mix point, a cosine crossfade blends them over ~8 seconds
- The entire frontend is vanilla JS — no React, no build step, no bundler

**Tech stack:** Python/FastAPI backend, vanilla JS frontend, SQLite cache, deployed on Fly.io.

I also built a Party Mode (fullscreen for casting to a TV), synced lyrics, a visual mix timeline, and 8 mood presets for zero-typing entry. It's a PWA, so you can install it on your phone.

141 tests. MIT licensed. Feedback welcome — especially from anyone who actually DJs and can tell me what I'm doing wrong.

GitHub: https://github.com/Ask149/djwala-ai

---

## 2. Reddit r/SideProject

**Title:** I built a free AI DJ that actually mixes tracks together — not just a playlist

**Body:**

I got tired of Spotify radio and YouTube autoplay just queuing random songs with no flow. So I built DjwalaAI — an AI auto-DJ that finds tracks, analyzes their tempo and key, and crossfades between them like a real DJ would.

**Live demo:** https://djwala-ai.fly.dev

**How to use it:**
1. Type some artist names (or pick a mood like "House Party" or "Road Trip")
2. Hit DJ!
3. It searches YouTube, analyzes BPM + musical key, orders tracks for optimal flow, and plays them with smooth crossfades

**What makes it different from a playlist:**
- BPM matching — transitions between tracks at similar tempos
- Harmonic mixing — uses the Camelot wheel to only transition between key-compatible songs
- Cosine crossfades — smooth 8-second blends, not hard cuts
- Smart mix points — skips dead intros and cuts before outros die out

**Other stuff I added:**
- Party Mode — fullscreen with big track art, perfect for casting to a TV at a party
- Song Mode — start from one song and it auto-discovers similar tracks
- 8 mood presets — House Party, Road Trip, Late Night, Chill Vibes, Workout, Bollywood, Hip Hop, Latin
- Synced lyrics that scroll with the music
- Shareable links — send `?mood=house-party` to a friend and they get instant music
- PWA — install it on your phone like a native app

It's completely free, no signup, no ads. Open source on GitHub.

I'd love feedback on what could be better. Been building this over a few intense weekends and I'm too close to it now to see the obvious problems.

**GitHub:** https://github.com/Ask149/djwala-ai

---

## 3. Reddit r/webdev

**Title:** Built a DJ mixing app with FastAPI + vanilla JS (no React, no build step) — here's what I learned

**Body:**

I built [DjwalaAI](https://djwala-ai.fly.dev), an AI auto-DJ that creates seamless mixed playlists from YouTube. The interesting part (from a webdev perspective) is the architecture — it's FastAPI on the backend, vanilla JS on the frontend, zero build tools, and runs on a single $3/month Fly.io machine.

**The challenge:** Play two YouTube videos simultaneously in the browser and crossfade between them, timed to the beat, with key-compatible transitions.

**How I solved it:**

**Backend (Python/FastAPI):**
- yt-dlp for YouTube search (no YouTube API key required for basic operation)
- librosa for audio analysis — BPM detection via onset envelopes, key detection via chroma features, energy curves via RMS
- Camelot wheel mapping — translates detected musical keys to a wheel where compatible keys are adjacent
- Track ordering algorithm: minimizes harmonic distance + BPM jumps across the set
- SQLite cache so tracks don't get re-analyzed
- WebSocket endpoint for live queue updates as analysis completes in the background

**Frontend (vanilla JS):**
- Dual YouTube IFrame API players — one active, one on standby
- At the mix point, both play simultaneously with a cosine volume curve (smooth S-curve fade, not linear)
- No React, no Vue, no Svelte — just classes, DOM manipulation, and CSS. The entire JS is ~1600 lines across 3 files
- Canvas-based waveform visualization (generated from track metadata, not actual audio)
- Service worker for PWA install + offline caching

**Lessons learned:**
1. **Vanilla JS is fine.** For a single-page app with clear state flow, classes + querySelector is perfectly readable. No virtual DOM overhead, instant load.
2. **YouTube IFrame API is quirky.** You can't get raw audio for Web Audio API mixing. Volume crossfades work surprisingly well as a substitute.
3. **librosa is slow but accurate.** BPM detection on a 4-minute track takes ~3 seconds. Caching is essential.
4. **WebSockets > polling for this.** The backend analyzes tracks asynchronously and pushes updates. SSE would also work but WS was simpler with FastAPI.
5. **Fly.io's free tier is generous.** A single shared-cpu machine handles this fine for hundreds of users. Auto-stop on idle keeps costs near zero.

**Test coverage:** 141 pytest tests covering the API, session management, analysis cache, mixing logic, and edge cases.

Try it: https://djwala-ai.fly.dev

Source: https://github.com/Ask149/djwala-ai

Happy to answer questions about any part of the architecture.

---

## 4. Twitter/X Thread

**Tweet 1 (Hook):**
I built an AI DJ that actually mixes tracks together.

Not a playlist. Real crossfades with BPM matching and harmonic mixing.

Type any artists → get a seamless DJ set. Free.

https://djwala-ai.fly.dev

🧵 How it works:

**Tweet 2 (The Problem):**
Spotify radio and YouTube autoplay just queue songs.

No flow. No transitions. Songs end abruptly and the next one starts in a completely different key and tempo.

I wanted something that actually blends tracks like a real DJ would.

**Tweet 3 (The Solution):**
DjwalaAI analyzes every track for:
- BPM (tempo)
- Musical key (mapped to the Camelot wheel)
- Energy curve

Then orders them for smooth flow and crossfades between them with cosine curves.

The result sounds like a DJ set, not a shuffled playlist.

**Tweet 4 (Tech):**
Built with:
- Python + FastAPI backend
- librosa for BPM/key detection
- yt-dlp for YouTube search
- Vanilla JS frontend (no React!)
- Dual YouTube iframes with volume crossfades
- Deployed on Fly.io

141 tests. ~1600 lines of JS. Zero build step.

**Tweet 5 (Features):**
Some things I'm proud of:

🎉 8 mood presets (House Party, Road Trip, etc.)
🖥️ Party Mode — fullscreen, cast to your TV
🎤 Synced lyrics
⌨️ Keyboard shortcuts
📱 PWA — install on your phone
🔗 Shareable links

**Tweet 6 (CTA):**
Try it free, no signup: https://djwala-ai.fly.dev

Source code (MIT): https://github.com/Ask149/djwala-ai

Would love feedback — especially from actual DJs who can tell me what I'm getting wrong.

---

## Posting Notes

**Timing:**
- HN: Tuesday–Thursday, 8-10am ET
- Reddit: Tuesday–Thursday, early morning ET
- Twitter: Post thread, then share the HN/Reddit links as replies

**Engagement:**
- Reply to every comment in the first 2 hours
- On HN: be technical, answer architecture questions honestly
- On Reddit: be humble, ask for feedback genuinely
- On Twitter: quote-tweet with short demo clips if possible

**Don't forget:**
- The app should be working when you post (check https://djwala-ai.fly.dev/health first)
- Have the Fly.io dashboard open to monitor traffic
- Check analytics at `/tmp/djwala_analytics.jsonl` on the Fly machine (`fly ssh console` → `cat /tmp/djwala_analytics.jsonl`)
