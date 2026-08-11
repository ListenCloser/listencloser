"""Tests for adaptive quantization."""

from __future__ import annotations

import io
import json

import pytest

pytest.importorskip("pretty_midi", reason="pretty_midi not installed locally")

import pretty_midi

from notation.grid import build_metrical_grid
from notation.quantize import adaptive_quantize


def _make_midi(notes) -> bytes:
    midi = pretty_midi.PrettyMIDI(initial_tempo=60)
    inst = pretty_midi.Instrument(program=0)
    for pitch, start, end in notes:
        inst.notes.append(pretty_midi.Note(velocity=64, pitch=pitch, start=start, end=end))
    midi.instruments.append(inst)
    buf = io.BytesIO()
    midi.write(buf)
    return buf.getvalue()


def _notes_from_midi(midi_bytes: bytes) -> list[dict]:
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    notes = []
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            notes.append({"pitch": note.pitch, "start": note.start, "end": note.end})
    return notes


class TestAdaptiveQuantize:
    def test_performance_midi_unchanged(self):
        midi = _make_midi([(60, 0.0, 0.5)])
        original = midi
        beats = [0.0, 0.5, 1.0]
        grid = build_metrical_grid(beats)
        _result, _report = adaptive_quantize(original, grid)
        assert original == midi

    def test_no_negative_durations(self):
        midi = _make_midi([(60, 0.0, 0.05), (64, 0.48, 0.52)])
        beats = [0.0, 0.5, 1.0]
        grid = build_metrical_grid(beats)
        result_midi, report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        for n in notes:
            assert n["end"] > n["start"]

    def test_missing_beat_grid_preserves_timing(self):
        midi = _make_midi([(60, 0.0, 0.5)])
        grid = build_metrical_grid([])
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "preserved_no_grid"

    def test_successful_run_sets_metrical_grid_mode(self):
        midi = _make_midi([(60, 0.0, 0.5), (64, 0.5, 1.0)])
        beats = [0.0, 0.5, 1.0]
        downbeats = [0.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "metrical_grid"
        assert len(report["grid_selections"]) > 0

    def test_no_meter_no_grid(self):
        midi = _make_midi([(60, 0.0, 0.5)])
        beats = [0.0, 0.5]
        grid = build_metrical_grid(beats)
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "preserved_no_grid"

    def test_all_notes_in_measure_same_grid(self):
        midi = _make_midi(
            [
                (60, 0.0, 0.5),
                (64, 0.48, 0.98),
                (67, 0.97, 1.48),
                (65, 1.47, 1.99),
            ]
        )
        beats = [0.0, 0.5, 1.0, 1.5, 2.0]
        downbeats = [0.0, 2.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "metrical_grid"
        selections = report["grid_selections"]
        assert len(selections) == 1

    def test_different_measures_different_grids(self):
        notes = [
            (60, 0.0, 1.0),
            (64, 1.0, 2.0),
            (67, 2.01, 2.25),
            (65, 2.25, 2.50),
            (69, 2.50, 2.75),
            (72, 2.75, 3.0),
            (60, 3.0, 3.25),
            (64, 3.25, 3.50),
            (67, 3.50, 3.75),
            (65, 3.75, 4.0),
        ]
        midi = _make_midi(notes)
        beats = [b / 4.0 for b in range(17)]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        selections = report["grid_selections"]
        assert len(selections) >= 2

    def test_compound_meter_preserved(self):
        midi = _make_midi([(60, 0.0, 0.33), (64, 0.33, 0.66), (67, 0.66, 1.0)])
        beats = [b / 3.0 for b in range(13)]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        assert grid.inferred_meter == (6, 8)
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "metrical_grid"

    def test_sustained_cross_measure_note(self):
        midi = _make_midi([(60, 0.0, 3.0)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert notes[0]["end"] > notes[0]["start"]
        assert abs(notes[0]["end"] - 3.0) < 0.5

    def test_same_rhythm_at_60_and_180_bpm(self):
        """Quarter notes at 60 BPM and 180 BPM should both select quarter grid."""
        for tempo_dur, bpm_beats in [
            (1.0, [0.0, 1.0, 2.0, 3.0]),
            (0.333, [0.0, 0.333, 0.666, 1.0]),
        ]:
            dur = tempo_dur  # beat duration in seconds
            midi = _make_midi(
                [
                    (60, 0.0, dur),
                    (64, dur, dur * 2),
                    (67, dur * 2, dur * 3),
                    (65, dur * 3, dur * 4),
                ]
            )
            beats = bpm_beats
            downbeats = [0.0, bpm_beats[-1] + dur]
            grid = build_metrical_grid(beats, downbeats)
            _result_midi, report = adaptive_quantize(midi, grid)
            selections = report["grid_selections"]
            assert len(selections) >= 1
            assert selections[0]["grid_name"] == "quarter"

    def test_report_is_json_serializable(self):
        midi = _make_midi([(60, 0.0, 0.5)])
        beats = [0.0, 0.5, 1.0]
        downbeats = [0.0, 1.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        text = json.dumps(report, indent=2)
        assert "grid_selections" in text
        assert "grid_name" in text

    def test_measure_indices_are_correct(self):
        notes = [
            (60, 0.0, 0.5),
            (64, 0.5, 1.0),
            (67, 1.0, 1.5),
            (65, 2.0, 2.5),
            (69, 2.5, 3.0),
            (72, 4.0, 4.5),
            (60, 4.5, 5.0),
        ]
        midi = _make_midi(notes)
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5]
        downbeats = [0.0, 2.0, 4.0, 6.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        indices = sorted({s["measure_index"] for s in report["grid_selections"]})
        assert indices == [0, 1, 2]
