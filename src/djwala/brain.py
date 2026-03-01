"""DJ Brain — playlist ordering, mix decisions, crossfade logic."""

from __future__ import annotations

from djwala.models import TrackAnalysis, MixCommand


class DJBrain:
    """Core DJ intelligence: ordering, compatibility, mix decisions."""

    BPM_TOLERANCE = 0.06  # 6% BPM difference allowed

    def keys_compatible(self, camelot_a: str, camelot_b: str) -> bool:
        """Check if two Camelot keys are harmonically compatible.

        Compatible = same key, adjacent numbers (same letter), or
        same number (different letter, i.e., relative major/minor).
        """
        num_a, letter_a = int(camelot_a[:-1]), camelot_a[-1]
        num_b, letter_b = int(camelot_b[:-1]), camelot_b[-1]

        # Same key
        if camelot_a == camelot_b:
            return True

        # Same number, different letter (relative major/minor)
        if num_a == num_b:
            return True

        # Adjacent numbers, same letter (wrapping 12 → 1)
        if letter_a == letter_b:
            diff = abs(num_a - num_b)
            if diff == 1 or diff == 11:  # 11 = wrapping (12→1 or 1→12)
                return True

        return False

    def bpm_compatible(self, bpm_a: float, bpm_b: float) -> bool:
        """Check if two BPMs are close enough to mix."""
        if bpm_a == 0 or bpm_b == 0:
            return True  # unknown BPM, allow it
        ratio = abs(bpm_a - bpm_b) / min(bpm_a, bpm_b)
        return ratio <= self.BPM_TOLERANCE

    def order_playlist(self, tracks: list[TrackAnalysis]) -> list[TrackAnalysis]:
        """Order tracks for smooth DJ flow.

        Strategy:
        1. Sort by BPM (gradual progression)
        2. Within BPM clusters, prefer Camelot-compatible neighbors
        3. Shape energy arc (build up, peak, wind down)
        """
        if len(tracks) <= 1:
            return tracks

        # Start with BPM sort
        sorted_tracks = sorted(tracks, key=lambda t: t.bpm)

        # Greedy reorder: pick next track that's BPM-close AND key-compatible
        ordered = [sorted_tracks.pop(0)]
        while sorted_tracks:
            current = ordered[-1]
            best_idx = 0
            best_score = float("inf")

            for i, candidate in enumerate(sorted_tracks):
                score = self._transition_score(current, candidate)
                if score < best_score:
                    best_score = score
                    best_idx = i

            ordered.append(sorted_tracks.pop(best_idx))

        return ordered

    def _transition_score(self, current: TrackAnalysis, candidate: TrackAnalysis) -> float:
        """Score how well candidate follows current. Lower = better."""
        # BPM difference (normalized)
        bpm_diff = abs(current.bpm - candidate.bpm) / max(current.bpm, 1)

        # Key compatibility bonus
        key_penalty = 0.0 if self.keys_compatible(current.camelot, candidate.camelot) else 0.5

        # Energy continuity (prefer gradual change)
        current_energy = sum(current.energy_curve) / max(len(current.energy_curve), 1)
        candidate_energy = sum(candidate.energy_curve) / max(len(candidate.energy_curve), 1)
        energy_diff = abs(current_energy - candidate_energy)

        return bpm_diff + key_penalty + energy_diff * 0.3

    def crossfade_duration(self, outgoing: TrackAnalysis, incoming: TrackAnalysis) -> float:
        """Calculate crossfade duration based on energy and BPM."""
        avg_energy_out = sum(outgoing.energy_curve) / max(len(outgoing.energy_curve), 1)
        avg_energy_in = sum(incoming.energy_curve) / max(len(incoming.energy_curve), 1)
        avg_energy = (avg_energy_out + avg_energy_in) / 2

        avg_bpm = (outgoing.bpm + incoming.bpm) / 2

        # High energy + high BPM = shorter crossfade
        # Low energy + low BPM = longer crossfade
        if avg_energy > 0.6 or avg_bpm > 135:
            return 8.0
        elif avg_energy < 0.35 or avg_bpm < 115:
            return 18.0
        else:
            return 14.0

    def plan_mix(self, outgoing: TrackAnalysis, incoming: TrackAnalysis) -> MixCommand:
        """Plan the mix transition between two tracks."""
        fade_duration = self.crossfade_duration(outgoing, incoming)

        return MixCommand(
            action="fade_to_next",
            current_fade_start=outgoing.mix_out_point,
            next_video_id=incoming.video_id,
            next_seek_to=incoming.mix_in_point,
            fade_duration=fade_duration,
            next_title=incoming.title,
        )
