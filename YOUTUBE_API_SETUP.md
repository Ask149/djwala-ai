# YouTube Data API v3 Setup Guide (Optional)

## Overview

DjwalaAI uses **yt-dlp as the primary method** for YouTube search (metadata-based, no API key needed). The **YouTube Data API v3 is an optional secondary method** that can be used as a fallback if yt-dlp is blocked in your deployment environment.

### Default Behavior:
- ✅ **Primary:** yt-dlp (metadata extraction, works in most environments)
- 🔄 **Secondary:** YouTube Data API v3 (optional fallback, requires API key)

### When to Use YouTube API:
- Your deployment environment blocks yt-dlp (datacenter IP detection)
- You want guaranteed reliability at the cost of API quotas
- yt-dlp is failing with "Sign in to confirm you're not a bot" errors

### When NOT to Use YouTube API:
- yt-dlp works fine in your environment (default, no setup needed)
- You want to avoid external dependencies
- You prefer metadata-based approach

---

## Setup Instructions (Only if Needed)

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Sign in with your Google account (`contact.iodevz@gmail.com`)
3. Click **"Select a project"** → **"New Project"**
4. Project name: `djwala-ai` (or any name)
5. Click **"Create"**

### 2. Enable YouTube Data API v3

1. In the Cloud Console, go to **"APIs & Services"** → **"Library"**
2. Search for **"YouTube Data API v3"**
3. Click on it, then click **"Enable"**

### 3. Create API Key

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"Create Credentials"** → **"API key"**
3. Copy the generated API key (looks like: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)
4. (Optional) Click **"Restrict key"** for security:
   - Under "API restrictions", select "Restrict key"
   - Choose "YouTube Data API v3"
   - Click "Save"

### 4. Add API Key to Fly.io

```bash
# Set the secret in Fly.io (replace YOUR_API_KEY)
flyctl secrets set DJWALA_YOUTUBE_API_KEY="YOUR_API_KEY" --app djwala-ai

# Verify secret was set
flyctl secrets list --app djwala-ai
```

### 5. Deploy to Fly.io

```bash
# Deploy the updated code
flyctl deploy --app djwala-ai

# Monitor deployment
flyctl logs --app djwala-ai
```

### 6. Test Public Access

```bash
# Test the API from anywhere (no authentication needed)
curl -X POST https://djwala-ai.fly.dev/session \
  -H "Content-Type: application/json" \
  -d '{"mode": "vibe", "query": "deep house chill"}'
```

You should get a response with `session_id` and `status: "searching"`.

---

## Cost & Quota

- **Free tier:** 10,000 requests/day
- **Search request:** 1 query = 100 quota units
- **Daily capacity:** ~100 searches/day (sufficient for most users)
- **Cost after free tier:** $0.05 per 1,000 quota units (very affordable)

### Quota Management

To monitor usage:
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **"APIs & Services"** → **"Quotas"**
3. Search for "YouTube Data API v3"
4. View usage graphs

---

## Testing Without API Key

DjwalaAI works out of the box without any API key:

```bash
# 1. Start the server (no API key needed)
cd /Users/ashishkshirsagar/Projects/djwalaAI
uvicorn djwala.main:app --reload

# 2. Test in browser
# Open http://localhost:8000
# Create a session with any query (e.g., "deep house chill")
# Should work fine using yt-dlp
```

---

## Fallback Behavior

DjwalaAI automatically handles failures:

1. **Primary:** Tries yt-dlp first (no API key needed)
2. **If yt-dlp fails:** Automatically tries YouTube API (if API key is set)
3. **If both fail:** Returns appropriate error message

This ensures maximum reliability without requiring API keys by default.

---

## Troubleshooting

### "YouTube API request failed"

**Cause:** Invalid API key or quota exceeded

**Solution:**
1. Verify API key is correct: `flyctl secrets list --app djwala-ai`
2. Check quota in Google Cloud Console
3. Ensure "YouTube Data API v3" is enabled

### "Could not analyze any tracks"

**Cause:** API key not set or network issues

**Solution:**
1. Verify secret is set: `flyctl secrets list --app djwala-ai`
2. Check logs: `flyctl logs --app djwala-ai`
3. Restart app: `flyctl apps restart djwala-ai`

### Quota Exceeded

**Cause:** Used more than 10,000 requests/day

**Solutions:**
1. Wait 24 hours for quota reset (resets at midnight Pacific Time)
2. Request quota increase in Google Cloud Console (usually approved instantly)
3. Implement caching (already done in DjwalaAI)

---

## Security Best Practices

1. **Restrict API key** to YouTube Data API v3 only (in Google Cloud Console)
2. **Never commit** API keys to git
3. **Use environment variables** (Fly.io secrets) for production
4. **Monitor usage** regularly to detect abuse

---

## Alternative: Invidious API

If you want to avoid Google APIs entirely, consider using Invidious:

- Self-hosted YouTube frontend
- No API key required
- May have rate limits or availability issues
- See `src/djwala/youtube_api.py` for integration example

**Note:** As of now, public Invidious instances are heavily rate-limited, so YouTube Data API v3 is the recommended approach.

---

## Next Steps

Once you've set up the API key:

1. ✅ **Deploy to Fly.io** — API key is automatically picked up
2. ✅ **Test public access** — Anyone can use the app without authentication
3. ✅ **Monitor quota** — Check usage in Google Cloud Console
4. 🚀 **Share your app** — `https://djwala-ai.fly.dev/`

---

## Questions?

If you encounter issues:
1. Check Fly.io logs: `flyctl logs --app djwala-ai`
2. Verify API key: `flyctl secrets list --app djwala-ai`
3. Test locally with the API key to isolate issues
