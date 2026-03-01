# DjwalaAI — Fly.io Deployment Guide

## Why Fly.io?

| Feature | Benefit |
|---------|---------|
| Auto-HTTPS | Free SSL + `*.fly.dev` domain |
| Auto-stop/start | Pay only when running (~$0-6/month) |
| Docker-native | Uses existing Dockerfile |
| Persistent volumes | SQLite cache survives restarts |
| WebSocket support | Live DJ mix commands work |
| No VPS management | No SSH, no Caddy config |

**Cost:** ~$1-6/month (shared-cpu-1x with auto-stop + 1GB volume)

---

## Prerequisites

1. **Fly.io account** — Sign up at https://fly.io/app/sign-up
   - Use email: `contact.iodevz@gmail.com`
   - Add payment method (required for VMs with >256MB RAM)

2. **flyctl CLI** — Install:
   ```bash
   brew install flyctl
   ```

---

## Deployment Steps

### 1. Authenticate with Fly.io

```bash
fly auth login
```

### 2. Launch the App

From the project root (where `fly.toml` exists):

```bash
fly launch --copy-config --no-deploy
```

**What this does:**
- Reads `fly.toml` configuration
- Creates the app on Fly.io (name: `djwala-ai`)
- Creates the persistent volume (`djwala_data`, 1GB)
- Does **not** deploy yet (we'll do that next)

**If `djwala-ai` is taken:** Edit `fly.toml` line 1 and try `djwala-ai-app` or `djwalai`

### 3. Deploy

```bash
fly deploy
```

**What this does:**
- Builds Docker image from `Dockerfile`
- Pushes image to Fly.io registry
- Provisions shared-cpu-1x VM (1GB RAM, 1 vCPU)
- Mounts persistent volume at `/data`
- Starts the app with health checks
- Assigns `https://djwala-ai.fly.dev` domain

**Build time:** ~3-5 minutes (ffmpeg dependencies are large)

### 4. Verify Deployment

```bash
# Check app status
fly status

# Check logs
fly logs

# Test health endpoint
curl https://djwala-ai.fly.dev/health
# Expected: {"status":"ok"}

# Open in browser
open https://djwala-ai.fly.dev/static/index.html
```

### 5. Test the DJ

```bash
# Create a session
curl -X POST https://djwala-ai.fly.dev/session \
  -H "Content-Type: application/json" \
  -d '{"mode":"vibe","query":"deep house chill"}'
# Expected: {"session_id":"...", "status":"searching"}

# Check queue (use session_id from above)
curl https://djwala-ai.fly.dev/session/YOUR_SESSION_ID/queue
```

---

## Configuration

### Environment Variables

Set secrets via flyctl (never commit secrets to git):

```bash
# CORS origins (optional, defaults to ["*"])
fly secrets set DJWALA_CORS_ORIGINS='["https://djwala-ai.fly.dev"]'

# Rate limit (optional, defaults to 5/minute)
fly secrets set DJWALA_RATE_LIMIT="10/minute"
```

View secrets:
```bash
fly secrets list
```

**Note:** `DJWALA_DATABASE_PATH` is already set in `fly.toml` to `/data/djwala_cache.db`

### Persistent Volume

The SQLite cache lives in a 1GB persistent volume:

```bash
# View volumes
fly volumes list

# Snapshot backup (manual)
fly volumes snapshots create djwala_data

# View snapshots
fly volumes snapshots list djwala_data
```

---

## Auto-stop/start Behavior

**Configured in `fly.toml`:**
```toml
auto_stop_machines = 'stop'  # Stop when idle
auto_start_machines = true   # Start on incoming request
min_machines_running = 0     # Allow full shutdown
```

**What this means:**
- After ~5 minutes of inactivity, the VM **stops** (no charges for CPU/RAM)
- Next request **starts** the VM (~5-15s cold start)
- You only pay for **active runtime** + volume storage ($0.15/GB/month)

**Cold start time:** ~5-15 seconds (Python + numpy import)

---

## Scaling (When You Outgrow Free Tier)

### Scale vertically (more RAM/CPU)

```bash
# Upgrade to 2GB RAM
fly scale memory 2048

# View current size
fly scale show
```

### Scale horizontally (multiple machines)

```bash
# Add a second machine
fly scale count 2

# Auto-scale based on load
fly autoscale standard min=1 max=3
```

### Keep machines always running

Edit `fly.toml`:
```toml
min_machines_running = 1  # Always keep 1 running
auto_stop_machines = 'off'  # Disable auto-stop
```

Then:
```bash
fly deploy
```

---

## Updating the App

After code changes:

```bash
git pull  # (if using git)
fly deploy
```

Fly.io rebuilds and does a **rolling deployment** (zero downtime if >1 machine).

---

## Monitoring

### View logs (real-time)
```bash
fly logs
```

### View metrics
```bash
fly dashboard
# Opens browser to https://fly.io/apps/djwala-ai/metrics
```

### SSH into machine (for debugging)
```bash
fly ssh console
```

---

## Custom Domain (Optional)

### Add your domain

```bash
# Add domain
fly certs create yourdomain.com

# View certificate status
fly certs show yourdomain.com
```

### Configure DNS

Add these records at your DNS provider:

| Type | Name | Value |
|------|------|-------|
| A | @ | (IP shown by `fly certs show`) |
| AAAA | @ | (IPv6 shown by `fly certs show`) |

**Certificate:** Fly.io auto-provisions Let's Encrypt SSL (same as Caddy)

---

## Cost Breakdown

| Component | Usage | Cost |
|---|---|---|
| shared-cpu-1x | $0.001/min when running | ~$0-5.70/month |
| 1GB persistent volume | Always charged | $0.15/month |
| Bandwidth | First 100GB free | $0 (for MVP) |
| SSL certificate | Automatic | Free |
| **Total** | | **~$1-6/month** |

**With auto-stop:** If app is used 2 hours/day = ~$4.00/month CPU + $0.15 volume = **$4.15/month**

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `fly launch` fails (name taken) | Edit `fly.toml` line 1, change app name |
| Build timeout | Increase timeout: `fly deploy --build-timeout 600` |
| Cold start too slow | Set `min_machines_running = 1` in `fly.toml` |
| WebSocket disconnects | Normal during auto-stop, reconnect on frontend |
| Out of volume space | Scale volume: `fly volumes extend djwala_data -s 2` |
| Static files 404 (fixed) | Ensure `DJWALA_STATIC_DIR=/app/static` in Dockerfile |
| Tests fail locally | `source .venv/bin/activate && pip install -e ".[dev]"` |

---

## Quick Reference

| Command | Action |
|---------|--------|
| `fly auth login` | Authenticate with Fly.io |
| `fly launch --copy-config --no-deploy` | Create app (first time) |
| `fly deploy` | Deploy/update app |
| `fly status` | Check app status |
| `fly logs` | View real-time logs |
| `fly ssh console` | SSH into machine |
| `fly scale show` | View VM size |
| `fly volumes list` | View volumes |
| `fly secrets set KEY=value` | Set environment variable |
| `fly open` | Open app in browser |
| `fly dashboard` | Open web dashboard |

---

## Next Steps

1. ✅ Deploy to Fly.io
2. Test with real queries (Bollywood, deep house, etc.)
3. Monitor logs for errors
4. (Optional) Add custom domain
5. (Optional) Set up GitHub Actions for CI/CD

---

## Comparison: Fly.io vs Hetzner

| Feature | Fly.io | Hetzner CAX11 |
|---------|--------|---------------|
| Setup time | 5 minutes | 30+ minutes |
| SSL/HTTPS | Auto (Let's Encrypt) | Manual (Caddy setup) |
| Auto-stop | Yes (pay per use) | No (always charged) |
| Minimum cost | $0.15/month (volume only) | €4.15/month (~$4.50) |
| Scaling | `fly scale memory 2048` | Provision new VPS |
| Maintenance | Zero | OS updates, security patches |

**For MVP:** Fly.io is simpler and cheaper (auto-stop when idle).
**For scale:** Hetzner is cheaper at high load (flat rate vs per-minute).

---

## Support

- Fly.io Docs: https://fly.io/docs/
- Community: https://community.fly.io/
- DjwalaAI Issues: (create GitHub repo first)
