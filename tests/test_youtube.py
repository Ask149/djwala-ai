"""Tests for YouTube search service."""

import pytest
from unittest.mock import patch, MagicMock
from djwala.youtube import YouTubeSearch
from djwala.youtube_api import YouTubeAPISearch
from djwala.models import InputMode, TrackInfo


class TestQueryBuilding:
    """Test that correct search queries are generated."""

    def test_artist_queries(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Rufus Du Sol, Bob Moses")
        assert len(queries) >= 2
        assert any("rufus du sol" in q.lower() for q in queries)
        assert any("bob moses" in q.lower() for q in queries)

    def test_mood_queries_house_party(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.MOOD, "house-party")
        assert queries == ["house party hits", "club bangers 2024"]

    def test_mood_queries_all_presets_exist(self):
        from djwala.youtube import MOOD_PRESETS
        assert len(MOOD_PRESETS) == 8
        for key, queries in MOOD_PRESETS.items():
            assert isinstance(queries, list)
            assert len(queries) >= 1
            assert all(isinstance(q, str) for q in queries)

    def test_mood_queries_unknown_fallback(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.MOOD, "unknown-mood")
        assert queries == ["unknown-mood"]


class TestResultParsing:
    """Test that yt-dlp results are parsed into TrackInfo."""

    def test_parse_entry(self):
        yt = YouTubeSearch()
        entry = {
            'id': 'abc123',
            'title': 'Artist - Track Name [Deep House]',
            'duration': 245,  # seconds
            'channel': 'Some Channel',
        }
        track = yt._parse_entry(entry)
        assert track.video_id == "abc123"
        assert track.title == "Artist - Track Name [Deep House]"
        assert track.duration == 245.0
        assert track.channel == "Some Channel"

    def test_parse_entry_skips_too_short(self):
        yt = YouTubeSearch()
        entry = {
            'id': 'x',
            'title': 'Short',
            'duration': 30,
            'channel': '',
        }
        track = yt._parse_entry(entry)
        assert track is None  # < 60 seconds = probably not a full song

    def test_parse_entry_skips_too_long(self):
        yt = YouTubeSearch()
        entry = {
            'id': 'x',
            'title': 'Mix',
            'duration': 7200,  # 2 hours
            'channel': '',
        }
        track = yt._parse_entry(entry)
        assert track is None  # > 600 seconds = probably a mix/compilation

    def test_parse_entry_skips_compilation(self):
        yt = YouTubeSearch()
        entry = {
            'id': 'comp1',
            'title': 'Non Stop Holi Dance Party Songs 2025',
            'duration': 500,
            'channel': 'T-Series',
        }
        track = yt._parse_entry(entry)
        assert track is None

    def test_parse_entry_skips_mashup(self):
        yt = YouTubeSearch()
        entry = {
            'id': 'mash1',
            'title': 'Bollywood Mega Mashup 2025 - DJ Shadow',
            'duration': 300,
            'channel': 'DJ Shadow',
        }
        track = yt._parse_entry(entry)
        assert track is None

    def test_parse_entry_allows_normal_title(self):
        yt = YouTubeSearch()
        entry = {
            'id': 'ok1',
            'title': 'Arijit Singh - Tum Hi Ho Full Video Song',
            'duration': 280,
            'channel': 'T-Series',
        }
        track = yt._parse_entry(entry)
        assert track is not None
        assert track.video_id == "ok1"


class TestCompilationFilter:
    """Test _is_compilation filter detects problematic titles."""

    @pytest.mark.parametrize("title", [
        "Non Stop Bollywood Party Songs 2025",
        "Nonstop Dance Hits",
        "Best of 2025 - Bollywood Non-Stop Mix",
        "Top 10 Romantic Songs",
        "Top 50 Dance Hits Playlist",
        "Bollywood Mashup 2025",
        "Mega Mix - Club Hits",
        "Megamix Party Edition",
        "Bollywood Jukebox - Latest Songs",
        "Back To Back Hits 2025",
        "Arijit Singh Hits Collection",
        "All Songs of Pritam",
    ])
    def test_compilation_detected(self, title):
        assert YouTubeSearch._is_compilation(title) is True

    @pytest.mark.parametrize("title", [
        "Arijit Singh - Tum Hi Ho Full Video Song",
        "AP Dhillon - Brown Munde Official Audio",
        "Deadmau5 - Strobe (Original Mix)",
        "The Weeknd - Blinding Lights (Official Music Video)",
        "Dua Lipa - Don't Start Now",
    ])
    def test_compilation_not_detected(self, title):
        assert YouTubeSearch._is_compilation(title) is False


class TestDesiDetection:
    """Test desi/Bollywood query detection and suffix selection."""

    @pytest.mark.parametrize("query,expected", [
        ("bollywood party hits", True),
        ("arijit singh romantic songs", True),
        ("ap dhillon new song", True),
        ("ar rahman best", True),
        ("punjabi bhangra", True),
        ("deep house chill", False),
        ("deadmau5 strobe", False),
        ("edm festival 2025", False),
    ])
    def test_is_desi_query(self, query, expected):
        assert YouTubeSearch._is_desi_query(query) is expected

    def test_desi_query_gets_desi_suffixes(self):
        yt = YouTubeSearch()
        suffixes = yt._get_suffixes("arijit singh romantic")
        assert "full video song" in suffixes or "lyrical video" in suffixes

    def test_non_desi_query_gets_default_suffixes(self):
        yt = YouTubeSearch()
        suffixes = yt._get_suffixes("deep house progressive")
        assert "official music video" in suffixes or "original mix" in suffixes


class TestBollywoodQueries:
    """Test query building for Bollywood-specific scenarios."""

    def test_artists_desi_gets_desi_suffixes(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Arijit Singh, AP Dhillon")
        # Both artists should appear
        assert any("arijit singh" in q.lower() for q in queries)
        assert any("ap dhillon" in q.lower() for q in queries)
        # Should use desi suffixes for both (both are desi hints)
        assert any(
            "full video song" in q or "lyrical video" in q or "official audio" in q
            for q in queries
        )

    def test_artists_mixed_genre(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Arijit Singh, Deadmau5")
        # Arijit should get desi suffixes, Deadmau5 should get default
        arijit_queries = [q for q in queries if "arijit" in q.lower()]
        deadmau5_queries = [q for q in queries if "deadmau5" in q.lower()]
        assert len(arijit_queries) >= 1
        assert len(deadmau5_queries) >= 1


class TestMultiArtistDistribution:
    """Test that multi-artist queries distribute results fairly."""

    def test_build_queries_single_artist(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Arijit Singh")
        # Should have suffix variants for one artist
        assert len(queries) >= 3
        assert all("arijit singh" in q.lower() for q in queries)

    def test_build_queries_three_artists(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Arijit Singh, Pritam, AP Dhillon")
        # Should have queries for all three artists
        arijit = [q for q in queries if "arijit" in q.lower()]
        pritam = [q for q in queries if "pritam" in q.lower()]
        ap = [q for q in queries if "ap dhillon" in q.lower()]
        assert len(arijit) >= 1
        assert len(pritam) >= 1
        assert len(ap) >= 1

    def test_build_queries_whitespace_handling(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "  Arijit Singh ,, , Pritam  ")
        # Should handle extra whitespace and empty entries
        assert any("arijit" in q.lower() for q in queries)
        assert any("pritam" in q.lower() for q in queries)
        # Should NOT have empty artist queries
        assert all(len(q.strip()) > 0 for q in queries)

    def test_build_queries_empty_input(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "")
        assert queries == []

    def test_build_queries_only_commas(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, ",,,")
        assert queries == []


class TestSearchApiKeyFallback:
    """Test that search() uses override api_key when yt-dlp fails."""

    def test_search_uses_override_api_key_on_ytdlp_failure(self):
        """When yt-dlp fails, search should use the override api_key if provided."""
        yt = YouTubeSearch(api_key=None)  # no server key

        mock_api_search = MagicMock()
        mock_api_search.search.return_value = [
            TrackInfo(video_id="abc", title="Test Song", duration=200.0, channel="Ch"),
        ]

        with patch("djwala.youtube.YouTubeAPISearch", return_value=mock_api_search) as mock_cls:
            with patch.object(yt, "_search_with_ytdlp", side_effect=Exception("blocked")):
                results = yt.search(InputMode.ARTISTS, "test artist", api_key="user-key-123")

        mock_cls.assert_called_once_with("user-key-123")
        assert len(results) == 1
        assert results[0].video_id == "abc"


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
