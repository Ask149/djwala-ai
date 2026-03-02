# Genre-Aware Smart Estimation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the `estimate()` method to return varied, deterministic BPM/key/energy values based on title genre keywords and artist names, making DJ brain ordering work intelligently on production where YouTube blocks audio downloads.

**Architecture:** Pure function enhancement to `analyzer.py`. No external API calls. Three-layer heuristic: (1) genre keywords in title → BPM range, (2) known artist names → narrow range, (3) deterministic hash(video_id) → pick specific value. Keys chosen from common Bollywood keys with weighted distribution. Energy curves shaped based on genre (not flat).

**Tech Stack:** Python stdlib (hashlib for deterministic seeding), existing analyzer.py structure, pytest for TDD.

---

## Task 1: Add Genre Keyword Detection

**Files:**
- Modify: `src/djwala/analyzer.py:52-70` (enhance `estimate()` method)
- Test: `tests/test_analyzer.py` (add new test class)

**Context:**
Currently `estimate()` returns fixed values (BPM=120, Am/8A, flat energy). We'll add genre detection that parses the title for keywords and returns appropriate BPM ranges.

**Step 1: Write failing test for genre detection**

Add to `tests/test_analyzer.py` after the existing `TestEstimate` class:

```python
class TestGenreAwareEstimation:
    """Test that estimate() returns varied values based on genre/artist hints."""
    
    def test_romantic_genre_gets_slower_bpm(self, analyzer):
        """Romantic songs should get BPM in 78-95 range."""
        track = TrackInfo(
            video_id="abc123",
            title="Tum Hi Ho - Romantic Song",
            duration=240.0
        )
        result = analyzer.estimate(track)
        assert 78 <= result.bpm <= 95, f"Romantic BPM should be 78-95, got {result.bpm}"
    
    def test_party_genre_gets_faster_bpm(self, analyzer):
        """Party songs should get BPM in 125-145 range."""
        track = TrackInfo(
            video_id="def456",
            title="Badtameez Dil - Party Song",
            duration=240.0
        )
        result = analyzer.estimate(track)
        assert 125 <= result.bpm <= 145, f"Party BPM should be 125-145, got {result.bpm}"
    
    def test_dance_genre_gets_medium_fast_bpm(self, analyzer):
        """Dance songs should get BPM in 120-140 range."""
        track = TrackInfo(
            video_id="ghi789",
            title="Kar Gayi Chull - Dance Mix",
            duration=240.0
        )
        result = analyzer.estimate(track)
        assert 120 <= result.bpm <= 140, f"Dance BPM should be 120-140, got {result.bpm}"
    
    def test_no_genre_gets_default_range(self, analyzer):
        """Songs with no genre keywords should get BPM in 95-130 range (Bollywood default)."""
        track = TrackInfo(
            video_id="jkl012",
            title="Some Random Song Title",
            duration=240.0
        )
        result = analyzer.estimate(track)
        assert 95 <= result.bpm <= 130, f"Default BPM should be 95-130, got {result.bpm}"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation -v`

Expected: All 4 tests FAIL because `estimate()` always returns BPM=120.0

**Step 3: Add genre detection helper to analyzer.py**

Add this helper method to the `AudioAnalyzer` class (after `estimate()` method):

```python
    def _detect_genre_from_title(self, title: str) -> tuple[int, int]:
        """Detect genre from title keywords and return (min_bpm, max_bpm) range.
        
        Returns BPM range based on genre keywords found in title.
        Searches for keywords in lowercase title to be case-insensitive.
        """
        title_lower = title.lower()
        
        # Genre keyword mappings to BPM ranges
        # Order matters — more specific keywords first
        genre_patterns = [
            # Slow/emotional genres (78-95 BPM)
            (["romantic", "ballad", "sad", "unplugged", "acoustic", "lofi"], (78, 95)),
            # Fast party genres (125-145 BPM)
            (["party", "club", "edm", "remix", "bass boosted", "workout"], (125, 145)),
            # Dance/upbeat (120-140 BPM)
            (["dance", "bhangra", "garba", "dandiya", "folk"], (120, 140)),
            # Hip-hop/rap (85-110 BPM)
            (["hip hop", "rap", "trap", "drill"], (85, 110)),
            # Punjabi/Desi pop (95-120 BPM)
            (["punjabi", "bhangra", "desi"], (95, 120)),
        ]
        
        for keywords, bpm_range in genre_patterns:
            if any(keyword in title_lower for keyword in keywords):
                return bpm_range
        
        # Default Bollywood/pop range (95-130 BPM)
        return (95, 130)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation -v`

Expected: All 4 tests still FAIL because `estimate()` doesn't call the helper yet.

**Step 5: Update estimate() to use genre detection**

Replace the `estimate()` method in `src/djwala/analyzer.py` (lines 52-70) with:

```python
    def estimate(self, track: TrackInfo) -> TrackAnalysis:
        """Return estimated DJ parameters when audio download is unavailable.
        
        Used as fallback when YouTube blocks downloads (e.g., from datacenter IPs).
        Returns genre-aware estimates based on title keywords and artist names,
        with deterministic variation so the DJ brain can still order tracks
        intelligently and plan reasonable crossfades.
        """
        import hashlib
        
        duration = track.duration or 240.0
        
        # Step 1: Detect genre from title → get BPM range
        min_bpm, max_bpm = self._detect_genre_from_title(track.title)
        
        # Step 2: Use hash of video_id as deterministic seed
        # This ensures same track always gets same estimate, but different tracks vary
        hash_int = int(hashlib.md5(track.video_id.encode()).hexdigest(), 16)
        bpm_range = max_bpm - min_bpm
        bpm = min_bpm + (hash_int % (bpm_range + 1))  # +1 to include max_bpm
        bpm = float(bpm)
        
        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=duration,
            bpm=bpm,
            key="Am",                     # Will be enhanced in Task 2
            camelot="8A",                 # Will be enhanced in Task 2
            energy_curve=[0.5] * int(duration),  # Will be enhanced in Task 3
            mix_in_point=0.0,
            mix_out_point=max(0.0, duration - 16.0),
        )
```

**Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation -v`

Expected: All 4 tests PASS. BPMs now vary based on genre keywords.

**Step 7: Run all analyzer tests**

Run: `uv run pytest tests/test_analyzer.py -v`

Expected: All 13 tests pass (9 existing + 4 new).

**Step 8: Commit**

```bash
git add src/djwala/analyzer.py tests/test_analyzer.py
git commit -m "feat: add genre-aware BPM estimation from title keywords"
```

---

## Task 2: Add Artist-Specific BPM Narrowing

**Files:**
- Modify: `src/djwala/analyzer.py` (add artist detection helper)
- Test: `tests/test_analyzer.py` (add tests for artist-specific ranges)

**Context:**
Certain well-known artists have characteristic BPM ranges. If we detect an artist name in the title/channel, we can narrow the BPM range further.

**Step 1: Write failing tests for artist detection**

Add to `tests/test_analyzer.py` in the `TestGenreAwareEstimation` class:

```python
    def test_arijit_singh_gets_slower_range(self, analyzer):
        """Arijit Singh songs should narrow to 80-110 BPM."""
        track = TrackInfo(
            video_id="arijit123",
            title="Tum Hi Ho - Arijit Singh",
            duration=240.0
        )
        result = analyzer.estimate(track)
        assert 80 <= result.bpm <= 110, f"Arijit Singh BPM should be 80-110, got {result.bpm}"
    
    def test_ap_dhillon_gets_punjabi_range(self, analyzer):
        """AP Dhillon songs should narrow to 90-115 BPM (Punjabi hip-hop)."""
        track = TrackInfo(
            video_id="ap123",
            title="Brown Munde - AP Dhillon",
            duration=240.0
        )
        result = analyzer.estimate(track)
        assert 90 <= result.bpm <= 115, f"AP Dhillon BPM should be 90-115, got {result.bpm}"
    
    def test_badshah_gets_hip_hop_range(self, analyzer):
        """Badshah songs should narrow to 85-110 BPM (Desi hip-hop)."""
        track = TrackInfo(
            video_id="badshah123",
            title="Genda Phool - Badshah",
            duration=240.0
        )
        result = analyzer.estimate(track)
        assert 85 <= result.bpm <= 110, f"Badshah BPM should be 85-110, got {result.bpm}"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation::test_arijit -v`

Expected: Test FAILS because artist detection doesn't exist yet.

**Step 3: Add artist detection helper**

Add this method to `AudioAnalyzer` class after `_detect_genre_from_title()`:

```python
    def _narrow_by_artist(self, title: str, min_bpm: int, max_bpm: int) -> tuple[int, int]:
        """Narrow BPM range based on known artist names in title.
        
        If a known artist is detected, returns their characteristic range.
        Otherwise returns the input range unchanged.
        Artist ranges take precedence over genre ranges for better accuracy.
        """
        title_lower = title.lower()
        
        # Artist name → (min_bpm, max_bpm) mappings
        # Common Bollywood/Indian artists with characteristic tempos
        artist_patterns = [
            (["arijit singh", "arijit"], (80, 110)),      # Romantic/melodic
            (["ap dhillon"], (90, 115)),                   # Punjabi hip-hop
            (["badshah"], (85, 110)),                      # Desi hip-hop
            (["yo yo honey singh", "honey singh"], (95, 125)),  # Party/bhangra
            (["guru randhawa"], (95, 120)),                # Punjabi pop
            (["neha kakkar"], (100, 130)),                 # Pop/dance
            (["atif aslam"], (85, 110)),                   # Romantic/slow
            (["shreya ghoshal"], (85, 115)),               # Classical/melodic
            (["jubin nautiyal"], (80, 110)),               # Romantic
            (["pritam"], (95, 130)),                       # Versatile (wide range)
        ]
        
        for keywords, bpm_range in artist_patterns:
            if any(keyword in title_lower for keyword in keywords):
                return bpm_range
        
        # No artist match — return original range
        return (min_bpm, max_bpm)
```

**Step 4: Update estimate() to call artist narrowing**

Update the `estimate()` method (around line 67) to add artist narrowing:

```python
    def estimate(self, track: TrackInfo) -> TrackAnalysis:
        """Return estimated DJ parameters when audio download is unavailable.
        
        Used as fallback when YouTube blocks downloads (e.g., from datacenter IPs).
        Returns genre-aware estimates based on title keywords and artist names,
        with deterministic variation so the DJ brain can still order tracks
        intelligently and plan reasonable crossfades.
        """
        import hashlib
        
        duration = track.duration or 240.0
        
        # Step 1: Detect genre from title → get BPM range
        min_bpm, max_bpm = self._detect_genre_from_title(track.title)
        
        # Step 2: Narrow by artist if detected
        min_bpm, max_bpm = self._narrow_by_artist(track.title, min_bpm, max_bpm)
        
        # Step 3: Use hash of video_id as deterministic seed
        # This ensures same track always gets same estimate, but different tracks vary
        hash_int = int(hashlib.md5(track.video_id.encode()).hexdigest(), 16)
        bpm_range = max_bpm - min_bpm
        bpm = min_bpm + (hash_int % (bpm_range + 1))  # +1 to include max_bpm
        bpm = float(bpm)
        
        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=duration,
            bpm=bpm,
            key="Am",                     # Will be enhanced in Task 3
            camelot="8A",                 # Will be enhanced in Task 3
            energy_curve=[0.5] * int(duration),  # Will be enhanced in Task 4
            mix_in_point=0.0,
            mix_out_point=max(0.0, duration - 16.0),
        )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation -v`

Expected: All 7 tests pass (4 genre + 3 artist).

**Step 6: Run all analyzer tests**

Run: `uv run pytest tests/test_analyzer.py -v`

Expected: All 16 tests pass.

**Step 7: Commit**

```bash
git add src/djwala/analyzer.py tests/test_analyzer.py
git commit -m "feat: narrow BPM estimation by known artist names"
```

---

## Task 3: Add Deterministic Key Selection

**Files:**
- Modify: `src/djwala/analyzer.py` (add key selection logic)
- Test: `tests/test_analyzer.py` (add key variation tests)

**Context:**
Currently all estimates return Am/8A. We'll pick from common Bollywood keys (Am, Cm, Dm, Em, Gm) with weighted distribution using the same deterministic hash.

**Step 1: Write failing tests for key variation**

Add to `tests/test_analyzer.py` in the `TestGenreAwareEstimation` class:

```python
    def test_keys_vary_across_tracks(self, analyzer):
        """Different tracks should get different keys (not all Am)."""
        tracks = [
            TrackInfo(video_id=f"key{i}", title="Test Song", duration=240.0)
            for i in range(10)
        ]
        results = [analyzer.estimate(t) for t in tracks]
        keys = [r.key for r in results]
        
        # At least 2 different keys in 10 tracks
        assert len(set(keys)) >= 2, f"Expected key variation, got: {keys}"
    
    def test_same_track_gets_same_key(self, analyzer):
        """Same video_id should always return same key (deterministic)."""
        track = TrackInfo(video_id="consistent", title="Test", duration=240.0)
        result1 = analyzer.estimate(track)
        result2 = analyzer.estimate(track)
        assert result1.key == result2.key
        assert result1.camelot == result2.camelot
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation::test_keys -v`

Expected: FAIL — all tracks get "Am"

**Step 3: Add key selection helper**

Add this method to `AudioAnalyzer` class after `_narrow_by_artist()`:

```python
    def _pick_key_deterministic(self, video_id: str) -> tuple[str, str]:
        """Pick a musical key deterministically based on video_id hash.
        
        Uses common Bollywood/Indian pop keys with weighted distribution:
        - Minor keys are more common (60% of Bollywood music)
        - Am, Dm, Em are most common minor keys
        - Cm and Gm for darker/emotional tracks
        
        Returns (key_str, camelot_code).
        """
        import hashlib
        
        # Common Bollywood keys with weights (minor keys more common)
        # Format: (key_name, camelot, weight)
        key_pool = [
            ("Am", "8A", 25),   # Most common minor key in Bollywood
            ("Dm", "7A", 20),   # Second most common
            ("Em", "9A", 15),   # Third most common
            ("Cm", "5A", 15),   # Emotional/darker tracks
            ("Gm", "6A", 10),   # Less common
            ("C", "8B", 8),     # Major keys less common
            ("D", "10B", 7),
        ]
        
        # Use hash to deterministically pick from weighted pool
        hash_int = int(hashlib.md5(video_id.encode()).hexdigest(), 16)
        total_weight = sum(weight for _, _, weight in key_pool)
        pick = hash_int % total_weight
        
        cumulative = 0
        for key_name, camelot, weight in key_pool:
            cumulative += weight
            if pick < cumulative:
                return (key_name, camelot)
        
        # Fallback (should never reach here)
        return ("Am", "8A")
```

**Step 4: Update estimate() to use key selection**

Update the return statement in `estimate()` to use the helper:

```python
        # Step 4: Pick key deterministically
        key, camelot = self._pick_key_deterministic(track.video_id)
        
        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=duration,
            bpm=bpm,
            key=key,
            camelot=camelot,
            energy_curve=[0.5] * int(duration),  # Will be enhanced in Task 4
            mix_in_point=0.0,
            mix_out_point=max(0.0, duration - 16.0),
        )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation -v`

Expected: All 9 tests pass.

**Step 6: Run all analyzer tests**

Run: `uv run pytest tests/test_analyzer.py -v`

Expected: All 18 tests pass.

**Step 7: Commit**

```bash
git add src/djwala/analyzer.py tests/test_analyzer.py
git commit -m "feat: add deterministic key selection from common Bollywood keys"
```

---

## Task 4: Add Genre-Based Energy Curve Shaping

**Files:**
- Modify: `src/djwala/analyzer.py` (add energy curve generation)
- Test: `tests/test_analyzer.py` (add energy curve tests)

**Context:**
Currently energy curves are flat `[0.5] * duration`. We'll shape them based on genre — romantic gets gentle arc, party gets high arc, default gets medium arc.

**Step 1: Write failing tests for energy curves**

Add to `tests/test_analyzer.py` in the `TestGenreAwareEstimation` class:

```python
    def test_romantic_gets_low_energy_curve(self, analyzer):
        """Romantic songs should have lower energy values."""
        track = TrackInfo(video_id="rom1", title="Romantic Ballad", duration=240.0)
        result = analyzer.estimate(track)
        avg_energy = sum(result.energy_curve) / len(result.energy_curve)
        # Romantic should average below 0.5
        assert avg_energy < 0.5, f"Romantic avg energy should be < 0.5, got {avg_energy}"
    
    def test_party_gets_high_energy_curve(self, analyzer):
        """Party songs should have higher energy values."""
        track = TrackInfo(video_id="party1", title="Party Anthem", duration=240.0)
        result = analyzer.estimate(track)
        avg_energy = sum(result.energy_curve) / len(result.energy_curve)
        # Party should average above 0.5
        assert avg_energy > 0.5, f"Party avg energy should be > 0.5, got {avg_energy}"
    
    def test_energy_curves_not_flat(self, analyzer):
        """Energy curves should have some variation (not all identical values)."""
        track = TrackInfo(video_id="vary1", title="Test Song", duration=240.0)
        result = analyzer.estimate(track)
        # Should have at least some variation
        unique_values = len(set(result.energy_curve))
        assert unique_values > 1, "Energy curve should vary, not be completely flat"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation::test_.*energy -v`

Expected: All 3 tests FAIL — curves are currently flat at 0.5

**Step 3: Add energy level detection**

Add to `_detect_genre_from_title()` to return energy level. Update signature and return:

```python
    def _detect_genre_from_title(self, title: str) -> tuple[int, int, str]:
        """Detect genre from title keywords and return (min_bpm, max_bpm, energy_level).
        
        Returns BPM range and energy level based on genre keywords found in title.
        Energy levels: "low" (0.25-0.4), "medium" (0.4-0.6), "high" (0.6-0.8)
        """
        title_lower = title.lower()
        
        # Genre keyword mappings to BPM ranges and energy levels
        genre_patterns = [
            # Slow/emotional genres (78-95 BPM, low energy)
            (["romantic", "ballad", "sad", "unplugged", "acoustic", "lofi"], (78, 95, "low")),
            # Fast party genres (125-145 BPM, high energy)
            (["party", "club", "edm", "remix", "bass boosted", "workout"], (125, 145, "high")),
            # Dance/upbeat (120-140 BPM, high energy)
            (["dance", "bhangra", "garba", "dandiya", "folk"], (120, 140, "high")),
            # Hip-hop/rap (85-110 BPM, medium energy)
            (["hip hop", "rap", "trap", "drill"], (85, 110, "medium")),
            # Punjabi/Desi pop (95-120 BPM, medium energy)
            (["punjabi", "bhangra", "desi"], (95, 120, "medium")),
        ]
        
        for keywords, (min_bpm, max_bpm, energy) in genre_patterns:
            if any(keyword in title_lower for keyword in keywords):
                return (min_bpm, max_bpm, energy)
        
        # Default Bollywood/pop range (95-130 BPM, medium energy)
        return (95, 130, "medium")
```

**Step 4: Add energy curve generation helper**

Add this method to `AudioAnalyzer` class:

```python
    def _generate_energy_curve(self, duration: int, energy_level: str, video_id: str) -> list[float]:
        """Generate a shaped energy curve based on energy level.
        
        Creates a curved profile instead of flat line:
        - "low": gentle arc peaking at 0.35 (romantic/ballad)
        - "medium": moderate arc peaking at 0.5 (pop/hip-hop)
        - "high": pronounced arc peaking at 0.7 (party/dance)
        
        Uses deterministic variation based on video_id for intro/outro variation.
        """
        import hashlib
        import math
        
        # Base energy levels (peak values)
        energy_peaks = {
            "low": 0.35,
            "medium": 0.5,
            "high": 0.7,
        }
        peak = energy_peaks.get(energy_level, 0.5)
        
        # Generate arc shape: starts low, peaks in middle, falls at end
        curve = []
        for i in range(duration):
            # Sine-based arc from 0 to π
            position = i / max(1, duration - 1)  # 0.0 to 1.0
            arc_value = math.sin(position * math.pi)  # Smooth arc
            
            # Scale by peak energy level
            energy = arc_value * peak
            
            # Add small deterministic variation (±0.05) to avoid perfect uniformity
            hash_int = int(hashlib.md5(f"{video_id}{i}".encode()).hexdigest(), 16)
            variation = (hash_int % 11 - 5) / 100.0  # -0.05 to +0.05
            energy = max(0.1, min(1.0, energy + variation))
            
            curve.append(round(energy, 3))
        
        return curve
```

**Step 5: Update estimate() to use energy curve generation**

Update the call to `_detect_genre_from_title()` and energy curve generation:

```python
        # Step 1: Detect genre from title → get BPM range and energy level
        min_bpm, max_bpm, energy_level = self._detect_genre_from_title(track.title)
        
        # ... (existing BPM/key code) ...
        
        # Step 5: Generate shaped energy curve
        energy_curve = self._generate_energy_curve(int(duration), energy_level, track.video_id)
        
        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=duration,
            bpm=bpm,
            key=key,
            camelot=camelot,
            energy_curve=energy_curve,
            mix_in_point=0.0,
            mix_out_point=max(0.0, duration - 16.0),
        )
```

**Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_analyzer.py::TestGenreAwareEstimation -v`

Expected: All 12 tests pass.

**Step 7: Run all analyzer tests**

Run: `uv run pytest tests/test_analyzer.py -v`

Expected: All 21 tests pass.

**Step 8: Commit**

```bash
git add src/djwala/analyzer.py tests/test_analyzer.py
git commit -m "feat: add genre-based energy curve shaping (not flat)"
```

---

## Task 5: Update Existing estimate() Tests

**Files:**
- Modify: `tests/test_analyzer.py` (update old `TestEstimate` tests)

**Context:**
The existing `TestEstimate` class (lines 107-129) tests for fixed BPM=120.0, key=Am, flat energy. Now that estimate() is smart, those assertions are wrong. We need to update them to check for *reasonable* ranges instead of exact values.

**Step 1: Update test_estimate_returns_valid_analysis**

Replace the test at line 108-121:

```python
    def test_estimate_returns_valid_analysis(self, analyzer, sample_track):
        """Test that estimate() returns a valid TrackAnalysis with reasonable values."""
        result = analyzer.estimate(sample_track)
        
        assert result.video_id == sample_track.video_id
        assert result.title == sample_track.title
        assert result.duration == sample_track.duration
        
        # BPM should be in reasonable DJ range (not fixed 120.0)
        assert 78 <= result.bpm <= 145, f"BPM should be in DJ range, got {result.bpm}"
        
        # Key should be valid format
        assert result.key in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
                              "Am", "Cm", "Dm", "Em", "Gm"], f"Invalid key: {result.key}"
        assert result.camelot.endswith(("A", "B")), f"Invalid camelot: {result.camelot}"
        
        # Mix points should be reasonable
        assert result.mix_in_point == 0.0
        assert result.mix_out_point == sample_track.duration - 16.0
        
        # Energy curve should exist and be shaped (not flat)
        assert len(result.energy_curve) == int(sample_track.duration)
        assert all(0.0 <= v <= 1.0 for v in result.energy_curve), "Energy values should be 0-1"
```

**Step 2: Update test_estimate_handles_missing_duration**

The existing test at line 123-129 checks for flat energy `[0.5]`. Update it:

```python
    def test_estimate_handles_missing_duration(self, analyzer):
        """Test that estimate() handles tracks with no duration set."""
        track = TrackInfo(video_id="test", title="Test", duration=0.0)
        result = analyzer.estimate(track)
        
        assert result.duration == 240.0  # Default fallback
        assert result.mix_out_point == 224.0  # 240 - 16
        assert len(result.energy_curve) == 240  # Should match duration
        assert all(0.0 <= v <= 1.0 for v in result.energy_curve)
```

**Step 3: Run all analyzer tests**

Run: `uv run pytest tests/test_analyzer.py -v`

Expected: All tests pass (21 total).

**Step 4: Commit**

```bash
git add tests/test_analyzer.py
git commit -m "test: update estimate() tests for smart variation"
```

---

## Task 6: Integration Test and Verification

**Files:**
- Test: Run full test suite
- Verify: Manual spot-check with real queries

**Step 1: Run full test suite**

Run: `uv run pytest --tb=short -q`

Expected: All 81+ tests pass (76 existing + 5 new from earlier session + 12 new from this work = 93 tests)

**Step 2: Manual verification with local server**

Start server:
```bash
uv run uvicorn djwala.main:app --host 0.0.0.0 --port 8001 --reload
```

Create a test session:
```bash
curl -X POST http://localhost:8001/session \
  -H "Content-Type: application/json" \
  -d '{"mode":"artists","query":"Arijit Singh, AP Dhillon, Badshah"}'
```

Wait 15s, then fetch queue and check BPMs vary:
```bash
curl -s http://localhost:8001/session/<SESSION_ID>/queue | python3 -m json.tool | grep bpm
```

Expected: BPMs should vary (not all 120.0). Arijit tracks in 80-110 range, AP Dhillon in 90-115, Badshah in 85-110.

**Step 3: Push to production**

Push to trigger auto-deploy:
```bash
git push origin main
```

Wait for GitHub Actions deploy to complete (~3 min).

**Step 4: Verify on production**

```bash
curl -X POST https://djwala-ai.fly.dev/session \
  -H "Content-Type: application/json" \
  -d '{"mode":"artists","query":"Arijit Singh, Pritam"}'

# Wait 20s for search + estimation
sleep 20

# Check queue
curl -s https://djwala-ai.fly.dev/session/<SESSION_ID>/queue | python3 -m json.tool | grep -A 2 '"bpm"'
```

Expected: BPMs vary across tracks, keys vary (not all Am/8A), energy curves have different shapes.

**Step 5: Create summary doc (optional)**

Create `docs/estimation-strategy.md` documenting:
- Why we use estimation (YouTube blocks datacenter downloads)
- How genre/artist detection works
- Example BPM ranges by genre/artist
- Deterministic hash strategy
- Energy curve shaping

**Step 6: Final commit if doc created**

```bash
git add docs/estimation-strategy.md
git commit -m "docs: add estimation strategy documentation"
git push origin main
```

---

## Summary

| Task | Description | Files Modified | Tests Added | Est. Time |
|------|-------------|----------------|-------------|-----------|
| 1 | Genre keyword detection | `analyzer.py`, `test_analyzer.py` | 4 | 15 min |
| 2 | Artist-specific narrowing | `analyzer.py`, `test_analyzer.py` | 3 | 15 min |
| 3 | Deterministic key selection | `analyzer.py`, `test_analyzer.py` | 2 | 15 min |
| 4 | Energy curve shaping | `analyzer.py`, `test_analyzer.py` | 3 | 20 min |
| 5 | Update existing tests | `test_analyzer.py` | 0 (updates) | 10 min |
| 6 | Integration verification | None | 0 | 15 min |

**Total: ~90 minutes**

**Impact:** DJ brain ordering will now work intelligently on production. Tracks will vary in BPM (78-145 range), keys (7 options), and energy profiles (low/medium/high arcs), allowing the greedy transition algorithm to find good matches instead of seeing all tracks as identical.

**Commits: 5-6**
1. `feat: add genre-aware BPM estimation from title keywords`
2. `feat: narrow BPM estimation by known artist names`
3. `feat: add deterministic key selection from common Bollywood keys`
4. `feat: add genre-based energy curve shaping (not flat)`
5. `test: update estimate() tests for smart variation`
6. `docs: add estimation strategy documentation` (optional)
