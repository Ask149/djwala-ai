"""YouTube search using official Google API (no auth required for search)."""

from __future__ import annotations

import os
from typing import Optional

import requests

from djwala.models import TrackInfo


class YouTubeAPISearch:
    """Search YouTube using official API v3 (requires API key)."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DJWALA_YOUTUBE_API_KEY")
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    def search(self, query: str, max_results: int = 20) -> list[TrackInfo]:
        """Search YouTube videos using official API."""
        if not self.api_key:
            raise ValueError(
                "YouTube API key required. Set DJWALA_YOUTUBE_API_KEY environment variable. "
                "Get free key at https://console.cloud.google.com (10K requests/day free)"
            )
        
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoCategoryId": "10",  # Music category
            "maxResults": min(max_results, 50),  # API limit is 50
            "key": self.api_key,
        }
        
        try:
            response = requests.get(f"{self.base_url}/search", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Get video details (duration) in batch
            video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
            if not video_ids:
                return []
            
            # Fetch durations
            details_params = {
                "part": "contentDetails",
                "id": ",".join(video_ids),
                "key": self.api_key,
            }
            details_response = requests.get(
                f"{self.base_url}/videos", params=details_params, timeout=10
            )
            details_response.raise_for_status()
            details_data = details_response.json()
            
            # Build duration map
            durations = {}
            for item in details_data.get("items", []):
                video_id = item["id"]
                duration_str = item["contentDetails"]["duration"]  # Format: PT4M13S
                durations[video_id] = self._parse_duration(duration_str)
            
            # Convert to TrackInfo
            tracks = []
            for item in data.get("items", []):
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]
                
                track = TrackInfo(
                    video_id=video_id,
                    title=snippet["title"],
                    duration=durations.get(video_id, 0),
                    channel=snippet.get("channelTitle", ""),
                )
                
                # Filter out too short/long videos
                if 60 <= track.duration <= 600:  # 1-10 minutes
                    tracks.append(track)
            
            return tracks
        
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"YouTube API request failed: {e}")
    
    def get_playlist_items(self, playlist_id: str, exclude_id: str = "", max_results: int = 50) -> list[TrackInfo]:
        """Get items from a YouTube playlist (e.g., RD{videoId} for Mix)."""
        if not self.api_key:
            raise ValueError(
                "YouTube API key required. Set DJWALA_YOUTUBE_API_KEY environment variable."
            )

        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(max_results, 50),
            "key": self.api_key,
        }

        response = requests.get(f"{self.base_url}/playlistItems", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        video_ids = []
        snippets = {}
        for item in data.get("items", []):
            vid = item["snippet"]["resourceId"]["videoId"]
            if vid == exclude_id:
                continue
            video_ids.append(vid)
            snippets[vid] = item["snippet"]

        if not video_ids:
            return []

        # Batch fetch durations
        details_params = {
            "part": "contentDetails",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }
        details = requests.get(f"{self.base_url}/videos", params=details_params, timeout=10)
        details.raise_for_status()

        durations = {}
        for item in details.json().get("items", []):
            durations[item["id"]] = self._parse_duration(item["contentDetails"]["duration"])

        tracks = []
        for vid in video_ids:
            duration = durations.get(vid, 0)
            if duration < 60 or duration > 600:
                continue
            snippet = snippets[vid]
            tracks.append(TrackInfo(
                video_id=vid,
                title=snippet["title"],
                duration=float(duration),
                channel=snippet.get("channelTitle", ""),
            ))

        return tracks
    
    @staticmethod
    def _parse_duration(duration_str: str) -> int:
        """Parse ISO 8601 duration (PT4M13S) to seconds."""
        import re
        
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds
