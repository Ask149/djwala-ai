"""Tests for YouTube search service."""

import pytest
from unittest.mock import patch, MagicMock
from djwala.youtube import YouTubeSearch
from djwala.models import InputMode


class TestQueryBuilding:
    """Test that correct search queries are generated."""

    def test_artist_queries(self):
        yt = YouTubeSearch()
        queries = yt.build_queries(InputMode.ARTISTS, "Rufus Du Sol, Bob Moses")
        assert len(queries) >= 2
        assert any("rufus du sol" in q.lower() for q in queries)
        assert any("bob moses" in q.lower() for q in queries)


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
