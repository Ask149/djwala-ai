"""FastAPI application entry point."""

import asyncio
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from djwala.config import Settings
from djwala.session import SessionManager

logger = logging.getLogger(__name__)

# Static directory resolution: prioritize env var, then fallback to relative path
# In production (Docker), DJWALA_STATIC_DIR=/app/static
# In dev (editable install), it resolves from source tree
STATIC_DIR = Path(os.getenv("DJWALA_STATIC_DIR", Path(__file__).resolve().parent.parent.parent / "static"))

settings = Settings()
app = FastAPI(title="DjwalaAI", version="0.1.0")
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = SessionManager(
    database_path=settings.database_path,
    youtube_api_key=settings.youtube_api_key,
)


def _log_task_exception(task: asyncio.Task) -> None:
    """Log unhandled exceptions from background tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Background task %s failed", task.get_name(), exc_info=exc)


class SessionCreate(BaseModel):
    mode: str
    query: str
    youtube_api_key: str | None = None
    mix_length: int = Field(default=50, ge=0, le=100)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    """Serve the main page."""
    from fastapi.responses import FileResponse
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(404, "index.html not found")


@app.post("/session")
@limiter.limit(settings.rate_limit)
async def create_session(request: Request, req: SessionCreate):
    from djwala.models import InputMode
    try:
        mode = InputMode(req.mode)
    except ValueError:
        raise HTTPException(400, f"Invalid mode: {req.mode}")

    session = manager.create_session(mode, req.query, youtube_api_key=req.youtube_api_key, mix_length=req.mix_length)
    # Start building queue in background
    task = asyncio.create_task(
        manager.build_queue(session.session_id),
        name=f"build_queue:{session.session_id}",
    )
    task.add_done_callback(_log_task_exception)

    return {
        "session_id": session.session_id,
        "status": session.status.value,
    }


@app.get("/session/{session_id}/queue")
async def get_queue(session_id: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    tracks = []
    for t in session.queue:
        tracks.append({
            "video_id": t.video_id,
            "title": t.title,
            "bpm": t.bpm,
            "key": t.key,
            "camelot": t.camelot,
            "duration": t.duration,
            "mix_in_point": t.mix_in_point,
            "mix_out_point": t.mix_out_point,
            "energy": round(sum(t.energy_curve) / max(len(t.energy_curve), 1), 2),
        })

    return {
        "session_id": session_id,
        "status": session.status.value,
        "current_index": session.current_index,
        "tracks": tracks,
        "error": session.error,
    }


@app.get("/track/{video_id}")
async def get_track(video_id: str):
    analysis = manager.get_cached_analysis(video_id)
    if not analysis:
        raise HTTPException(404, "Track not analyzed")
    return {
        "video_id": analysis.video_id,
        "title": analysis.title,
        "bpm": analysis.bpm,
        "key": analysis.key,
        "camelot": analysis.camelot,
        "duration": analysis.duration,
        "mix_in_point": analysis.mix_in_point,
        "mix_out_point": analysis.mix_out_point,
    }


@app.websocket("/session/{session_id}/live")
async def websocket_live(websocket: WebSocket, session_id: str):
    session = manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "get_mix_command":
                mix_cmd = manager.get_mix_command(session_id)
                if mix_cmd:
                    await websocket.send_json({
                        "action": mix_cmd.action,
                        "current_fade_start": mix_cmd.current_fade_start,
                        "next_video_id": mix_cmd.next_video_id,
                        "next_seek_to": mix_cmd.next_seek_to,
                        "fade_duration": mix_cmd.fade_duration,
                        "next_title": mix_cmd.next_title,
                    })
                else:
                    await websocket.send_json({"action": "no_more_tracks"})

            elif action == "track_ended":
                manager.advance(session_id)
                # Trigger background analysis of more tracks
                task = asyncio.create_task(
                    manager.analyze_more(session_id),
                    name=f"analyze_more:{session_id}",
                )
                task.add_done_callback(_log_task_exception)
                await websocket.send_json({"action": "advanced"})

            elif action == "request_queue":
                session = manager.get_session(session_id)
                await websocket.send_json({
                    "action": "queue_update",
                    "current_index": session.current_index,
                    "queue_length": len(session.queue),
                })

    except WebSocketDisconnect:
        pass


# Static files must be mounted AFTER API routes to avoid catching API paths
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
