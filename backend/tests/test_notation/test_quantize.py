"""Tests for adaptive quantization."""

from __future__ import annotations

import io
import json

import pytest

pytest.importorskip("pretty_midi", reason="pretty_midi not installed locally")

import pretty_midi  # noqa: E402

from notation.grid import build_metrical_grid  # noqa: E402
from notation.quantize import adaptive_quantize, quantize_fixed_grid  # noqa: E402


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
    def test_performance_midi_unchanged_notation_midi_quantized(self):
        """Input bytes untouched; returned MIDI has quantized timings."""
        midi = _make_midi([(60, 0.03, 0.47), (64, 0.52, 0.98)])
        original = midi  # bytes
        beats = [0.0, 0.5, 1.0, 1.5]
        downbeats = [0.0, 1.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, report = adaptive_quantize(midi, grid)
        # Input unchanged
        assert original == midi
        # Output quantized
        notes = _notes_from_midi(result_midi)
        for n in notes:
            assert abs(n["start"] - round(n["start"] / 0.5) * 0.5) < 0.06
        assert report["timing_mode"] == "metrical_grid"
        assert report["quantized_notes"] >= 2

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
        downbeats = [0.0, 1.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "metrical_grid"
        assert len(report["grid_selections"]) > 0

    def test_no_meter_no_grid(self):
        """Beats alone cannot establish a meter, so timing is preserved (no grid)."""
        midi = _make_midi([(60, 0.0, 0.5)])
        beats = [0.0, 0.5]
        grid = build_metrical_grid(beats)
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "preserved_no_meter"

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
        """Different measures can select different subdivision grids."""
        # 4/4 meter (downbeats every 2.0s, beats every 0.5s).
        # Measure 0 is quarter-note based; measure 1 is eighth-note based.
        notes = [
            (60, 0.0, 0.5),
            (64, 0.5, 1.0),
            (67, 1.0, 1.5),
            (65, 1.5, 2.0),
            (60, 2.0, 2.25),
            (64, 2.25, 2.5),
            (67, 2.5, 2.75),
            (65, 2.75, 3.0),
            (69, 3.0, 3.25),
            (72, 3.25, 3.5),
            (70, 3.5, 3.75),
            (65, 3.75, 4.0),
        ]
        midi = _make_midi(notes)
        beats = [b / 2.0 for b in range(9)]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        _result_midi, report = adaptive_quantize(midi, grid)
        assert report["timing_mode"] == "metrical_grid"
        selections = report["grid_selections"]
        assert len(selections) >= 2
        assert {s["grid_name"] for s in selections} >= {"quarter", "eighth"}

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

    def test_measure_start_not_at_time_zero(self):
        """Grid anchored at measure boundary, not absolute time 0."""
        midi = _make_midi([(60, 1.13, 1.62), (64, 1.62, 2.12)])
        beats = [1.0, 1.5, 2.0, 2.5]
        downbeats = [1.0, 2.0, 3.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        for n in notes:
            assert n["start"] >= 1.0
            assert abs(n["start"] - round(n["start"] / 0.5) * 0.5) < 0.06


class TestReleasePreservation:
    """Note releases are preserved across measure boundaries.

    A note's onset is quantized against the grid of the measure it starts in,
    and its release against the measure that contains it. Releases in a later
    measure (or outside every trustworthy measure) are never clamped to the
    onset measure's boundary, so sustained musical notes keep their full extent
    and barline ties are owned downstream.
    """

    def test_release_inside_single_measure_preserved(self):
        """A short note entirely inside one measure keeps its release."""
        midi = _make_midi([(60, 0.0, 1.0)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0]
        downbeats = [0.0, 2.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert notes[0]["start"] == 0.0
        assert abs(notes[0]["end"] - 1.0) < 0.05

    def test_release_exactly_on_barline_preserved(self):
        """A release landing exactly on a barline stays on the barline."""
        midi = _make_midi([(60, 0.0, 2.0)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert notes[0]["start"] == 0.0
        assert abs(notes[0]["end"] - 2.0) < 1e-6

    def test_release_crossing_one_barline_not_truncated(self):
        """A note crossing a barline keeps its full extent, never clamped to
        the onset measure's end."""
        midi = _make_midi([(60, 0.0, 3.0)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert abs(notes[0]["end"] - 3.0) < 0.05

    def test_release_crossing_multiple_bars_preserved(self):
        """A note spanning several measures is not compressed into its first."""
        midi = _make_midi([(60, 0.0, 5.0)])
        beats = [b / 2.0 for b in range(13)]
        downbeats = [0.0, 2.0, 4.0, 6.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert abs(notes[0]["end"] - 5.0) < 0.05

    def test_late_start_early_release_next_measure(self):
        """An onset near the end of measure 0 releases inside measure 1; the
        release is quantized on its own measure's grid, not clamped to 2.0."""
        midi = _make_midi([(60, 1.75, 2.25)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert notes[0]["start"] == 1.75  # already on measure 0's eighth grid
        assert notes[0]["end"] > 2.0  # never clamped to the measure-0 boundary
        assert abs(notes[0]["end"] - 2.25) < 0.05

    def test_cross_bar_release_uses_next_measure_grid(self):
        """When measure grids differ, a cross-bar note's release follows the
        containing measure's subdivision: quarter in m0, eighth in m1."""
        notes = [
            (60, 0.0, 0.5),
            (64, 0.5, 1.0),
            (67, 1.0, 1.5),
            (65, 1.5, 2.0),
            (60, 2.0, 2.25),
            (64, 2.25, 2.5),
            (67, 2.5, 2.75),
            (65, 2.75, 3.0),
            (69, 3.0, 3.25),
            (72, 3.25, 3.5),
            (70, 3.5, 3.75),
            (65, 3.75, 4.0),
            (72, 1.5, 2.4),
        ]
        midi = _make_midi(notes)
        beats = [b / 2.0 for b in range(9)]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, report = adaptive_quantize(midi, grid)
        selections = {s["measure_index"]: s["grid_name"] for s in report["grid_selections"]}
        assert selections[0] == "quarter"
        assert selections[1] == "eighth"
        out = [n for n in _notes_from_midi(result_midi) if n["pitch"] == 72]
        cross_bar = min(out, key=lambda n: n["start"])
        assert abs(cross_bar["start"] - 1.5) < 1e-6  # on measure 0's quarter grid
        assert abs(cross_bar["end"] - 2.5) < 1e-6  # snapped to measure 1's eighth grid

    def test_release_exactly_on_barline_with_next_measure_notes(self):
        """A note ending exactly on a barline is not extended or truncated even
        when the next measure has its own grid and notes."""
        notes = [
            (60, 0.0, 2.0),
            (64, 2.25, 2.5),
            (67, 2.5, 2.75),
        ]
        midi = _make_midi(notes)
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.25, 2.5, 2.75, 3.0]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        sustained = [n for n in _notes_from_midi(result_midi) if n["pitch"] == 60][0]
        assert abs(sustained["end"] - 2.0) < 1e-6

    def test_release_after_last_trustworthy_measure_preserved(self):
        """A release past the final inferred measure is preserved, not mapped
        to an unrelated earlier measure."""
        midi = _make_midi([(60, 0.0, 9.0)])
        beats = [b / 2.0 for b in range(17)]
        downbeats = [0.0, 2.0, 4.0, 6.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert abs(notes[0]["end"] - 9.0) < 0.05

    def test_pre_roll_start_before_first_boundary_preserved(self):
        """A note beginning before the first measure boundary is not snapped
        forward onto measure 0's grid."""
        midi = _make_midi([(60, 0.0, 1.5)])
        beats = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        downbeats = [1.0, 3.0, 5.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        assert abs(notes[0]["start"] - 0.0) < 1e-6
        assert abs(notes[0]["end"] - 1.5) < 0.05

    def test_simultaneous_cross_bar_notes_preserved(self):
        """Simultaneous notes crossing a barline each keep their own extent."""
        midi = _make_midi([(60, 0.0, 3.0), (64, 0.5, 3.5)])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, _report = adaptive_quantize(midi, grid)
        notes = _notes_from_midi(result_midi)
        by_pitch = {n["pitch"]: n for n in notes}
        assert abs(by_pitch[60]["end"] - 3.0) < 0.05
        assert abs(by_pitch[64]["end"] - 3.5) < 0.05

    def test_long_sustain_does_not_bias_onset_measure_grid(self):
        """A sustained note releasing in a later measure must not change the
        subdivision chosen for the measure it starts in."""
        notes = [
            (60, 0.0, 0.5),
            (64, 0.5, 1.0),
            (67, 1.0, 1.5),
            (65, 1.5, 2.0),
            (72, 1.0, 3.5),
        ]
        midi = _make_midi(notes)
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        downbeats = [0.0, 2.0, 4.0]
        grid = build_metrical_grid(beats, downbeats)
        result_midi, report = adaptive_quantize(midi, grid)
        m0 = [s for s in report["grid_selections"] if s["measure_index"] == 0][0]
        assert m0["grid_name"] == "quarter"
        sustained = [n for n in _notes_from_midi(result_midi) if n["pitch"] == 72][0]
        assert abs(sustained["end"] - 3.5) < 0.05

    def test_downstream_notation_keeps_cross_bar_tie(self):
        """A quantized logical note crossing a barline yields tied notes in the
        grand-staff engraving (music21 makeTies)."""
        pytest.importorskip("music21", reason="music21 not installed locally")
        from notation.staffing import grand_staff_from_midi

        notes = [
            (60, 0.0, 0.5),
            (64, 0.5, 1.0),
            (67, 1.0, 1.5),
            (65, 1.5, 2.0),
            (72, 0.0, 5.0),
        ]
        midi = _make_midi(notes)
        beats = [b / 2.0 for b in range(13)]
        downbeats = [0.0, 2.0, 4.0, 6.0]
        grid = build_metrical_grid(beats, downbeats)
        quantized, report = adaptive_quantize(midi, grid)
        qnotes = {n["pitch"]: n for n in _notes_from_midi(quantized)}
        assert abs(qnotes[72]["end"] - 5.0) < 0.05  # full extent survives

        score = grand_staff_from_midi(quantized)
        tied = [n for n in score.recurse().notes if n.tie is not None]
        assert tied, "expected a cross-bar tie in the engraved score"
        assert any(n.pitch.midi == 72 for n in tied)


class TestFixedGridQuantize:
    def test_quantizes_to_eighth_note_grid(self):
        """Micro-timing collapses to a clean eighth-note grid."""
        midi = _make_midi([(60, 0.03, 0.47), (64, 0.52, 0.98), (67, 1.03, 1.62)])
        result_midi, report = quantize_fixed_grid(midi)
        assert report["timing_mode"] == "fixed_grid"
        step = report["grid_step_seconds"]
        assert step == 0.5  # _make_midi uses 60 BPM; subdivision 2 -> eighth
        notes = _notes_from_midi(result_midi)
        # Onsets and offsets land on multiples of the grid step.
        for n in notes:
            assert abs(n["start"] - round(n["start"] / step) * step) < 1e-6
            assert abs(n["end"] - round(n["end"] / step) * step) < 1e-6
        # Durations are clean multiples of the grid step.
        durations = {round(n["end"] - n["start"], 3) for n in notes}
        assert durations <= {step, step * 2, step * 3, step * 4}

    def test_short_note_gets_minimum_grid_duration(self):
        """A sub-grid-length note is floored to at least one grid step."""
        midi = _make_midi([(60, 0.0, 0.05)])
        result_midi, report = quantize_fixed_grid(midi)
        notes = _notes_from_midi(result_midi)
        assert notes[0]["start"] == 0.0
        assert notes[0]["end"] == report["grid_step_seconds"]

    def test_respects_midi_tempo(self):
        """Grid step derives from the MIDI's own tempo, not a hardcoded 120."""
        midi = pretty_midi.PrettyMIDI(initial_tempo=240)
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=64, pitch=60, start=0.0, end=0.2))
        midi.instruments.append(inst)
        buf = io.BytesIO()
        midi.write(buf)
        result_midi, report = quantize_fixed_grid(buf.getvalue())
        assert report["bpm"] == 240.0
        assert report["grid_step_seconds"] == 0.125
        notes = _notes_from_midi(result_midi)
        assert abs(notes[0]["end"] - round(notes[0]["end"] / 0.125) * 0.125) < 1e-6
