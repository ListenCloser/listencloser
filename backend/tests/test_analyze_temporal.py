"""Tests for temporal analysis features (Analysis V2).

Tests the helper functions _compute_windowed_density, _detect_rests, and
the harmonic rhythm computation in analyze_midi.
"""

from __future__ import annotations

import os
import sys
import tempfile

import pretty_midi

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyze import (
    _compute_beat_relative_density,
    _compute_windowed_density,
    _detect_rests,
    _midi_rhythm,
)

# ── _compute_windowed_density ────────────────────────────────────────────────


class TestWindowedDensity:
    """Tests for explicit seconds- and beat-relative density helpers."""

    def test_sparse_passage_lower_density(self):
        """Sparse onsets (1 per 2s) produce lower density than dense passages."""
        sparse = [0.0, 2.0, 4.0, 6.0, 8.0]
        result = _compute_windowed_density(sparse, 10.0, window=2.0, step=1.0)
        densities = [w["density"] for w in result]
        avg = sum(densities) / len(densities)
        # 1 onset per 2s window = 0.5 events/s average
        assert avg < 1.0

    def test_dense_passage_higher_density(self):
        """Dense onsets (5 per second) produce higher density."""
        dense = [i * 0.2 for i in range(50)]  # 50 onsets in 10s
        result = _compute_windowed_density(dense, 10.0, window=2.0, step=1.0)
        densities = [w["density"] for w in result]
        avg = sum(densities) / len(densities)
        # ~5 events/s average
        assert avg >= 4.0

    def test_onset_burst_higher_density(self):
        """A burst of onsets in one region produces a density spike."""
        # Sparse baseline with a burst at 4-6s
        onsets = [0.0, 2.0, 4.0, 4.2, 4.4, 4.6, 4.8, 5.0, 5.2, 5.4, 5.6, 8.0]
        result = _compute_windowed_density(onsets, 10.0, window=2.0, step=2.0)
        # Window starting at 4s should have high density
        burst_window = [w for w in result if w["start"] == 4.0]
        sparse_window = [w for w in result if w["start"] == 0.0]
        assert len(burst_window) == 1
        assert len(sparse_window) == 1
        assert burst_window[0]["density"] > sparse_window[0]["density"]

    def test_empty_onsets_returns_empty(self):
        assert _compute_windowed_density([], 10.0) == []

    def test_zero_duration_returns_empty(self):
        assert _compute_windowed_density([1.0, 2.0], 0.0) == []

    def test_window_spans_correct_time_range(self):
        onsets = [0.5, 1.5, 2.5]
        result = _compute_windowed_density(onsets, 4.0, window=2.0, step=1.0)
        # First window: 0-2s, should contain 0.5 and 1.5
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 2.0
        assert result[0]["density"] == 1.0  # 2 events / 2s
        assert result[0]["unit"] == "events_per_second"

    def test_beat_relative_density_with_beats(self):
        """Beat-relative density uses an explicit events-per-beat contract."""
        onsets = [0.0, 1.0, 2.0, 3.0, 4.0]
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
        result = _compute_beat_relative_density(
            onsets,
            beats,
            window_beats=2,
            step_beats=1,
        )
        assert len(result) > 0
        for window in result:
            assert window["mode"] == "beat_relative"
            assert window["unit"] == "events_per_beat"
            assert window["window_size"] == 2.0
            assert window["step_size"] == 1.0


# ── _detect_rests ────────────────────────────────────────────────────────────


class TestDetectRests:
    """Tests for _detect_rests."""

    def test_silence_gap_exact_rest_span(self):
        """A gap of >= min_gap seconds is detected as a rest."""
        onsets = [0.0, 3.0]  # 3s gap between, then 1s after last to end=4
        rests = _detect_rests(onsets, 4.0, min_gap=1.0)
        # Two rests: gap between 0-3s and gap after last onset 3-4s
        assert len(rests) == 2
        # First rest: between onsets
        assert rests[0]["start"] == 0.0
        assert rests[0]["end"] == 3.0
        assert rests[0]["duration"] == 3.0
        # Second rest: after last onset (3-4s = 1.0s >= min_gap)
        assert rests[1]["start"] == 3.0
        assert rests[1]["end"] == 4.0

    def test_no_rest_when_gaps_too_small(self):
        """Gaps smaller than min_gap are not detected as rests."""
        onsets = [0.0, 0.5, 1.0, 1.5]
        rests = _detect_rests(onsets, 2.0, min_gap=1.0)
        assert len(rests) == 0

    def test_rest_before_first_onset(self):
        """Gap before first onset is detected."""
        onsets = [3.0, 4.0]
        rests = _detect_rests(onsets, 5.0, min_gap=1.0)
        assert len(rests) >= 1
        assert rests[0]["start"] == 0.0
        assert rests[0]["end"] == 3.0

    def test_rest_after_last_onset(self):
        """Gap after last onset is detected."""
        onsets = [0.0, 1.0]
        rests = _detect_rests(onsets, 5.0, min_gap=1.0)
        assert len(rests) >= 1
        last_rest = rests[-1]
        assert last_rest["start"] == 1.0
        assert last_rest["end"] == 5.0

    def test_multiple_rest_segments(self):
        """Multiple gaps produce multiple rest segments."""
        onsets = [0.0, 1.0, 5.0, 6.0, 10.0]
        rests = _detect_rests(onsets, 12.0, min_gap=1.0)
        # Should have rests at 1-5s and 6-10s (and possibly before/after)
        rest_starts = [r["start"] for r in rests]
        assert 1.0 in rest_starts
        assert 6.0 in rest_starts

    def test_empty_onsets_returns_empty(self):
        assert _detect_rests([], 10.0) == []

    def test_zero_duration_returns_empty(self):
        assert _detect_rests([1.0], 0.0) == []

    def test_rest_is_observed_silence_not_phrase(self):
        """Verify docstring semantics: rest = observed gap, not phrase boundary."""
        # A 2-second gap is just silence, not a phrase boundary
        onsets = [0.0, 3.0]
        rests = _detect_rests(onsets, 10.0, min_gap=1.0)
        # Multiple rests detected (between onsets, after last onset)
        assert len(rests) >= 1
        # The rest segments have no "kind" or "phrase" field
        for rest in rests:
            assert "kind" not in rest
            assert "phrase" not in rest


# ── _midi_rhythm integration ─────────────────────────────────────────────────


class TestMidiRhythm:
    """Integration tests for _midi_rhythm with real MIDI files."""

    def _make_midi(self, onsets: list[float], duration: float = 10.0) -> str:
        """Create a temporary MIDI file with notes at the given onset times."""
        pm = pretty_midi.PrettyMIDI(initial_tempo=120)
        inst = pretty_midi.Instrument(program=0)
        for onset in onsets:
            inst.notes.append(
                pretty_midi.Note(velocity=80, pitch=60, start=onset, end=min(onset + 0.3, duration))
            )
        pm.instruments.append(inst)
        path = tempfile.mktemp(suffix=".mid")
        with open(path, "wb") as f:
            pm.write(f)
        return path

    def test_sparse_midi_has_lower_density(self):
        path = self._make_midi([0.0, 3.0, 6.0, 9.0])
        try:
            result = _midi_rhythm(path)
            assert result is not None
            assert result["rhythmic_density"] < 1.0
            # Without trusted beat evidence, inspect the explicit seconds fallback.
            densities = [w["density"] for w in result["note_density_seconds_over_time"]]
            avg_density = sum(densities) / len(densities) if densities else 0
            assert avg_density < 2.0
            assert result["note_density_over_time"] == []
        finally:
            os.unlink(path)

    def test_dense_midi_has_higher_density(self):
        onsets = [i * 0.1 for i in range(100)]  # 100 notes in 10s
        path = self._make_midi(onsets)
        try:
            result = _midi_rhythm(path)
            assert result is not None
            assert result["rhythmic_density"] >= 8.0
        finally:
            os.unlink(path)

    def test_midi_with_rest_detected(self):
        # Notes at 0-1s, then silence 1-5s, then notes at 5-6s
        onsets = [0.0, 0.5, 1.0, 5.0, 5.5, 6.0]
        path = self._make_midi(onsets, duration=8.0)
        try:
            result = _midi_rhythm(path)
            assert result is not None
            assert len(result["rest_segments"]) >= 1
            # The rest between 1.0 and 5.0 should be detected
            rest = [r for r in result["rest_segments"] if r["start"] >= 0.9 and r["end"] <= 5.1]
            assert len(rest) >= 1
        finally:
            os.unlink(path)

    def test_explicit_pulse_coordinates_are_preserved_exactly(self):
        path = self._make_midi([0.15, 0.82, 1.56, 2.31], duration=3.0)
        pulse = {
            "bpm": 91.7,
            "beats": [0.11, 0.73, 1.41, 2.2, 2.86],
            "downbeats": [0.11, 2.2],
            "provenance": {"engine": "beat_this", "model_version": "test"},
        }
        try:
            result = _midi_rhythm(path, pulse)
            assert result is not None
            assert result["beats_seconds"] == pulse["beats"]
            assert result["downbeats_seconds"] == pulse["downbeats"]
            assert result["pulse_coordinate_unit"] == "seconds"
        finally:
            os.unlink(path)

    def test_no_pulse_does_not_publish_detected_grid(self):
        path = self._make_midi([0.0, 1.0, 2.0], duration=3.0)
        try:
            result = _midi_rhythm(path)
            assert result is not None
            assert "beats_seconds" not in result
            assert "downbeats_seconds" not in result
            assert "pulse_coordinate_unit" not in result
        finally:
            os.unlink(path)

    def test_empty_midi_returns_none(self):
        pm = pretty_midi.PrettyMIDI(initial_tempo=120)
        pm.instruments.append(pretty_midi.Instrument(program=0))
        path = tempfile.mktemp(suffix=".mid")
        with open(path, "wb") as f:
            pm.write(f)
        try:
            result = _midi_rhythm(path)
            assert result is None
        finally:
            os.unlink(path)


# ── Harmonic rhythm ──────────────────────────────────────────────────────────


class TestHarmonicRhythm:
    """Tests for harmonic rhythm computation (chord-change activity)."""

    def test_constant_chord_no_activity(self):
        """A single sustained chord produces no chord-change activity."""
        # One chord spanning the whole piece
        chord_onsets = [0.0]
        duration = 10.0
        result = _compute_windowed_density(chord_onsets, duration, window=4.0, step=1.0)
        # All windows should have density 0 or 1 (the initial chord)
        for w in result:
            assert w["density"] <= 1.0

    def test_changing_chords_higher_activity(self):
        """Rapid chord changes produce higher harmonic activity."""
        # Chord every 0.5s = high activity
        rapid = [i * 0.5 for i in range(20)]
        result_rapid = _compute_windowed_density(rapid, 10.0, window=4.0, step=1.0)
        densities_rapid = [w["density"] for w in result_rapid]

        # Chord every 4s = low activity
        slow = [0.0, 4.0, 8.0]
        result_slow = _compute_windowed_density(slow, 10.0, window=4.0, step=1.0)
        densities_slow = [w["density"] for w in result_slow]

        assert max(densities_rapid) > max(densities_slow)

    def test_no_chords_empty_result(self):
        """No chord onsets produces empty harmonic rhythm."""
        result = _compute_windowed_density([], 10.0, window=4.0, step=1.0)
        assert result == []

    def test_harmonic_rhythm_is_chord_change_not_tension(self):
        """Verify: harmonic_rhythm measures chord-change frequency, not tension."""
        # Two chords: I and V — simple, not tense
        onsets = [0.0, 5.0]
        result = _compute_windowed_density(onsets, 10.0, window=4.0, step=1.0)
        # Low density = low chord-change activity (correct)
        for w in result:
            assert w["density"] <= 1.0
        # This is correct: few chord changes = low harmonic activity
        # It does NOT measure whether the chords are "tense"
