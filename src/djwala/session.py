"""Session manager — orchestrates search, analysis, and mix planning."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum

from djwala.analyzer import AudioAnalyzer
from djwala.brain import DJBrain
from djwala.cache import AnalysisCache
from djwala.models import InputMode, MixCommand, TrackAnalysis, TrackInfo
from djwala.youtube import YouTubeSearch

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    READY = "ready"
    PLAYING = "playing"
    ERROR = "error"


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
    youtube_api_key: str | None = None  # user-provided, in-memory only, never persisted
    mix_length: int = 50
    seen_ids: set[str] = field(default_factory=set)


class SessionManager:
    """Manages DJ sessions — search, analyze, queue."""

    def __init__(self, database_path: str = "djwala_cache.db", youtube_api_key: str | None = None):
        self._sessions: dict[str, Session] = {}
        self._youtube = YouTubeSearch(api_key=youtube_api_key)
        self._analyzer = AudioAnalyzer()
        self._brain = DJBrain()
        self._cache = AnalysisCache(db_path=database_path)

    def create_session(self, mode: InputMode, query: str, youtube_api_key: str | None = None, mix_length: int = 50) -> Session:
        session_id = str(uuid.uuid4())[:8]
        session = Session(
            session_id=session_id,
            mode=mode,
            query=query,
            youtube_api_key=youtube_api_key,
            mix_length=mix_length,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def get_cached_analysis(self, video_id: str) -> TrackAnalysis | None:
        """Get cached analysis for a track, if available."""
        if self._cache.has(video_id):
            return self._cache.get(video_id)
        return None

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

    async def build_queue(self, session_id: str) -> None:
        """Search YouTube, analyze tracks, build ordered queue."""
        session = self._sessions.get(session_id)
        if not session:
            return

        if session.mode == InputMode.SONG:
            await self._build_song_queue(session)
        else:
            await self._build_artists_queue(session)

    async def _build_artists_queue(self, session: Session) -> None:
        """Build queue for artists mode (existing behavior)."""
        try:
            # Step 1: Search YouTube
            session.status = SessionStatus.SEARCHING
            candidates = await asyncio.to_thread(
                self._youtube.search, session.mode, session.query,
                api_key=session.youtube_api_key,
            )
            session.candidates = candidates

            if not candidates:
                session.status = SessionStatus.ERROR
                session.error = "No tracks found"
                return

            # Step 2: Analyze tracks (first batch)
            session.status = SessionStatus.ANALYZING
            analyzed = []
            batch_size = min(5, len(candidates))

            for track in candidates[:batch_size]:
                analysis = await self._analyze_track(track, session.mix_length)
                analyzed.append(analysis)

            if not analyzed:
                session.status = SessionStatus.ERROR
                session.error = "Could not analyze any tracks"
                return

            # Step 3: Order playlist
            session.queue = self._brain.order_playlist(analyzed)
            session.status = SessionStatus.READY

        except Exception as e:
            session.status = SessionStatus.ERROR
            error_msg = str(e)
            if not session.youtube_api_key:
                error_msg += " — Add your YouTube API key in Settings for reliable access."
            session.error = error_msg

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


    def get_mix_command(self, session_id: str) -> MixCommand | None:
        """Get the next mix command for the current position."""
        session = self._sessions.get(session_id)
        if not session or not session.queue:
            return None

        idx = session.current_index
        if idx + 1 >= len(session.queue):
            return None  # no next track

        outgoing = session.queue[idx]
        incoming = session.queue[idx + 1]
        return self._brain.plan_mix(outgoing, incoming)

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

    async def analyze_more(self, session_id: str) -> None:
        """Continue analyzing remaining candidates in the background."""
        session = self._sessions.get(session_id)
        if not session:
            return

        analyzed_ids = {t.video_id for t in session.queue}
        for track in session.candidates:
            if track.video_id in analyzed_ids:
                continue
            analysis = await self._analyze_track(track, session.mix_length)
            # Freeze played + currently-playing tracks; only reorder future portion
            played = session.queue[:session.current_index + 1]
            future = session.queue[session.current_index + 1:] + [analysis]
            future_ordered = self._brain.order_playlist(future)
            session.queue = played + future_ordered

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
