"""Regression tests for OSS bakeoff evaluation framework fixes.

Covers bugs found after merging PR #222:
1. Missing Path import in _compute_transcription_metrics
2. Redundant Note.from_dict() on already-Note objects (crash)
3. music21 BytesIO parsing bug producing IndexError
4. None values crashing _compute_category_aggregate
5. Wrong metric key names in transcription aggregate
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestTranscriptionMetricsPathImport:
    """Bug: _compute_transcription_metrics used Path without importing it."""

    def test_compute_transcription_metrics_has_reference_midi(self):
        """Function should work when clip.reference_midi exists (uses Path internally)."""
        from evaluation.engines import _compute_transcription_metrics
        from evaluation.models import EvalClip, Reference

        # Create a minimal MIDI file with one note
        midi_bytes = _make_minimal_midi()

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(midi_bytes)
            midi_path = f.name

        try:
            clip = EvalClip(
                id="test",
                audio="/dev/null",
                category="solo_piano",
                reference_midi=midi_path,
            )
            output = {"notes": [{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}]}

            metrics = _compute_transcription_metrics(output, clip)
            assert metrics is not None
            assert "note_f1" in metrics
        finally:
            os.unlink(midi_path)

    def test_compute_no_reference_returns_empty(self):
        """Without reference_midi, metrics should be empty dict (no crash)."""
        from evaluation.engines import _compute_transcription_metrics
        from evaluation.models import EvalClip

        clip = EvalClip(id="test", audio="/dev/null", category="solo_piano", reference_midi=None)
        metrics = _compute_transcription_metrics({"notes": []}, clip)
        assert metrics == {}


class TestNoteConversion:
    """Bug: _compute_transcription_metrics called Note.from_dict on Note objects."""

    def test_ref_notes_not_double_wrapped(self):
        """_midi_to_notes returns Note objects; they should NOT be re-wrapped."""
        from evaluation.engines import _compute_transcription_metrics
        from evaluation.models import EvalClip
        from evaluation.benchmark import _midi_to_notes

        midi_bytes = _make_minimal_midi()
        ref_notes = _midi_to_notes(midi_bytes)

        # ref_notes should be Note objects
        from evaluation.transcription_metrics import Note

        assert isinstance(ref_notes[0], Note)

        # _compute_transcription_metrics should accept these without crashing
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(midi_bytes)
            midi_path = f.name

        try:
            clip = EvalClip(
                id="test",
                audio="/dev/null",
                category="solo_piano",
                reference_midi=midi_path,
            )
            output = {"notes": [{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}]}
            metrics = _compute_transcription_metrics(output, clip)
            assert metrics is not None
        finally:
            os.unlink(midi_path)


class TestMusic21Parsing:
    """Bug: music21 converter.parse(BytesIO) triggers MuseData format bug."""

    def test_harmony_adapter_parses_midi_bytes(self):
        """Music21HarmonyAdapter.analyze_harmony should work with raw MIDI bytes."""
        pytest.importorskip("music21")

        from evaluation.engines.harmony import Music21HarmonyAdapter

        midi_bytes = _make_minimal_midi()
        adapter = Music21HarmonyAdapter()
        result = adapter.analyze_harmony(midi_bytes)

        assert "key" in result
        assert "chords" in result
        assert "cadences" in result


class TestAggregateMetricsNoneHandling:
    """Bug: None values in metrics dict crash _compute_category_aggregate."""

    def test_none_metrics_do_not_crash_aggregate(self):
        """Aggregate computation should handle None metric values gracefully."""
        from evaluation.engines import (
            EngineEvalResult,
            EngineInfo,
            EngineAggregateReport,
            _compute_category_aggregate,
        )

        # Simulate a result with None metrics (e.g. harmony clip without reference)
        result_with_none = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="harmony",
            success=True,
            metrics={"key_correct": None, "chord_f1": None, "bpm_absolute_error": None},
        )

        report = _compute_category_aggregate([result_with_none], "harmony")
        assert report["macro_key_accuracy"] == 0
        assert report["macro_chord_f1"] == 0

    def test_none_transcription_metrics_do_not_crash(self):
        """Same for transcription category."""
        from evaluation.engines import _compute_category_aggregate, EngineEvalResult

        result = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="transcription",
            success=True,
            metrics={"note_f1": None, "note_precision": None, "note_recall": None},
        )

        report = _compute_category_aggregate([result], "transcription")
        assert "macro_note_f1" in report


class TestMetricKeyNames:
    """Bug: Wrong metric key names in _compute_category_aggregate."""

    def test_harmony_uses_key_correct_not_key_accuracy(self):
        """Harmony aggregate should look for 'key_correct', not 'key_accuracy'."""
        from evaluation.engines import _compute_category_aggregate, EngineEvalResult

        result = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="harmony",
            success=True,
            metrics={"key_correct": True, "chord_f1": 0.8},
        )

        report = _compute_category_aggregate([result], "harmony")
        assert report["macro_key_accuracy"] == 1.0
        assert report["macro_chord_f1"] == 0.8

    def test_transcription_uses_note_precision_not_precision(self):
        """Transcription aggregate should use note_precision, not precision."""
        from evaluation.engines import _compute_category_aggregate, EngineEvalResult

        result = EngineEvalResult(
            engine_name="test",
            clip_id="c1",
            category="transcription",
            success=True,
            metrics={"note_f1": 0.9, "note_precision": 0.8, "note_recall": 0.85},
        )

        report = _compute_category_aggregate([result], "transcription")
        assert report["macro_precision"] == 0.8
        assert report["macro_recall"] == 0.85
        assert report["macro_note_f1"] == 0.9


# --- Helpers ---

def _make_minimal_midi() -> bytes:
    """Create a minimal MIDI file with a single C4 note for testing."""
    import struct
    import io

    def _var_len(value: int) -> bytes:
        buf = bytearray()
        buf.append(value & 0x7F)
        value >>= 7
        while value:
            buf.append(0x80 | (value & 0x7F))
            value >>= 7
        buf.reverse()
        return bytes(buf)

    ppq = 480
    tempo_bpm = 120
    ticks_per_beat = int(60_000_000 / tempo_bpm)

    track_data = bytearray()
    # Tempo
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x51, 0x03]))
    track_data.extend(bytes([(ticks_per_beat >> 16) & 0xFF, (ticks_per_beat >> 8) & 0xFF, ticks_per_beat & 0xFF]))
    # Note on
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0x90, 60, 64]))
    # Note off (1 beat later)
    track_data.extend(_var_len(ppq))
    track_data.extend(bytes([0x80, 60, 0]))
    # End of track
    track_data.extend(_var_len(0))
    track_data.extend(bytes([0xFF, 0x2F, 0x00]))

    header = struct.pack(">HHH", 0, 1, ppq)
    track_chunk = b"MTrk" + struct.pack(">I", len(track_data)) + bytes(track_data)
    return b"MThd" + struct.pack(">I", 6) + header + track_chunk
