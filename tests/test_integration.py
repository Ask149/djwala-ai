# tests/test_integration.py
"""Integration tests — test component wiring (mocked YouTube/audio)."""

import time
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from djwala.models import InputMode, TrackInfo, TrackAnalysis
from djwala.session import SessionManager


def _mock_analysis(video_id: str, bpm: float, camelot: str) -> TrackAnalysis:
    return TrackAnalysis(
        video_id=video_id,
        title=f"Track {video_id}",
        duration=240.0,
        bpm=bpm,
        key="Am",
        camelot=camelot,
        energy_curve=[0.5] * 240,
        mix_in_point=2.0,
        mix_out_point=224.0,
    )


class TestIntegration:
    """Test the full pipeline with mocked external services."""

    @patch("djwala.session.YouTubeSearch")
    @patch("djwala.session.AudioAnalyzer")
    @patch("djwala.session.AnalysisCache")
    @pytest.mark.asyncio
    async def test_full_session_flow(self, MockCache, MockAnalyzer, MockYT):
        # Setup mocks
        mock_yt = MockYT.return_value
        mock_yt.search.return_value = [
            TrackInfo("vid1", "Track 1", 240, "Ch1"),
            TrackInfo("vid2", "Track 2", 200, "Ch2"),
            TrackInfo("vid3", "Track 3", 260, "Ch3"),
        ]

        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze.side_effect = [
            _mock_analysis("vid1", 124.0, "8A"),
            _mock_analysis("vid2", 126.0, "8B"),
            _mock_analysis("vid3", 128.0, "9A"),
        ]

        mock_cache = MockCache.return_value
        mock_cache.has.return_value = False

        # Run
        manager = SessionManager()
        session = manager.create_session(InputMode.ARTISTS, "Arijit Singh, Deadmau5")
        await manager.build_queue(session.session_id)

        # Verify
        session = manager.get_session(session.session_id)
        assert session.status.value == "ready"
        assert len(session.queue) == 3

        # Verify mix command
        mix_cmd = manager.get_mix_command(session.session_id)
        assert mix_cmd is not None
        assert mix_cmd.action == "fade_to_next"

        # Advance
        manager.advance(session.session_id)
        assert session.current_index == 1


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


# --- OAuth Integration Tests ---

class TestOAuthIntegration:
    """Test full OAuth login → session → /auth/me → playlists → logout flow."""

    @pytest.fixture(autouse=True)
    def setup_oauth(self, tmp_path):
        """Configure OAuth with test credentials and a temp DB."""
        from djwala.main import app
        from djwala.config import Settings
        from djwala.db import UserDB
        from djwala.auth import init_auth

        self.db_path = str(tmp_path / "test_oauth.db")
        self.test_settings = Settings(
            google_client_id="test-google-id",
            google_client_secret="test-google-secret",
            spotify_client_id="test-spotify-id",
            spotify_client_secret="test-spotify-secret",
            session_secret="test-session-secret-for-signing",
            database_path=self.db_path,
        )
        self.test_db = UserDB(db_path=self.db_path)
        init_auth(self.test_settings, self.test_db)
        self.app = app
        yield
        # Restore original settings (disabled OAuth) after test
        from djwala.main import settings as original_settings, user_db as original_db
        init_auth(original_settings, original_db)

    def _mock_google_token_response(self):
        """Return a mock response for Google token exchange."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "access_token": "google-access-token-123",
            "refresh_token": "google-refresh-token-456",
            "expires_in": 3600,
        }
        return resp

    def _mock_google_profile_response(self):
        """Return a mock response for Google userinfo."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "id": "google-user-42",
            "name": "Test User",
            "email": "test@example.com",
            "picture": "https://example.com/avatar.jpg",
        }
        return resp

    def _mock_spotify_token_response(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "access_token": "spotify-access-token-abc",
            "refresh_token": "spotify-refresh-token-def",
            "expires_in": 3600,
        }
        return resp

    def _mock_spotify_profile_response(self, is_premium=True):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "id": "spotify-user-99",
            "display_name": "DJ Test",
            "images": [{"url": "https://example.com/spotify-avatar.jpg"}],
            "product": "premium" if is_premium else "free",
        }
        return resp

    @pytest.mark.asyncio
    @patch("djwala.auth.http_requests")
    async def test_google_login_callback_creates_session(self, mock_http):
        """Google OAuth callback creates user + session + sets cookie."""
        mock_http.post.return_value = self._mock_google_token_response()
        mock_http.get.return_value = self._mock_google_profile_response()

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Get login redirect to extract state
            login_resp = await client.get("/auth/google/login", follow_redirects=False)
            assert login_resp.status_code == 302
            assert "accounts.google.com" in login_resp.headers["location"]

            # Extract the state and oauth_state cookie
            oauth_state_cookie = login_resp.cookies.get("oauth_state")
            assert oauth_state_cookie is not None

            # Step 2: Simulate callback with code and state
            callback_resp = await client.get(
                f"/auth/google/callback?code=test-auth-code&state={oauth_state_cookie}",
                cookies={"oauth_state": oauth_state_cookie},
                follow_redirects=False,
            )
            assert callback_resp.status_code == 302
            assert callback_resp.headers["location"] == "/"

            # Session cookie should be set
            session_cookie = callback_resp.cookies.get("djwala_session")
            assert session_cookie is not None

            # Step 3: /auth/me should return logged-in user
            me_resp = await client.get(
                "/auth/me",
                cookies={"djwala_session": session_cookie},
            )
            assert me_resp.status_code == 200
            data = me_resp.json()
            assert data["logged_in"] is True
            assert data["user"]["display_name"] == "Test User"
            assert data["user"]["has_google"] is True
            assert data["user"]["has_spotify"] is False

    @pytest.mark.asyncio
    @patch("djwala.auth.http_requests")
    async def test_spotify_login_callback_creates_session(self, mock_http):
        """Spotify OAuth callback creates user + session + sets cookie."""
        mock_http.post.return_value = self._mock_spotify_token_response()
        mock_http.get.return_value = self._mock_spotify_profile_response(is_premium=True)

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Get login redirect
            login_resp = await client.get("/auth/spotify/login", follow_redirects=False)
            assert login_resp.status_code == 302
            assert "accounts.spotify.com" in login_resp.headers["location"]

            oauth_state_cookie = login_resp.cookies.get("oauth_state")
            assert oauth_state_cookie is not None

            # Step 2: Simulate callback
            callback_resp = await client.get(
                f"/auth/spotify/callback?code=test-spotify-code&state={oauth_state_cookie}",
                cookies={"oauth_state": oauth_state_cookie},
                follow_redirects=False,
            )
            assert callback_resp.status_code == 302

            session_cookie = callback_resp.cookies.get("djwala_session")
            assert session_cookie is not None

            # Step 3: /auth/me returns Spotify user
            me_resp = await client.get(
                "/auth/me",
                cookies={"djwala_session": session_cookie},
            )
            data = me_resp.json()
            assert data["logged_in"] is True
            assert data["user"]["has_spotify"] is True
            assert data["user"]["spotify_is_premium"] is True
            assert data["user"]["has_google"] is False

    @pytest.mark.asyncio
    @patch("djwala.auth.http_requests")
    async def test_logout_clears_session(self, mock_http):
        """Full flow: login → verify logged in → logout → verify logged out."""
        mock_http.post.return_value = self._mock_google_token_response()
        mock_http.get.return_value = self._mock_google_profile_response()

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login
            login_resp = await client.get("/auth/google/login", follow_redirects=False)
            oauth_state = login_resp.cookies.get("oauth_state")
            callback_resp = await client.get(
                f"/auth/google/callback?code=code&state={oauth_state}",
                cookies={"oauth_state": oauth_state},
                follow_redirects=False,
            )
            session_cookie = callback_resp.cookies.get("djwala_session")

            # Verify logged in
            me_resp = await client.get("/auth/me", cookies={"djwala_session": session_cookie})
            assert me_resp.json()["logged_in"] is True

            # Logout
            logout_resp = await client.get(
                "/auth/logout",
                cookies={"djwala_session": session_cookie},
                follow_redirects=False,
            )
            assert logout_resp.status_code == 302

            # Verify logged out — session should be invalidated server-side
            me_resp2 = await client.get("/auth/me", cookies={"djwala_session": session_cookie})
            assert me_resp2.json()["logged_in"] is False

    @pytest.mark.asyncio
    @patch("djwala.auth.http_requests")
    async def test_playlists_endpoint_with_auth(self, mock_http):
        """Logged-in user can fetch playlists from /api/playlists."""
        # Setup: Create a Google user with tokens
        mock_http.post.return_value = self._mock_google_token_response()
        mock_http.get.return_value = self._mock_google_profile_response()

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login to get session
            login_resp = await client.get("/auth/google/login", follow_redirects=False)
            oauth_state = login_resp.cookies.get("oauth_state")
            callback_resp = await client.get(
                f"/auth/google/callback?code=code&state={oauth_state}",
                cookies={"oauth_state": oauth_state},
                follow_redirects=False,
            )
            session_cookie = callback_resp.cookies.get("djwala_session")

            # Mock YouTube playlist API call
            with patch("djwala.main.fetch_youtube_playlists") as mock_yt_playlists:
                mock_yt_playlists.return_value = [
                    {"id": "PLtest1", "title": "My Favorites", "track_count": 25, "source": "youtube"},
                ]
                playlists_resp = await client.get(
                    "/api/playlists",
                    cookies={"djwala_session": session_cookie},
                )
                assert playlists_resp.status_code == 200
                data = playlists_resp.json()
                assert len(data["playlists"]) > 0
                assert data["playlists"][0]["title"] == "My Favorites"

    @pytest.mark.asyncio
    @patch("djwala.auth.http_requests")
    async def test_google_callback_invalid_state_rejected(self, mock_http):
        """Callback with mismatched state is rejected."""
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            callback_resp = await client.get(
                "/auth/google/callback?code=code&state=bad-state",
                cookies={"oauth_state": "different-state"},
                follow_redirects=False,
            )
            assert callback_resp.status_code == 400

    @pytest.mark.asyncio
    @patch("djwala.auth.http_requests")
    async def test_spotify_search_endpoint_with_auth(self, mock_http):
        """Logged-in Spotify user can search tracks via /api/spotify-search."""
        # Login as Spotify user
        mock_http.post.return_value = self._mock_spotify_token_response()
        mock_http.get.return_value = self._mock_spotify_profile_response(is_premium=True)

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_resp = await client.get("/auth/spotify/login", follow_redirects=False)
            oauth_state = login_resp.cookies.get("oauth_state")
            callback_resp = await client.get(
                f"/auth/spotify/callback?code=code&state={oauth_state}",
                cookies={"oauth_state": oauth_state},
                follow_redirects=False,
            )
            session_cookie = callback_resp.cookies.get("djwala_session")

            # Mock the Spotify search
            with patch("djwala.main.search_spotify_track") as mock_search:
                mock_search.return_value = {
                    "uri": "spotify:track:abc123",
                    "name": "Tum Hi Ho",
                    "artist": "Arijit Singh",
                }
                search_resp = await client.get(
                    "/api/spotify-search?q=Tum+Hi+Ho",
                    cookies={"djwala_session": session_cookie},
                )
                assert search_resp.status_code == 200
                data = search_resp.json()
                assert data["uri"] == "spotify:track:abc123"
