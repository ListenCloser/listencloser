"""Tests for source-separation experiment plumbing (no heavyweight models)."""

from __future__ import annotations

from evaluation.merge import merge_notes, raw_concat
from evaluation.separation import DEMUCS_SOURCES, PITCHED_SOURCES
from evaluation.transcription_metrics import Note


class TestSeparatorContract:
    def test_demucs_sources_are_drums_bass_other_vocals(self):
        assert list(DEMUCS_SOURCES) == ["drums", "bass", "other", "vocals"]

    def test_pitched_sources_exclude_drums(self):
        assert "drums" not in PITCHED_SOURCES
        assert set(PITCHED_SOURCES) == {"bass", "other", "vocals"}


class TestMerge:
    def test_merge_dedups_identical_notes(self):
        stem_preds = [
            [Note(60, 0.0, 0.5, 80)],
            [Note(60, 0.01, 0.5, 80)],  # near-duplicate from a second stem
        ]
        merged = merge_notes(stem_preds)
        assert len(merged) == 1

    def test_merge_keeps_distinct_notes(self):
        stem_preds = [
            [Note(60, 0.0, 0.5, 80)],
            [Note(64, 0.0, 0.5, 80)],  # different pitch
        ]
        merged = merge_notes(stem_preds)
        assert len(merged) == 2

    def test_raw_concat_does_not_dedup(self):
        stem_preds = [
            [Note(60, 0.0, 0.5, 80)],
            [Note(60, 0.01, 0.5, 80)],
        ]
        assert len(raw_concat(stem_preds)) == 2

    def test_merge_pitch_never_matches_different_octave(self):
        stem_preds = [
            [Note(60, 0.0, 0.5, 80)],
            [Note(72, 0.0, 0.5, 80)],  # same pitch class, different octave
        ]
        merged = merge_notes(stem_preds)
        assert len(merged) == 2
