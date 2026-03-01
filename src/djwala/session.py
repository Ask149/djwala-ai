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


class SessionManager:
    """Manages DJ sessions — search, analyze, queue."""

    def __init__(self, database_path: str = "djwala_cache.db", youtube_api_key: str | None = None):
        self._sessions: dict[str, Session] = {}
        self._youtube = YouTubeSearch(api_key=youtube_api_key)
        self._analyzer = AudioAnalyzer()
        self._brain = DJBrain()
        self._cache = AnalysisCache(db_path=database_path)

    def create_session(self, mode: InputMode, query: str) -> Session:
        session_id = str(uuid.uuid4())[:8]
        session = Session(
            session_id=session_id,
            mode=mode,
            query=query,
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

    async def build_queue(self, session_id: str) -> None:
        """Search YouTube, analyze tracks, build ordered queue."""
        session = self._sessions.get(session_id)
        if not session:
            return

        try:
            # Step 1: Search YouTube
            session.status = SessionStatus.SEARCHING
            candidates = await asyncio.to_thread(self._youtube.search, session.mode, session.query)
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
                if self._cache.has(track.video_id):
                    analysis = self._cache.get(track.video_id)
                else:
                    try:
                        analysis = await asyncio.to_thread(
                            self._analyzer.analyze, track
                        )
                        self._cache.store(analysis)
                    except Exception:
                        logger.exception("Analysis failed for %s (%s)", track.video_id, track.title)
                        continue  # skip tracks that fail analysis
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
        """Move to the next track."""
        session = self._sessions.get(session_id)
        if session and session.current_index + 1 < len(session.queue):
            session.current_index += 1

    async def analyze_more(self, session_id: str) -> None:
        """Continue analyzing remaining candidates in the background."""
        session = self._sessions.get(session_id)
        if not session:
            return

        analyzed_ids = {t.video_id for t in session.queue}
        for track in session.candidates:
            if track.video_id in analyzed_ids:
                continue
            if self._cache.has(track.video_id):
                analysis = self._cache.get(track.video_id)
            else:
                try:
                    analysis = await asyncio.to_thread(
                        self._analyzer.analyze, track
                    )
                    self._cache.store(analysis)
                except Exception:
                    logger.exception("Background analysis failed for %s", track.video_id)
                    continue
            # Freeze played + currently-playing tracks; only reorder future portion
            played = session.queue[:session.current_index + 1]
            future = session.queue[session.current_index + 1:] + [analysis]
            future_ordered = self._brain.order_playlist(future)
            session.queue = played + future_ordered
