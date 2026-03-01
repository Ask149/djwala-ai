"""Audio analyzer — extracts DJ parameters from audio."""

from __future__ import annotations

import os
import tempfile

import librosa
import numpy as np

from djwala.models import TrackAnalysis, TrackInfo

# Key name lookup: chroma index → key name
KEY_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Camelot wheel mapping: (key_name, mode) → camelot code
# mode: "major" or "minor"
CAMELOT_WHEEL = {
    ("C", "major"): "8B", ("A", "minor"): "8A",
    ("G", "major"): "9B", ("E", "minor"): "9A",
    ("D", "major"): "10B", ("B", "minor"): "10A",
    ("A", "major"): "11B", ("F#", "minor"): "11A",
    ("E", "major"): "12B", ("C#", "minor"): "12A",
    ("B", "major"): "1B", ("G#", "minor"): "1A",
    ("F#", "major"): "2B", ("D#", "minor"): "2A",
    ("Gb", "major"): "2B", ("Eb", "minor"): "2A",
    ("Db", "major"): "3B", ("Bb", "minor"): "3A",
    ("Ab", "major"): "4B", ("F", "minor"): "4A",
    ("Eb", "major"): "5B", ("C", "minor"): "5A",
    ("Bb", "major"): "6B", ("G", "minor"): "6A",
    ("F", "major"): "7B", ("D", "minor"): "7A",
}


class AudioAnalyzer:
    """Extracts DJ-relevant parameters from audio."""

    def __init__(self, tmp_dir: str | None = None):
        self._tmp_dir = tmp_dir or tempfile.mkdtemp(prefix="djwala_")

    def analyze(self, track: TrackInfo) -> TrackAnalysis:
        """Download audio from YouTube and analyze it."""
        audio_path = self._download_audio(track.video_id)
        try:
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
            return self._analyze_audio(y, sr, track)
        finally:
            # Clean up downloaded audio
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def estimate(self, track: TrackInfo) -> TrackAnalysis:
        """Return estimated DJ parameters when audio download is unavailable.
        
        Used as fallback when YouTube blocks downloads (e.g., from datacenter IPs).
        Returns conservative estimates that allow the DJ brain to still order tracks
        and plan crossfades, though transitions will be less optimal than with real analysis.
        """
        duration = track.duration or 240.0
        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=duration,
            bpm=120.0,                    # Center of Bollywood/pop range (~90-150 BPM)
            key="Am",                     # Arbitrary minor key
            camelot="8A",                 # Corresponds to A minor
            energy_curve=[0.5] * int(duration),  # Flat normalized energy
            mix_in_point=0.0,             # Start from beginning
            mix_out_point=max(0.0, duration - 16.0),  # Standard 16s fadeout window
        )

    def _download_audio(self, video_id: str) -> str:
        """Download audio from YouTube video, return path to audio file."""
        import yt_dlp

        output_path = os.path.join(self._tmp_dir, f"{video_id}.%(ext)s")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            # Spoof user agent to appear as mobile browser
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Sec-Fetch-Mode": "navigate",
            },
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
        }
        
        # Add cookies if available (helps bypass YouTube bot detection)
        # Check multiple possible cookie locations
        cookie_paths = [
            "/data/youtube-cookies.txt",  # Production (Fly.io volume)
            os.path.expanduser("~/.config/djwala/youtube-cookies.txt"),  # User config
            "youtube-cookies.txt",  # Current directory
        ]
        for cookie_path in cookie_paths:
            if os.path.exists(cookie_path):
                opts["cookiefile"] = cookie_path
                break

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

        wav_path = os.path.join(self._tmp_dir, f"{video_id}.wav")
        if not os.path.exists(wav_path):
            # Try common extensions
            for ext in ["m4a", "webm", "mp3", "opus"]:
                p = os.path.join(self._tmp_dir, f"{video_id}.{ext}")
                if os.path.exists(p):
                    return p
            raise FileNotFoundError(f"Downloaded audio not found for {video_id}")
        return wav_path

    def _analyze_audio(self, y: np.ndarray, sr: int, track: TrackInfo) -> TrackAnalysis:
        """Run all analysis on loaded audio."""
        bpm = self._detect_bpm(y, sr)
        key, camelot = self._detect_key(y, sr)
        energy_curve = self._compute_energy_curve(y, sr)
        mix_in = self._find_mix_in(energy_curve)
        mix_out = self._find_mix_out(energy_curve, track.duration)

        return TrackAnalysis(
            video_id=track.video_id,
            title=track.title,
            duration=track.duration,
            bpm=bpm,
            key=key,
            camelot=camelot,
            energy_curve=energy_curve,
            mix_in_point=mix_in,
            mix_out_point=mix_out,
        )

    def _detect_bpm(self, y: np.ndarray, sr: int) -> float:
        """Detect BPM using librosa beat tracking.

        Applies half-time correction: if detected tempo is below 80 BPM,
        it's likely a half-tempo detection (common with Bollywood, pop,
        and syncopated rhythms). In DJ music, sub-80 BPM is extremely rare,
        so doubling gives the correct tempo.
        """
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0])
        bpm = float(tempo)
        # Half-time correction: DJ music is almost never below 80 BPM
        if bpm < 80.0:
            bpm *= 2.0
        return round(bpm, 1)

    def _detect_key(self, y: np.ndarray, sr: int) -> tuple[str, str]:
        """Detect musical key using chroma features."""
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        # Find the strongest pitch class
        key_idx = int(np.argmax(chroma_avg))
        key_name = KEY_NAMES[key_idx]

        # Simple major/minor detection using the relative minor relationship
        # Compare energy of major third vs minor third
        major_third = chroma_avg[(key_idx + 4) % 12]
        minor_third = chroma_avg[(key_idx + 3) % 12]

        if minor_third > major_third:
            mode = "minor"
            key_str = f"{key_name}m"
        else:
            mode = "major"
            key_str = key_name

        camelot = CAMELOT_WHEEL.get((key_name, mode), "1A")

        return key_str, camelot

    def _compute_energy_curve(self, y: np.ndarray, sr: int) -> list[float]:
        """Compute per-second RMS energy."""
        duration_sec = len(y) // sr
        hop_length = sr  # one value per second
        rms = librosa.feature.rms(y=y, frame_length=sr, hop_length=hop_length)[0]
        # Truncate to exact number of whole seconds
        rms = rms[:duration_sec]
        # Normalize to 0-1
        max_rms = rms.max() if rms.max() > 0 else 1.0
        normalized = (rms / max_rms).tolist()
        return [round(v, 3) for v in normalized]

    def _find_mix_in(self, energy_curve: list[float]) -> float:
        """Find optimal point to start playing this track (skip silence/quiet intro)."""
        threshold = 0.1
        for i, energy in enumerate(energy_curve):
            if energy > threshold:
                return max(0.0, float(i) - 1.0)  # start 1 second before
        return 0.0

    def _find_mix_out(self, energy_curve: list[float], duration: float) -> float:
        """Find optimal point to start fading out (where energy drops near end)."""
        if not energy_curve:
            return max(0.0, duration - 16.0)

        # Look at last 30% of the track
        start_idx = int(len(energy_curve) * 0.7)
        avg_energy = sum(energy_curve[start_idx:]) / max(1, len(energy_curve) - start_idx)

        # Find where energy drops below 70% of the ending average
        threshold = avg_energy * 0.7
        for i in range(start_idx, len(energy_curve)):
            if energy_curve[i] < threshold:
                return float(i)

        # Fallback: 16 seconds before end
        return max(0.0, duration - 16.0)
