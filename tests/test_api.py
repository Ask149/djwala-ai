"""Tests for the API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient

from djwala.main import app, limiter, manager
from djwala.models import InputMode, TrackAnalysis, TrackInfo
from djwala.session import SessionStatus


@pytest.fixture(autouse=True)
def _clear_sessions():
    """Reset manager state and rate limiter between tests."""
    manager._sessions.clear()
    limiter.reset()
    yield
    manager._sessions.clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session(mock_build, client):
    resp = await client.post("/session", json={
        "mode": "artists",
        "query": "Arijit Singh, Pritam",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "searching"
    # Verify session was registered in the manager
    session = manager.get_session(data["session_id"])
    assert session is not None
    assert session.query == "Arijit Singh, Pritam"


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_with_api_key(mock_build, client):
    """POST /session accepts optional youtube_api_key."""
    resp = await client.post("/session", json={
        "mode": "artists",
        "query": "Arijit Singh",
        "youtube_api_key": "test-key-123",
    })
    assert resp.status_code == 200
    data = resp.json()
    session = manager.get_session(data["session_id"])
    assert session.youtube_api_key == "test-key-123"


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_without_api_key(mock_build, client):
    """POST /session works without youtube_api_key (backward compat)."""
    resp = await client.post("/session", json={
        "mode": "artists",
        "query": "Arijit Singh",
    })
    assert resp.status_code == 200
    data = resp.json()
    session = manager.get_session(data["session_id"])
    assert session.youtube_api_key is None


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_invalid_mode(mock_build, client):
    resp = await client.post("/session", json={
        "mode": "invalid_mode",
        "query": "test",
    })
    assert resp.status_code == 400
    mock_build.assert_not_awaited()


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_get_session_queue(mock_build, client):
    # Create a session first
    resp = await client.post("/session", json={
        "mode": "artists",
        "query": "test",
    })
    session_id = resp.json()["session_id"]

    resp = await client.get(f"/session/{session_id}/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert "tracks" in data
    assert "status" in data
    assert data["session_id"] == session_id
    assert data["tracks"] == []  # No tracks analyzed (build_queue was mocked)
    assert data["current_index"] == 0


async def test_get_nonexistent_session(client):
    resp = await client.get("/session/nonexistent/queue")
    assert resp.status_code == 404


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_with_mix_length(mock_build, client):
    """POST /session accepts optional mix_length."""
    resp = await client.post("/session", json={
        "mode": "artists",
        "query": "Arijit Singh",
        "mix_length": 75,
    })
    assert resp.status_code == 200
    data = resp.json()
    session = manager.get_session(data["session_id"])
    assert session.mix_length == 75


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_default_mix_length(mock_build, client):
    """POST /session defaults mix_length to 50."""
    resp = await client.post("/session", json={
        "mode": "artists",
        "query": "Arijit Singh",
    })
    assert resp.status_code == 200
    data = resp.json()
    session = manager.get_session(data["session_id"])
    assert session.mix_length == 50


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_mix_length_validation(mock_build, client):
    """POST /session rejects mix_length outside 0-100."""
    resp = await client.post("/session", json={
        "mode": "artists",
        "query": "test",
        "mix_length": 150,
    })
    assert resp.status_code == 422  # Pydantic validation error


# --- Helpers and fixtures for WebSocket / session tests ---


def _make_track(video_id: str, bpm: float = 120.0) -> TrackAnalysis:
    """Helper to create a minimal TrackAnalysis for testing."""
    return TrackAnalysis(
        video_id=video_id,
        title=f"Track {video_id}",
        duration=240.0,
        bpm=bpm,
        key="Am",
        camelot="8A",
        energy_curve=[0.5] * 10,
        mix_in_point=2.0,
        mix_out_point=220.0,
    )


@pytest.fixture
def sync_client():
    return TestClient(app)


# --- WebSocket tests ---


def test_websocket_invalid_session(sync_client):
    """WebSocket to nonexistent session should close with 4004."""
    with pytest.raises(Exception):
        with sync_client.websocket_connect("/session/nonexistent/live"):
            pass  # should not reach here


@patch.object(manager, "build_queue", new_callable=AsyncMock)
def test_websocket_get_mix_command(mock_build, sync_client):
    """WebSocket get_mix_command returns fade_to_next when queue has 2+ tracks."""
    session = manager.create_session(InputMode.ARTISTS, "test")
    session.queue = [_make_track("vid1"), _make_track("vid2")]
    session.status = SessionStatus.READY

    with sync_client.websocket_connect(f"/session/{session.session_id}/live") as ws:
        ws.send_json({"action": "get_mix_command"})
        data = ws.receive_json()
        assert data["action"] == "fade_to_next"
        assert data["next_video_id"] == "vid2"
        assert "fade_duration" in data
        assert "current_fade_start" in data


@patch.object(manager, "build_queue", new_callable=AsyncMock)
def test_websocket_no_more_tracks(mock_build, sync_client):
    """WebSocket get_mix_command with single track returns no_more_tracks."""
    session = manager.create_session(InputMode.ARTISTS, "test")
    session.queue = [_make_track("vid1")]
    session.status = SessionStatus.READY

    with sync_client.websocket_connect(f"/session/{session.session_id}/live") as ws:
        ws.send_json({"action": "get_mix_command"})
        data = ws.receive_json()
        assert data["action"] == "no_more_tracks"


@patch.object(manager, "analyze_more", new_callable=AsyncMock)
@patch.object(manager, "build_queue", new_callable=AsyncMock)
def test_websocket_track_ended_advances(mock_build, mock_analyze, sync_client):
    """WebSocket track_ended action advances current_index."""
    session = manager.create_session(InputMode.ARTISTS, "test")
    session.queue = [_make_track("vid1"), _make_track("vid2")]
    session.status = SessionStatus.READY
    assert session.current_index == 0

    with sync_client.websocket_connect(f"/session/{session.session_id}/live") as ws:
        ws.send_json({"action": "track_ended"})
        data = ws.receive_json()
        assert data["action"] == "advanced"

    assert session.current_index == 1


@patch.object(manager, "build_queue", new_callable=AsyncMock)
def test_websocket_request_queue(mock_build, sync_client):
    """WebSocket request_queue returns queue state."""
    session = manager.create_session(InputMode.ARTISTS, "test")
    session.queue = [_make_track("v1"), _make_track("v2"), _make_track("v3")]
    session.status = SessionStatus.READY

    with sync_client.websocket_connect(f"/session/{session.session_id}/live") as ws:
        ws.send_json({"action": "request_queue"})
        data = ws.receive_json()
        assert data["action"] == "queue_update"
        assert data["current_index"] == 0
        assert data["queue_length"] == 3


# --- analyze_more ordering test ---


async def test_analyze_more_preserves_played_tracks():
    """analyze_more should not reorder tracks before current_index."""
    session = manager.create_session(InputMode.ARTISTS, "test ordering")
    t1 = _make_track("vid1", bpm=120.0)
    t2 = _make_track("vid2", bpm=122.0)
    session.queue = [t1, t2]
    session.current_index = 1  # user is on track 2
    session.candidates = [
        TrackInfo(video_id="vid3", title="Track vid3", duration=240.0,
                  channel="Ch"),
    ]

    # Mock analyzer so it doesn't call YouTube
    with patch.object(manager._analyzer, "analyze",
                      return_value=_make_track("vid3", bpm=118.0)):
        with patch.object(manager._cache, "has", return_value=False):
            with patch.object(manager._cache, "store"):
                await manager.analyze_more(session.session_id)

    # Tracks before and at current_index must be unchanged
    assert session.queue[0].video_id == "vid1"
    assert session.queue[1].video_id == "vid2"
    # New track should be appended after current_index
    assert len(session.queue) == 3
    assert session.queue[2].video_id == "vid3"


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


@patch.object(manager, "build_queue", new_callable=AsyncMock)
async def test_create_session_mood(mock_build, client):
    """POST /session accepts mode=mood."""
    resp = await client.post("/session", json={
        "mode": "mood",
        "query": "house-party",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    session = manager.get_session(data["session_id"])
    assert session.mode == InputMode.MOOD
    assert session.query == "house-party"


async def test_analytics_endpoint(client):
    """POST /analytics accepts events and returns 204."""
    resp = await client.post("/analytics", json={
        "event": "mix_start",
        "mode": "artists",
        "query": "Drake, The Weeknd",
    })
    assert resp.status_code == 204


async def test_analytics_minimal_event(client):
    """POST /analytics works with just an event name."""
    resp = await client.post("/analytics", json={"event": "page_view"})
    assert resp.status_code == 204
