"""Google/Spotify API wrappers — profiles, playlists, audio features."""

from __future__ import annotations

import logging
import time

import requests as http_requests

from djwala.models import TrackAnalysis, TrackInfo, spotify_key_to_name, spotify_key_to_camelot

logger = logging.getLogger(__name__)

# --- YouTube / Google ---

YT_PLAYLISTS_URL = "https://www.googleapis.com/youtube/v3/playlists"
YT_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

SPOTIFY_PLAYLISTS_URL = "https://api.spotify.com/v1/me/playlists"
SPOTIFY_PLAYLIST_TRACKS_URL = "https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
SPOTIFY_AUDIO_FEATURES_URL = "https://api.spotify.com/v1/audio-features"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def fetch_youtube_playlists(access_token: str) -> list[dict]:
    """Fetch user's YouTube playlists."""
    resp = http_requests.get(YT_PLAYLISTS_URL, params={
        "mine": "true",
        "part": "snippet,contentDetails",
        "maxResults": 50,
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    playlists = []
    # Add Liked Videos as virtual playlist
    playlists.append({
        "id": "LL",
        "name": "Liked Videos",
        "image_url": None,
        "track_count": 0,
        "source": "youtube",
    })
    for item in items:
        playlists.append({
            "id": item["id"],
            "name": item["snippet"]["title"],
            "image_url": item["snippet"].get("thumbnails", {}).get("default", {}).get("url"),
            "track_count": item["contentDetails"]["itemCount"],
            "source": "youtube",
        })
    return playlists


def fetch_youtube_playlist_tracks(playlist_id: str, access_token: str, max_tracks: int = 50) -> list[TrackInfo]:
    """Fetch tracks from a YouTube playlist."""
    tracks = []
    page_token = None
    while len(tracks) < max_tracks:
        params = {
            "playlistId": playlist_id,
            "part": "snippet,contentDetails",
            "maxResults": min(50, max_tracks - len(tracks)),
        }
        if page_token:
            params["pageToken"] = page_token
        resp = http_requests.get(YT_PLAYLIST_ITEMS_URL, params=params,
                                  headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            video_id = item["contentDetails"]["videoId"]
            title = item["snippet"]["title"]
            # Duration requires a separate videos.list call; use 0 as placeholder
            tracks.append(TrackInfo(video_id=video_id, title=title, duration=0.0,
                                    channel=item["snippet"].get("videoOwnerChannelTitle", "")))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    # Fetch durations in batch
    if tracks:
        video_ids = [t.video_id for t in tracks]
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            resp = http_requests.get(YT_VIDEOS_URL, params={
                "id": ",".join(batch),
                "part": "contentDetails",
            }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
            resp.raise_for_status()
            for vid_item in resp.json().get("items", []):
                vid_id = vid_item["id"]
                duration_iso = vid_item["contentDetails"]["duration"]
                duration_sec = _parse_iso8601_duration(duration_iso)
                for t in tracks:
                    if t.video_id == vid_id:
                        t.duration = duration_sec
                        break

    return tracks


def _parse_iso8601_duration(duration: str) -> float:
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return float(hours * 3600 + minutes * 60 + seconds)


# --- Spotify ---

def fetch_spotify_playlists(access_token: str) -> list[dict]:
    """Fetch user's Spotify playlists."""
    resp = http_requests.get(SPOTIFY_PLAYLISTS_URL, params={
        "limit": 50,
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "image_url": item["images"][0]["url"] if item.get("images") else None,
            "track_count": item["tracks"]["total"],
            "source": "spotify",
        }
        for item in items
    ]


def fetch_spotify_playlist_tracks(playlist_id: str, access_token: str, max_tracks: int = 100) -> list[dict]:
    """Fetch tracks from a Spotify playlist. Returns list of Spotify track objects."""
    url = SPOTIFY_PLAYLIST_TRACKS_URL.format(playlist_id=playlist_id)
    resp = http_requests.get(url, params={
        "limit": min(100, max_tracks),
        "fields": "items(track(id,name,artists,duration_ms,uri)),next",
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    tracks = []
    for item in items:
        track = item.get("track")
        if track and track.get("id"):
            artists = ", ".join(a["name"] for a in track.get("artists", []))
            tracks.append({
                "spotify_id": track["id"],
                "name": track["name"],
                "artists": artists,
                "duration_ms": track["duration_ms"],
                "uri": track.get("uri", ""),
            })
    return tracks


def fetch_spotify_audio_features(track_ids: list[str], access_token: str) -> list[dict]:
    """Fetch audio features for up to 100 Spotify tracks."""
    if not track_ids:
        return []
    resp = http_requests.get(SPOTIFY_AUDIO_FEATURES_URL, params={
        "ids": ",".join(track_ids[:100]),
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    features = resp.json().get("audio_features", [])
    return [f for f in features if f is not None]


def search_spotify_track(query: str, access_token: str) -> dict | None:
    """Search Spotify for a track. Returns first result or None."""
    resp = http_requests.get(SPOTIFY_SEARCH_URL, params={
        "q": query,
        "type": "track",
        "limit": 1,
    }, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("tracks", {}).get("items", [])
    if not items:
        return None
    track = items[0]
    artists = ", ".join(a["name"] for a in track.get("artists", []))
    return {
        "spotify_id": track["id"],
        "name": track["name"],
        "artists": artists,
        "duration_ms": track["duration_ms"],
        "uri": track.get("uri", ""),
    }


def spotify_features_to_analysis(
    features: dict, *, title: str, video_id: str,
    spotify_uri: str = "",
) -> TrackAnalysis:
    """Convert Spotify Audio Features to a TrackAnalysis object."""
    bpm = features.get("tempo", 120.0)
    key_num = features.get("key", -1)
    mode = features.get("mode", 0)
    energy = features.get("energy", 0.5)
    duration_ms = features.get("duration_ms", 240000)
    duration = duration_ms / 1000.0

    key_name = spotify_key_to_name(key_num, mode)
    camelot = spotify_key_to_camelot(key_num, mode)

    # Create flat energy curve (Spotify gives single value, not per-second)
    energy_curve = [round(energy, 3)] * int(duration)

    # Estimate mix points based on energy
    mix_in = 8.0 if energy > 0.5 else 12.0
    mix_out = max(duration - 16.0, mix_in + 30.0)

    return TrackAnalysis(
        video_id=video_id,
        title=title,
        duration=duration,
        bpm=round(bpm, 1),
        key=key_name,
        camelot=camelot,
        energy_curve=energy_curve,
        mix_in_point=round(mix_in, 1),
        mix_out_point=round(mix_out, 1),
    )


# --- Token Refresh ---

def refresh_spotify_token(refresh_token: str, settings) -> tuple[str, int]:
    """Refresh Spotify access token. Returns (new_access_token, expires_at)."""
    resp = http_requests.post(SPOTIFY_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.spotify_client_id,
        "client_secret": settings.spotify_client_secret,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    new_token = data["access_token"]
    expires_at = int(time.time()) + data.get("expires_in", 3600)
    return new_token, expires_at


def refresh_google_token(refresh_token: str, settings) -> tuple[str, int]:
    """Refresh Google access token. Returns (new_access_token, expires_at)."""
    resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    new_token = data["access_token"]
    expires_at = int(time.time()) + data.get("expires_in", 3600)
    return new_token, expires_at
