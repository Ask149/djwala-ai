"""YouTube search service using yt-dlp."""

from __future__ import annotations

import os
from typing import Optional

import yt_dlp

from djwala.models import TrackInfo, InputMode

# Import YouTube API search (optional fallback)
try:
    from djwala.youtube_api import YouTubeAPISearch
    _API_AVAILABLE = True
except ImportError:
    _API_AVAILABLE = False

# Diverse query suffixes — genre-aware.
# EDM/Western: "official music video", "original mix", "artist single"
# Bollywood/Desi: "full song", "lyrical video", "official audio"
_QUERY_SUFFIXES_DEFAULT = [
    "official music video",
    "original mix",
    "full song",
]

_QUERY_SUFFIXES_DESI = [
    "full video song",
    "lyrical video",
    "official audio",
]

# Keywords that hint at Bollywood/Desi content in the query
_DESI_HINTS = {
    "bollywood", "hindi", "punjabi", "desi", "bhangra", "sufi",
    "arijit", "pritam", "ap dhillon", "badshah", "neha kakkar",
    "shreya ghoshal", "atif aslam", "vishal mishra", "jubin nautiyal",
    "anirudh", "ar rahman", "a.r. rahman",
}

# Mood preset search queries — each mood maps to YouTube search terms
MOOD_PRESETS = {
    "house-party": ["house party hits", "club bangers 2024"],
    "road-trip": ["road trip songs", "driving music hits"],
    "late-night": ["late night r&b", "midnight vibes"],
    "chill-vibes": ["chill lofi beats", "relaxing music"],
    "workout": ["workout music", "gym motivation songs"],
    "bollywood": ["bollywood party songs", "hindi hits"],
    "hip-hop": ["hip hop hits 2024", "rap bangers"],
    "latin": ["reggaeton hits", "latin party music"],
}

# Min/max duration for a single track (seconds)
MIN_DURATION = 60
MAX_DURATION = 600


class YouTubeSearch:
    """Search YouTube for tracks using yt-dlp."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional YouTube API key for improved reliability."""
        self.api_key = api_key or os.getenv("DJWALA_YOUTUBE_API_KEY")
        self._api_search = None
        
        # Initialize API search if key is available
        if self.api_key and _API_AVAILABLE:
            try:
                self._api_search = YouTubeAPISearch(self.api_key)
            except Exception:
                # Fall back to yt-dlp if API initialization fails
                self._api_search = None

    @staticmethod
    def _is_desi_query(query: str) -> bool:
        """Check if the query likely refers to Bollywood/Desi music."""
        query_lower = query.lower()
        return any(hint in query_lower for hint in _DESI_HINTS)

    @staticmethod
    def _get_suffixes(query: str) -> list[str]:
        """Return appropriate query suffixes based on genre detection."""
        if YouTubeSearch._is_desi_query(query):
            return _QUERY_SUFFIXES_DESI
        return _QUERY_SUFFIXES_DEFAULT

    def build_queries(self, mode: InputMode, query: str) -> list[str]:
        """Build search queries based on mode and input."""
        if mode == InputMode.MOOD:
            preset = MOOD_PRESETS.get(query)
            if preset:
                return list(preset)
            return [query]  # fallback: use raw query
        artists = [a.strip() for a in query.split(",") if a.strip()]
        suffixes = self._get_suffixes(query)
        queries = []
        for artist in artists:
            artist_suffixes = self._get_suffixes(artist) if self._is_desi_query(artist) else suffixes
            for suffix in artist_suffixes:
                queries.append(f"{artist} {suffix}")
        return queries

    def search(
        self, mode: InputMode, query: str, max_results: int = 20, api_key: str | None = None,
    ) -> list[TrackInfo]:
        """Search YouTube and return candidate tracks."""
        queries = self.build_queries(mode, query)
        try:
            return self._search_with_ytdlp(queries, query, max_results)
        except Exception as e:
            # Try user-provided key first
            if api_key and _API_AVAILABLE:
                try:
                    api_search = YouTubeAPISearch(api_key)
                    return self._search_with_api_instance(api_search, queries, max_results)
                except Exception:
                    pass
            # Then try server key
            if self._api_search:
                try:
                    return self._search_with_api_instance(self._api_search, queries, max_results)
                except Exception:
                    pass
            raise
    
    def search_song(self, query: str, api_key: str | None = None) -> TrackInfo | None:
        """Search YouTube for a specific song, return the best match."""
        try:
            return self._search_song_ytdlp(query)
        except Exception:
            # Try user-provided key
            if api_key and _API_AVAILABLE:
                try:
                    api = YouTubeAPISearch(api_key)
                    results = api.search(query, max_results=3)
                    return results[0] if results else None
                except Exception:
                    pass
            # Try server key
            if self._api_search:
                try:
                    results = self._api_search.search(query, max_results=3)
                    return results[0] if results else None
                except Exception:
                    pass
            return None

    def _search_song_ytdlp(self, query: str) -> TrackInfo | None:
        """Search for a single song via yt-dlp. Returns first valid result."""
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch3:{query}", download=False)
            for entry in result.get('entries', []):
                if entry:
                    track = self._parse_entry(entry)
                    if track:
                        return track
        return None

    def get_mix_playlist(self, video_id: str, api_key: str | None = None) -> list[TrackInfo]:
        """Get related songs from YouTube Mix playlist (RD{video_id})."""
        try:
            return self._get_mix_playlist_ytdlp(video_id)
        except Exception:
            # Try API fallback
            if api_key and _API_AVAILABLE:
                try:
                    api = YouTubeAPISearch(api_key)
                    return api.get_playlist_items(f"RD{video_id}", exclude_id=video_id)
                except Exception:
                    pass
            if self._api_search:
                try:
                    return self._api_search.get_playlist_items(f"RD{video_id}", exclude_id=video_id)
                except Exception:
                    pass
            return []  # Graceful degradation

    def _get_mix_playlist_ytdlp(self, video_id: str) -> list[TrackInfo]:
        """Extract YouTube Mix playlist via yt-dlp."""
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
        tracks = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
            result = ydl.extract_info(url, download=False)
            for entry in result.get('entries', []):
                if not entry or entry.get('id') == video_id:
                    continue
                track = self._parse_entry(entry)
                if not track and entry.get('id') and entry.get('title'):
                    # Lenient: accept mix playlist tracks with unknown duration
                    track = TrackInfo(
                        video_id=entry['id'],
                        title=entry['title'],
                        duration=240.0,
                        channel=entry.get('channel', '') or entry.get('uploader', ''),
                    )
                if track:
                    tracks.append(track)
        return tracks
    
    def _search_with_api(self, queries: list[str], max_results: int) -> list[TrackInfo]:
        """Search using YouTube Data API v3 (server key)."""
        return self._search_with_api_instance(self._api_search, queries, max_results)

    def _search_with_api_instance(self, api_search, queries: list[str], max_results: int) -> list[TrackInfo]:
        """Search using a specific YouTubeAPISearch instance."""
        seen_ids: set[str] = set()
        tracks: list[TrackInfo] = []

        per_query = max(5, max_results // len(queries))

        for q in queries:
            if len(tracks) >= max_results:
                break

            try:
                results = api_search.search(q, max_results=per_query)
                for track in results:
                    if track.video_id in seen_ids:
                        continue
                    seen_ids.add(track.video_id)

                    # Skip compilations
                    if not self._is_compilation(track.title):
                        tracks.append(track)
            except Exception:
                continue

        return tracks[:max_results]
    
    def _search_with_ytdlp(
        self, queries: list[str], query: str, max_results: int
    ) -> list[TrackInfo]:
        """Search using yt-dlp (fallback method, may be blocked in production)."""
        seen_ids: set[str] = set()
        tracks: list[TrackInfo] = []

        # Cap per-query to ensure fair distribution across artists
        num_artists = len([a.strip() for a in query.split(",") if a.strip()])
        per_artist = max(3, max_results // max(num_artists, 1))
        per_query = max(8, per_artist * 2)  # fetch extra to account for filtering

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        for q in queries:
            if len(tracks) >= max_results:
                break

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(f"ytsearch{per_query}:{q}", download=False)
                    for entry in result.get('entries', []):
                        if not entry:
                            continue
                        video_id = entry.get('id', '')
                        if video_id in seen_ids:
                            continue
                        seen_ids.add(video_id)
                        track = self._parse_entry(entry)
                        if track:
                            tracks.append(track)
            except Exception:
                continue

        return tracks[:max_results]

    def _parse_entry(self, entry: dict) -> TrackInfo | None:
        """Parse a yt-dlp entry dict into TrackInfo. Returns None if invalid."""
        video_id = entry.get('id', '')
        title = entry.get('title', '')
        duration = entry.get('duration')
        channel = entry.get('channel', '') or entry.get('uploader', '')

        if not duration or duration < MIN_DURATION or duration > MAX_DURATION:
            return None

        # Skip compilations, mashups, and non-stop mixes
        if self._is_compilation(title):
            return None

        return TrackInfo(
            video_id=video_id,
            title=title,
            duration=float(duration),
            channel=channel,
        )

    @staticmethod
    def _is_compilation(title: str) -> bool:
        """Check if the title suggests a compilation/mashup rather than a single."""
        title_lower = title.lower()
        compilation_markers = [
            "non stop", "nonstop", "non-stop",
            "mashup", "mega mix", "megamix",
            "jukebox", "back to back", "b2b",
            "best of 20", "top 10", "top 20", "top 50",
            "hits collection", "all songs",
        ]
        return any(marker in title_lower for marker in compilation_markers)
