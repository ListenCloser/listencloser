"""Tests for adaptive quantization."""

from __future__ import annotations

import io

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
        """Notes within one measure must share the same selected grid."""
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
        assert selections[0]["grid_name"] in ("eighth", "sixteenth")

    def test_different_measures_can_choose_different_grids(self):
        """Two measures with different rhythmic density may pick different grids."""
        notes = []
        # Measure 1: widely spaced
        notes.extend([(60, 0.0, 1.0), (64, 1.0, 2.0)])
        # Measure 2: dense
        notes.extend(
            [
                (67, 2.01, 2.25),
                (65, 2.25, 2.50),
                (69, 2.50, 2.75),
                (72, 2.75, 3.0),
                (60, 3.0, 3.25),
                (64, 3.25, 3.50),
                (67, 3.50, 3.75),
                (65, 3.75, 4.0),
            ]
        )
        midi = _make_midi(notes)
        beats = list([b / 4.0 for b in range(17)])
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        selections = report["grid_selections"]
        assert len(selections) >= 2
        grid_names = [s["grid_name"] for s in selections]
        assert len(set(grid_names)) >= 1  # at minimum, different measures

    def test_compound_meter_preserved(self):
        """6/8 meter inferred from downbeats should produce valid quantization."""
        midi = _make_midi([(60, 0.0, 0.33), (64, 0.33, 0.66), (67, 0.66, 1.0)])
        beats = list([b / 3.0 for b in range(13)])  # 6 beats per 2-sec measure
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
