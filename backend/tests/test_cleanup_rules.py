"""Deterministic tests for transcription cleanup rules + forensics."""

from __future__ import annotations

from evaluation.cleanup_rules import (
    cleanup_existing,
    cleanup_model_context,
    cleanup_model_score,
    cleanup_raw,
)
from evaluation.transcription_diagnostics import note_stats


def _note(pitch, start, end, velocity=64, amplitude=None):
    n = {"pitch": pitch, "start": start, "end": end, "velocity": velocity}
    if amplitude is not None:
        n["amplitude"] = amplitude
    return n


class TestCleanupRules:
    def test_raw_preserves_all(self):
        notes = [_note(60, 0, 0.5), _note(90, 0.5, 1.0)]
        kept, report = cleanup_raw(notes)
        assert len(kept) == 2
        assert report["profile"] == "raw"

    def test_existing_removes_short_and_out_of_range(self):
        notes = [
            _note(60, 0, 0.5),  # keep
            _note(64, 0.5, 0.55),  # too short (<75ms)
            _note(10, 1.0, 1.5),  # out of range (<21)
            _note(100, 1.5, 2.0),  # keep (in range)
        ]
        kept, report = cleanup_existing(notes)
        kept_pitches = {n["pitch"] for n in kept}
        assert kept_pitches == {60, 100}
        assert report["removed_short"] == 1
        assert report["removed_out_of_range"] == 1

    def test_model_score_filters_weak(self):
        notes = [_note(60, 0, 0.5, amplitude=0.8), _note(90, 0.5, 1.0, amplitude=0.1)]
        kept, report = cleanup_model_score(notes, amplitude_threshold=0.3)
        assert len(kept) == 1
        assert kept[0]["pitch"] == 60
        assert report["removed_weak"] == 1

    def test_model_context_filters_isolated_extreme(self):
        # A lone very-high note floating above a low cluster gets dropped.
        notes = [
            _note(60, 0, 0.5, amplitude=0.6),
            _note(64, 0, 0.5, amplitude=0.6),
            _note(97, 0.25, 0.75, amplitude=0.6),  # isolated extreme high (>96)
        ]
        kept, report = cleanup_model_context(notes, amplitude_threshold=0.3)
        kept_pitches = {n["pitch"] for n in kept}
        assert kept_pitches == {60, 64}
        assert report["removed_extreme_isolated"] == 1

    def test_model_context_keeps_legitimate_high_notes(self):
        # A high note in a stepwise line is not isolated and must be kept.
        notes = [
            _note(84, 0, 0.5, amplitude=0.6),
            _note(88, 0.5, 1.0, amplitude=0.6),
            _note(91, 1.0, 1.5, amplitude=0.6),
        ]
        kept, _ = cleanup_model_context(notes, amplitude_threshold=0.3)
        assert len(kept) == 3


class TestDiagnostics:
    def test_note_stats_counts_and_outliers(self):
        notes = [
            _note(60, 0, 0.5),
            _note(64, 0, 0.5),
            _note(67, 0, 0.5),
            _note(100, 0.25, 0.75),  # isolated (>12 st from the cluster), above C7
        ]
        stats = note_stats(notes)
        assert stats["note_count"] == 4
        assert stats["min_pitch"] == 60
        assert stats["max_pitch"] == 100
        assert stats["above_C7"] == 1
        assert stats["below_C2"] == 0
        assert stats["isolated_gt12"] == 1

    def test_note_stats_duration_histogram(self):
        notes = [_note(60, 0, 0.05), _note(64, 0.1, 0.5)]
        stats = note_stats(notes)
        assert stats["shorter_50ms"] == 0  # 0.05 is not < 0.05
        assert stats["shorter_100ms"] == 1
