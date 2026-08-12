"""Cleanup ablation and regression tests."""

from __future__ import annotations

import io

import pytest

pytest.importorskip("pretty_midi", reason="pretty_midi not installed locally")

import pretty_midi

from music_features import _clean_midi


def _make_midi(notes: list[tuple[int, float, float, int]]) -> bytes:
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    for pitch, start, end, vel in notes:
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch, start=start, end=end))
    midi.instruments.append(inst)
    buf = io.BytesIO()
    midi.write(buf)
    return buf.getvalue()


class TestCleanup:
    def test_removes_very_short_notes(self):
        midi = _make_midi([
            (60, 0.0, 0.5, 80),  # kept
            (64, 0.1, 0.11, 40),  # too short (< 0.075)
        ])
        result, report = _clean_midi(midi)
        assert report["removed_short"] == 1
        assert report["kept_notes"] == 1

    def test_removes_low_velocity_short(self):
        midi = _make_midi([
            (60, 0.0, 0.1, 15),  # low vel, short dur → removed
        ])
        result, report = _clean_midi(midi)
        assert report["removed_low_velocity"] == 1

    def test_keeps_low_velocity_long(self):
        midi = _make_midi([(60, 0.0, 0.3, 10)])  # low vel but long enough
        result, report = _clean_midi(midi)
        assert report["kept_notes"] == 1

    def test_removes_out_of_range(self):
        midi = _make_midi([
            (60, 0.0, 0.5, 80),  # kept
            (10, 0.0, 0.5, 80),  # too low
            (120, 0.0, 0.5, 80),  # too high
        ])
        result, report = _clean_midi(midi)
        assert report["removed_out_of_range"] == 2
        assert report["kept_notes"] == 1

    def test_merges_overlapping_same_pitch(self):
        midi = _make_midi([
            (60, 0.0, 0.3, 64),
            (60, 0.25, 0.5, 80),  # overlaps
        ])
        result, report = _clean_midi(midi)
        assert report["merged_overlaps"] == 1
        assert report["kept_notes"] == 1

    def test_cleanup_provenance(self):
        midi = _make_midi([(60, 0.0, 0.5, 80)])
        _result, report = _clean_midi(midi)
        assert report["profile"] == "performance_conservative_v1"
        assert "input_notes" in report
        assert "kept_notes" in report

    def test_no_accidental_quantization(self):
        """Cleanup must not quantize timing."""
        midi = _make_midi([(60, 0.03, 0.47, 80)])
        result, _report = _clean_midi(midi)
        midi2 = pretty_midi.PrettyMIDI(io.BytesIO(result))
        for inst in midi2.instruments:
            if inst.is_drum:
                continue
            for note in inst.notes:
                assert note.start == 0.03
                assert note.end == 0.47

    def test_drums_untouched(self):
        midi = pretty_midi.PrettyMIDI()
        drum = pretty_midi.Instrument(program=0, is_drum=True)
        drum.notes.append(pretty_midi.Note(velocity=80, pitch=36, start=0.0, end=0.05))
        midi.instruments.append(drum)
        buf = io.BytesIO()
        midi.write(buf)
        result, report = _clean_midi(buf.getvalue())
        assert report["input_notes"] == 0  # drums not counted
        assert report["kept_notes"] == 0
