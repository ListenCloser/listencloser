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
    def test_stable_4_4(self):
        midi = _make_midi([(60, 0.0, 0.5), (64, 0.5, 1.0), (67, 1.0, 1.5), (65, 1.5, 2.0)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0]
        grid = build_metrical_grid(beats)
        result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "metrical_grid"
        notes = _notes_from_midi(result_midi)
        for n in notes:
            assert abs(n["start"] - float(round(n["start"] / 0.01) * 0.01)) < 0.02

    def test_performance_midi_unchanged(self):
        """Input performance MIDI must be byte-identical before and after."""
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
            assert n["end"] - n["start"] > 0

    def test_tiny_timing_deviations(self):
        midi = _make_midi([(60, 0.01, 0.49)])
        beats = [0.0, 0.5]
        grid = build_metrical_grid(beats)
        result_midi, report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert abs(notes[0]["start"] - 0.0) < 0.02

    def test_missing_beat_grid(self):
        midi = _make_midi([(60, 0.0, 0.5)])
        grid = build_metrical_grid([])
        result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "preserved_no_grid"

    def test_notes_crossing_measure_boundary(self):
        midi = _make_midi([(60, 0.0, 2.5)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        downbeats = [0.0, 2.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        for n in notes:
            assert n["end"] > n["start"]

    def test_tempo_drift(self):
        midi = _make_midi([(60, 0.0, 0.6), (64, 0.6, 1.3), (67, 1.3, 2.0)])
        beats = [0.0, 0.6, 1.3, 2.0]
        grid = build_metrical_grid(beats)
        result_midi, report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert len(notes) == 3
        for n in notes:
            assert n["end"] > n["start"]
