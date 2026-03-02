# Song Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add "Song" mode — user enters a song name, plays it first, then queues endless related songs from YouTube Mix playlists.

**Architecture:** New `InputMode.SONG` triggers a different search path: find the seed song → extract YouTube Mix playlist (`RD{videoId}`) → DJ Brain orders related tracks. Rolling queue fetches more as tracks run out. Backend trims old tracks to prevent memory bloat.

**Tech Stack:** Python (FastAPI, yt-dlp), YouTube Data API v3, vanilla JS frontend

---

### Task 1: Add InputMode.SONG to models.py

**Files:**
- Modify: `src/djwala/models.py:9-10`
- Test: `tests/test_youtube.py` (existing tests still pass)

**Step 1: Add SONG enum value**

```python
class InputMode(str, Enum):
    ARTISTS = "artists"
    SONG = "song"
```

**Step 2: Run existing tests to verify no breakage**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/ -v --tb=short`
Expected: All 111 tests PASS

**Step 3: Commit**

```bash
git add src/djwala/models.py
git commit -m "feat: add InputMode.SONG enum value"
```

---

### Task 2: Add get_playlist_items() to youtube_api.py

**Files:**
- Modify: `src/djwala/youtube_api.py`
- Test: `tests/test_youtube.py`

**Step 1: Write the failing test**

Add to `tests/test_youtube.py`:

```python
from djwala.youtube_api import YouTubeAPISearch


class TestYouTubeAPIPlaylistItems:
    """Test YouTubeAPISearch.get_playlist_items() for mix playlists."""

    def test_get_playlist_items_returns_tracks(self):
        """get_playlist_items extracts tracks from a playlist, excluding seed."""
        api = YouTubeAPISearch(api_key="fake-key")

        mock_playlist_response = MagicMock()
        mock_playlist_response.status_code = 200
        mock_playlist_response.json.return_value = {
            "items": [
                {"snippet": {"resourceId": {"videoId": "seed1"}, "title": "Seed Song", "channelTitle": "Ch1"}},
                {"snippet": {"resourceId": {"videoId": "rel1"}, "title": "Related 1", "channelTitle": "Ch2"}},
                {"snippet": {"resourceId": {"videoId": "rel2"}, "title": "Related 2", "channelTitle": "Ch3"}},
            ]
        }

        mock_details_response = MagicMock()
        mock_details_response.status_code = 200
        mock_details_response.json.return_value = {
            "items": [
                {"id": "rel1", "contentDetails": {"duration": "PT3M30S"}},
                {"id": "rel2", "contentDetails": {"duration": "PT4M15S"}},
            ]
        }

        with patch("djwala.youtube_api.requests.get", side_effect=[mock_playlist_response, mock_details_response]):
            tracks = api.get_playlist_items("RDseed1", exclude_id="seed1")

        assert len(tracks) == 2
        assert tracks[0].video_id == "rel1"
        assert tracks[0].title == "Related 1"
        assert tracks[0].duration == 210.0
        assert tracks[1].video_id == "rel2"

    def test_get_playlist_items_filters_short_tracks(self):
        """get_playlist_items skips tracks shorter than 60 seconds."""
        api = YouTubeAPISearch(api_key="fake-key")

        mock_playlist_response = MagicMock()
        mock_playlist_response.status_code = 200
        mock_playlist_response.json.return_value = {
            "items": [
                {"snippet": {"resourceId": {"videoId": "short1"}, "title": "Short Clip", "channelTitle": "Ch"}},
            ]
        }

        mock_details_response = MagicMock()
        mock_details_response.status_code = 200
        mock_details_response.json.return_value = {
            "items": [
                {"id": "short1", "contentDetails": {"duration": "PT30S"}},
            ]
        }

        with patch("djwala.youtube_api.requests.get", side_effect=[mock_playlist_response, mock_details_response]):
            tracks = api.get_playlist_items("RDxyz", exclude_id="xyz")

        assert len(tracks) == 0

    def test_get_playlist_items_no_key_raises(self):
        """get_playlist_items raises ValueError without API key."""
        api = YouTubeAPISearch(api_key=None)
        with pytest.raises(ValueError, match="API key required"):
            api.get_playlist_items("RDxyz")
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/test_youtube.py::TestYouTubeAPIPlaylistItems -v`
Expected: FAIL — `AttributeError: 'YouTubeAPISearch' object has no attribute 'get_playlist_items'`

**Step 3: Write the implementation**

Add to `src/djwala/youtube_api.py` (after the `search` method, before `_parse_duration`):

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/test_youtube.py::TestYouTubeAPIPlaylistItems -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/djwala/youtube_api.py tests/test_youtube.py
git commit -m "feat: add get_playlist_items to YouTubeAPISearch for mix playlists"
```

---

### Task 3: Add search_song() and get_mix_playlist() to youtube.py

**Files:**
- Modify: `src/djwala/youtube.py`
- Test: `tests/test_youtube.py`

**Step 1: Write the failing tests**

Add to `tests/test_youtube.py`:

```python
class TestSearchSong:
    """Test search_song() — find a specific song."""

    def test_search_song_returns_top_result(self):
        yt = YouTubeSearch()
        mock_result = {
            'entries': [
                {'id': 'abc', 'title': 'Tum Hi Ho Full Song', 'duration': 280, 'channel': 'T-Series'},
            ]
        }
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MagicMock()
            MockYDL.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            MockYDL.return_value.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.return_value = mock_result

            track = yt.search_song("Tum Hi Ho")

        assert track is not None
        assert track.video_id == "abc"
        assert track.title == "Tum Hi Ho Full Song"

    def test_search_song_returns_none_when_no_results(self):
        yt = YouTubeSearch()
        mock_result = {'entries': []}
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MagicMock()
            MockYDL.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            MockYDL.return_value.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.return_value = mock_result

            track = yt.search_song("nonexistent song xyz123")

        assert track is None

    def test_search_song_skips_compilations(self):
        yt = YouTubeSearch()
        mock_result = {
            'entries': [
                {'id': 'comp', 'title': 'Non Stop Bollywood Party Mix', 'duration': 500, 'channel': 'DJ'},
                {'id': 'real', 'title': 'Tum Hi Ho - Arijit Singh', 'duration': 280, 'channel': 'T-Series'},
            ]
        }
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MagicMock()
            MockYDL.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            MockYDL.return_value.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.return_value = mock_result

            track = yt.search_song("Tum Hi Ho")

        assert track is not None
        assert track.video_id == "real"

    def test_search_song_falls_back_to_api(self):
        """When yt-dlp fails, search_song uses API fallback."""
        yt = YouTubeSearch(api_key=None)

        mock_api = MagicMock()
        mock_api.search.return_value = [
            TrackInfo(video_id="api1", title="API Song", duration=200.0, channel="Ch"),
        ]

        with patch("yt_dlp.YoutubeDL", side_effect=Exception("blocked")):
            with patch("djwala.youtube.YouTubeAPISearch", return_value=mock_api):
                track = yt.search_song("some song", api_key="user-key")

        assert track is not None
        assert track.video_id == "api1"


class TestGetMixPlaylist:
    """Test get_mix_playlist() — extract YouTube Mix playlist."""

    def test_get_mix_playlist_returns_related_tracks(self):
        yt = YouTubeSearch()
        mock_result = {
            'entries': [
                {'id': 'seed1', 'title': 'Seed Song', 'duration': 280, 'channel': 'Ch'},
                {'id': 'rel1', 'title': 'Related 1', 'duration': 240, 'channel': 'Ch'},
                {'id': 'rel2', 'title': 'Related 2', 'duration': 200, 'channel': 'Ch'},
            ]
        }
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MagicMock()
            MockYDL.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            MockYDL.return_value.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.return_value = mock_result

            tracks = yt.get_mix_playlist("seed1")

        assert len(tracks) == 2
        assert tracks[0].video_id == "rel1"
        assert tracks[1].video_id == "rel2"

    def test_get_mix_playlist_excludes_seed(self):
        yt = YouTubeSearch()
        mock_result = {
            'entries': [
                {'id': 'seed1', 'title': 'Seed', 'duration': 280, 'channel': 'Ch'},
            ]
        }
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MagicMock()
            MockYDL.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            MockYDL.return_value.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.return_value = mock_result

            tracks = yt.get_mix_playlist("seed1")

        assert len(tracks) == 0

    def test_get_mix_playlist_lenient_on_missing_duration(self):
        """Mix playlist entries without duration get a 240s default."""
        yt = YouTubeSearch()
        mock_result = {
            'entries': [
                {'id': 'nodur', 'title': 'No Duration Track', 'channel': 'Ch'},
            ]
        }
        with patch("yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MagicMock()
            MockYDL.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            MockYDL.return_value.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.return_value = mock_result

            tracks = yt.get_mix_playlist("seed1")

        assert len(tracks) == 1
        assert tracks[0].duration == 240.0

    def test_get_mix_playlist_returns_empty_on_failure(self):
        """get_mix_playlist returns [] on total failure (graceful degradation)."""
        yt = YouTubeSearch(api_key=None)

        with patch("yt_dlp.YoutubeDL", side_effect=Exception("blocked")):
            tracks = yt.get_mix_playlist("seed1")

        assert tracks == []
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/test_youtube.py::TestSearchSong tests/test_youtube.py::TestGetMixPlaylist -v`
Expected: FAIL — `AttributeError: 'YouTubeSearch' object has no attribute 'search_song'`

**Step 3: Write the implementation**

Add to `src/djwala/youtube.py` (after the `search` method):

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/test_youtube.py -v`
Expected: All tests PASS (old + new)

**Step 5: Commit**

```bash
git add src/djwala/youtube.py tests/test_youtube.py
git commit -m "feat: add search_song and get_mix_playlist to YouTubeSearch"
```

---

### Task 4: Update session.py — Song mode queue, rolling, cleanup

**Files:**
- Modify: `src/djwala/session.py`
- Test: `tests/test_integration.py`, `tests/test_api.py`

**Step 1: Write the failing tests**

Add to `tests/test_integration.py`:

```python
class TestSongModeIntegration:
    """Test song mode: seed + mix playlist → ordered queue."""

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_song_mode_seed_first(self, MockCache, MockAnalyzer, MockYT):
        """Song mode: seed song is always first in queue."""
        mock_yt = MockYT.return_value
        mock_yt.search_song.return_value = TrackInfo("seed1", "Seed Song", 280, "Ch")
        mock_yt.get_mix_playlist.return_value = [
            TrackInfo("rel1", "Related 1", 240, "Ch"),
            TrackInfo("rel2", "Related 2", 200, "Ch"),
            TrackInfo("rel3", "Related 3", 260, "Ch"),
            TrackInfo("rel4", "Related 4", 220, "Ch"),
        ]

        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze.side_effect = [
            _mock_analysis("seed1", 120.0, "8A"),
            _mock_analysis("rel1", 122.0, "8B"),
            _mock_analysis("rel2", 118.0, "7A"),
            _mock_analysis("rel3", 124.0, "9A"),
            _mock_analysis("rel4", 126.0, "9B"),
        ]

        mock_cache = MockCache.return_value
        mock_cache.has.return_value = False

        manager = SessionManager()
        session = manager.create_session(InputMode.SONG, "Tum Hi Ho")
        await manager.build_queue(session.session_id)

        session = manager.get_session(session.session_id)
        assert session.status.value == "ready"
        assert session.queue[0].video_id == "seed1"  # Seed is ALWAYS first
        assert len(session.queue) == 5

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_song_mode_no_song_found(self, MockCache, MockAnalyzer, MockYT):
        """Song mode: error when seed song not found."""
        mock_yt = MockYT.return_value
        mock_yt.search_song.return_value = None

        mock_cache = MockCache.return_value

        manager = SessionManager()
        session = manager.create_session(InputMode.SONG, "nonexistent xyz")
        await manager.build_queue(session.session_id)

        session = manager.get_session(session.session_id)
        assert session.status.value == "error"
        assert "not found" in session.error.lower()

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_song_mode_empty_mix_playlist(self, MockCache, MockAnalyzer, MockYT):
        """Song mode: works with seed only if mix playlist is empty."""
        mock_yt = MockYT.return_value
        mock_yt.search_song.return_value = TrackInfo("seed1", "Lonely Song", 280, "Ch")
        mock_yt.get_mix_playlist.return_value = []

        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze.return_value = _mock_analysis("seed1", 120.0, "8A")

        mock_cache = MockCache.return_value
        mock_cache.has.return_value = False

        manager = SessionManager()
        session = manager.create_session(InputMode.SONG, "Lonely Song")
        await manager.build_queue(session.session_id)

        session = manager.get_session(session.session_id)
        assert session.status.value == "ready"
        assert len(session.queue) == 1
        assert session.queue[0].video_id == "seed1"
```

Add to `tests/test_api.py`:

```python
@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_song_mode(mock_build, client):
    """POST /session accepts mode: 'song'."""
    resp = await client.post("/session", json={
        "mode": "song",
        "query": "Tum Hi Ho",
    })
    assert resp.status_code == 200
    data = resp.json()
    session = manager.get_session(data["session_id"])
    assert session.mode.value == "song"
```

Add to a new section in `tests/test_integration.py` for cleanup:

```python
class TestQueueCleanup:
    """Test advance() trims old tracks."""

    def test_advance_trims_old_tracks(self):
        """After advancing past 3 tracks, old ones are trimmed."""
        manager = SessionManager()
        session = manager.create_session(InputMode.ARTISTS, "test")
        session.queue = [_mock_analysis(f"v{i}", 120.0, "8A") for i in range(10)]
        session.current_index = 0

        # Advance 5 times
        for _ in range(5):
            manager.advance(session.session_id)

        # After 5 advances: current_index was 5, trim should have happened
        # current_index > 3 triggers trim: trim = current_index - 3
        # Queue should be shorter, current_index adjusted
        assert session.current_index <= 3
        assert len(session.queue) < 10
        # Current track should still be accessible
        assert session.queue[session.current_index] is not None
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/test_integration.py::TestSongModeIntegration tests/test_integration.py::TestQueueCleanup tests/test_api.py::test_create_session_song_mode -v`
Expected: FAIL

**Step 3: Write the implementation**

Modify `src/djwala/session.py`:

**3a. Add `seen_ids` to Session dataclass:**

```python
@dataclass
class Session:
    session_id: str
    mode: InputMode
    query: str
    status: SessionStatus = SessionStatus.SEARCHING
    candidates: list[TrackInfo] = field(default_factory=list)
    queue: list[TrackAnalysis] = field(default_factory=list)
    current_index: int = 0
    error: str = ""
    youtube_api_key: str | None = None
    mix_length: int = 50
    seen_ids: set[str] = field(default_factory=set)
```

**3b. Extract `_analyze_track` helper (DRY):**

```python
    async def _analyze_track(self, track: TrackInfo, mix_length: int) -> TrackAnalysis:
        """Analyze a single track, using cache or falling back to estimates."""
        if self._cache.has(track.video_id):
            return self._cache.get(track.video_id)
        try:
            analysis = await asyncio.to_thread(self._analyzer.analyze, track)
            self._cache.store(analysis)
            return analysis
        except Exception:
            logger.warning("Analysis failed for %s, using estimates", track.video_id)
            return self._analyzer.estimate(track, mix_length=mix_length)
```

**3c. Update `build_queue` to handle song mode:**

Replace the `build_queue` method body with:

```python
    async def build_queue(self, session_id: str) -> None:
        """Search YouTube, analyze tracks, build ordered queue."""
        session = self._sessions.get(session_id)
        if not session:
            return

        if session.mode == InputMode.SONG:
            await self._build_song_queue(session)
        else:
            await self._build_artists_queue(session)
```

Extract current `build_queue` logic into `_build_artists_queue(self, session)` — same code, just moved into a new method. Then add:

```python
    async def _build_song_queue(self, session: Session) -> None:
        """Build queue for song mode: seed + YouTube Mix playlist."""
        try:
            # Step 1: Find the seed song
            session.status = SessionStatus.SEARCHING
            seed = await asyncio.to_thread(
                self._youtube.search_song, session.query,
                api_key=session.youtube_api_key,
            )
            if not seed:
                session.status = SessionStatus.ERROR
                session.error = "Song not found. Try a different search term."
                return

            session.seen_ids.add(seed.video_id)

            # Step 2: Get related songs from YouTube Mix playlist
            mix_tracks = await asyncio.to_thread(
                self._youtube.get_mix_playlist, seed.video_id,
                api_key=session.youtube_api_key,
            )
            for t in mix_tracks:
                if t.video_id not in session.seen_ids:
                    session.seen_ids.add(t.video_id)
                    session.candidates.append(t)

            # Step 3: Analyze seed + first batch
            session.status = SessionStatus.ANALYZING
            seed_analysis = await self._analyze_track(seed, session.mix_length)

            batch = session.candidates[:4]
            analyzed = []
            for track in batch:
                analysis = await self._analyze_track(track, session.mix_length)
                analyzed.append(analysis)

            # Step 4: Seed first, DJ Brain orders the rest
            session.queue = [seed_analysis] + self._brain.order_playlist(analyzed)
            session.status = SessionStatus.READY

        except Exception as e:
            session.status = SessionStatus.ERROR
            session.error = str(e)
```

**3d. Update `advance` with cleanup:**

```python
    def advance(self, session_id: str) -> None:
        """Move to the next track. Trims old tracks if queue grows."""
        session = self._sessions.get(session_id)
        if not session or session.current_index + 1 >= len(session.queue):
            return
        session.current_index += 1

        # Cleanup: keep at most 3 played tracks behind current
        if session.current_index > 3:
            trim = session.current_index - 3
            session.queue = session.queue[trim:]
            session.current_index -= trim
```

**3e. Update `analyze_more` with rolling fetch:**

Add at the end of the existing `analyze_more` method:

```python
        # Rolling queue: fetch more related tracks when running low (song mode)
        if session.mode == InputMode.SONG:
            upcoming = len(session.queue) - session.current_index - 1
            if upcoming < 5 and session.queue:
                last_vid = session.queue[-1].video_id
                try:
                    new_tracks = await asyncio.to_thread(
                        self._youtube.get_mix_playlist, last_vid,
                        api_key=session.youtube_api_key,
                    )
                    for t in new_tracks:
                        if t.video_id not in session.seen_ids:
                            session.seen_ids.add(t.video_id)
                            analysis = await self._analyze_track(t, session.mix_length)
                            played = session.queue[:session.current_index + 1]
                            future = session.queue[session.current_index + 1:] + [analysis]
                            future_ordered = self._brain.order_playlist(future)
                            session.queue = played + future_ordered
                except Exception:
                    logger.warning("Failed to fetch more tracks for rolling queue")
```

**Step 4: Run all tests**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS (old + new)

**Step 5: Commit**

```bash
git add src/djwala/session.py tests/test_integration.py tests/test_api.py
git commit -m "feat: song mode queue building, rolling fetch, and cleanup"
```

---

### Task 5: Frontend — Mode toggle UI

**Files:**
- Modify: `static/index.html`
- Modify: `static/css/style.css`
- Modify: `static/js/app.js`

**Step 1: Add toggle HTML to index.html**

After line 16 (`<div class="search-row">`), add the mode toggle BEFORE the search row. The input-section should become:

```html
<div class="input-section">
    <div class="mode-toggle">
        <button class="mode-btn active" data-mode="artists">Artists</button>
        <button class="mode-btn" data-mode="song">Song</button>
    </div>
    <div class="search-row">
        <input type="text" class="search-input" placeholder="Artist names, comma separated... (e.g., &quot;Arijit Singh, Pritam, AP Dhillon&quot;)">
        <button class="go-btn">DJ!</button>
    </div>
    <div class="artist-chips"></div>
</div>
```

Bump cache from `?v=9` to `?v=10` on all three asset references (css, mix-engine.js, app.js).

**Step 2: Add toggle CSS to style.css**

Add after the `.input-section` styles:

```css
/* Mode toggle */
.mode-toggle {
    display: flex;
    gap: 0;
    margin-bottom: 0.75rem;
}

.mode-btn {
    padding: 0.4rem 1.2rem;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: transparent;
    color: rgba(255, 255, 255, 0.45);
    cursor: pointer;
    font-size: 0.85rem;
    font-family: inherit;
    transition: all 0.2s;
}

.mode-btn:first-child {
    border-radius: 6px 0 0 6px;
}

.mode-btn:last-child {
    border-radius: 0 6px 6px 0;
    border-left: none;
}

.mode-btn.active {
    background: rgba(139, 92, 246, 0.25);
    color: #fff;
    border-color: rgba(139, 92, 246, 0.5);
}

.mode-btn:hover:not(.active) {
    background: rgba(255, 255, 255, 0.05);
    color: rgba(255, 255, 255, 0.7);
}
```

**Step 3: Update app.js — wire toggle and mode switching**

Add to element refs in `constructor()`:

```javascript
modeToggle: document.querySelector('.mode-toggle'),
modeBtns: document.querySelectorAll('.mode-btn'),
```

Add to `bindEvents()`:

```javascript
this.els.modeBtns.forEach(btn => {
    btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
});
```

Add new method:

```javascript
setMode(mode) {
    this.mode = mode;
    this.els.modeBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    if (mode === 'song') {
        this.els.searchInput.placeholder = 'Enter a song name... (e.g., "Tum Hi Ho", "Blinding Lights")';
    } else {
        this.els.searchInput.placeholder = 'Artist names, comma separated... (e.g., "Arijit Singh, Pritam, AP Dhillon")';
    }
}
```

In `startSession()`, change the artist chips logic to handle both modes:

```javascript
async startSession() {
    const query = this.els.searchInput.value.trim();
    if (!query) return;

    if (this.mode === 'artists') {
        const artists = this.parseArtists(query);
        this.showArtistChips(artists);
    } else {
        this.showArtistChips([query]);  // Show song name as single chip
    }
    // ... rest unchanged
}
```

**Step 4: Verify manually in browser (or run backend tests)**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add static/index.html static/css/style.css static/js/app.js
git commit -m "feat: add Artists/Song mode toggle UI with placeholder switching"
```

---

### Task 6: Deploy and verify

**Step 1: Run full test suite**

Run: `cd /Users/ashishkshirsagar/Projects/djwalaAI && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 2: Deploy to Fly.io**

```bash
cd /Users/ashishkshirsagar/Projects/djwalaAI && fly deploy
```

**Step 3: Verify deployment**

1. Open https://djwala-ai.fly.dev
2. Verify mode toggle visible (Artists selected by default)
3. Click "Song" — placeholder changes
4. Type "Tum Hi Ho" and click DJ!
5. Verify queue shows the seed song first, then related songs
6. Click play — music starts
7. Wait for crossfade or skip — next song should be a different related song (not another Tum Hi Ho)
8. Switch back to "Artists" mode, type "Arijit Singh, Pritam" — verify old behavior unchanged

**Step 4: Commit deploy docs**

```bash
git add docs/plans/
git commit -m "docs: add song mode design and implementation plan"
```
