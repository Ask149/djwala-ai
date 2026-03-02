# DjwalaAI Growth Roadmap — Design Doc

**Date:** 2026-03-02
**Status:** Approved
**Goal:** Get users (primary) + monetize (secondary)

---

## Positioning

**For** music lovers, party hosts, and road trippers
**who** want endless music that flows seamlessly
**DjwalaAI** is an AI auto-DJ
**that** creates smooth, mixed playlists from any artists or songs you type
**unlike** Spotify radio or YouTube autoplay
**we** actually mix tracks together with real DJ techniques (BPM matching, harmonic mixing, crossfades)

**Share hook:** "Like having a DJ at your party"

**Headline:** Type any artists. Get a seamless DJ mix. Free.

---

## Roadmap

### Phase A: Make It Shareable (This session)

The product works. Nobody knows it exists. Fix distribution first.

| # | Task | What | Why |
|---|------|------|-----|
| A1 | Share button | URL like `?artists=Drake,Weeknd` or `?song=Blinding+Lights` — pre-fills input on load | Virality. Someone shares in group chat → friend clicks → instant mix |
| A2 | SEO + meta tags | og:title, og:description, og:image, twitter:card | Shared links look good in iMessage/WhatsApp/Twitter |
| A3 | Landing page polish | Hero headline, value prop, how-it-works, CTA | First impression for cold traffic |
| A4 | README marketing | GitHub README that explains + sells | Devs who find the repo convert to users |
| A5 | Launch posts | HN Show, Reddit r/SideProject + r/webdev, Twitter | First wave of users |
| A6 | Analytics | Simple event tracking (plays, shares, mode usage) | Know what's working |

### Phase B: Wow Factor

| # | Task | What | Why |
|---|------|------|-----|
| B1 | Visual mix timeline | Horizontal bar showing tracks, crossfade zones, BPM/key per track | Screenshot moment — this is what people post |
| B2 | Party Mode | Fullscreen URL `/party/Drake+Weeknd` — big album art, dark, TV-optimized | Cast to TV at parties, impressive demo |

### Phase C: Lower Friction Entry

| # | Task | What | Why |
|---|------|------|-----|
| C1 | Mood/Genre mode | "House Party", "Road Trip", "Chill Vibes", "Late Night" presets | Zero-typing entry point, broader audience |
| C2 | Shareable mood links | `?mood=house-party` | Same virality as A1 but for moods |

---

## Phase A Detail

### A1: Share Button

**Frontend changes:**
- Add a share icon button next to the DJ! button (or in player bar)
- On click: copy URL with current input state to clipboard
- URL format: `https://djwala-ai.fly.dev/?mode=artists&q=Drake,The+Weeknd`
- On page load: parse URL params, pre-fill input, optionally auto-start

**Backend changes:** None — purely frontend URL params.

**URL Param Spec:**
- `?mode=artists&q=Artist1,Artist2` — artists mode
- `?mode=song&q=Song+Name` — song mode
- `?autoplay=1` — optional: auto-start on load

### A2: SEO + Meta Tags

```html
<title>DjwalaAI — AI-Powered Auto-DJ | Free Seamless Music Mixes</title>
<meta name="description" content="Type any artists, get a seamless DJ mix with BPM matching and smooth crossfades. Like having a DJ at your party. Free, no signup.">
<meta property="og:title" content="DjwalaAI — Like Having a DJ at Your Party">
<meta property="og:description" content="Type any artists. Get a seamless mix with real DJ transitions. Free.">
<meta property="og:image" content="[OG image URL — need to create]">
<meta property="og:url" content="https://djwala-ai.fly.dev">
<meta property="twitter:card" content="summary_large_image">
```

**OG Image:** Need to create a 1200x630 image. Options:
- Screenshot of the app in action
- Designed card with logo + tagline
- Use an OG image generation service

### A3: Landing Page Polish

Current: Just the app (input + queue). No explanation for first-time visitors.

**Add above the app:**
- Hero headline: "Type any artists. Get a seamless DJ mix."
- Subheadline: "AI-powered mixing with BPM matching and smooth crossfades. Like having a DJ at your party."
- The input IS the CTA (no separate button needed — the app is the landing page)

**Add below the app:**
- "How it works" — 3-step visual (Search → Analyze → Mix)
- Social proof section (once we have it)

### A4: README Marketing

Rewrite README.md to be a landing page for GitHub visitors. Include:
- Hook line + demo GIF/screenshot
- "Why?" section (pain point)
- Feature bullets (benefit-driven)
- Quick start
- Link to live app

### A5: Launch Posts

Write copy for:
- **HN Show:** "Show HN: DjwalaAI – Type any artists, get a seamless DJ mix (free)"
- **Reddit r/SideProject:** Humble, feedback-seeking tone
- **Reddit r/webdev:** Technical angle (cosine crossfades, Camelot wheel)
- **Twitter thread:** Problem → solution → demo

### A6: Analytics

Lightweight — no heavy dependencies:
- Option 1: Plausible (privacy-friendly, free for <10k views)
- Option 2: Simple custom events via fetch to a logging endpoint
- Track: page views, mix starts, share clicks, mode usage (artists vs song)

---

## Monetization Ideas (Future)

- **Pro Mode** ($5/mo): No rate limits, higher quality, priority queue
- **Event DJ License** ($20 one-time): Remove branding, custom logo for events
- **API Access**: Let others build on the mixing engine
- **Tips/Donations**: Simple "buy me a coffee" for now

---

## Current State Snapshot

- 11 features shipped, 127 tests passing
- Deployed at https://djwala-ai.fly.dev
- Zero SEO, zero share functionality, zero analytics
- GitHub repo behind local (needs push)

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Distribution before features | Product works; bottleneck is awareness |
| Share links via URL params | Zero backend work, works everywhere |
| Landing page = the app | Don't separate marketing from product |
| Phase B after A | Wow factor matters more after people are visiting |
| Mood mode last | Validates demand for existing modes first |
