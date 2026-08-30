"""Regression coverage for source-grid timing in piano Score engraving."""

from __future__ import annotations

import io

import pytest

pretty_midi = pytest.importorskip("pretty_midi", reason="pretty_midi not installed locally")
pytest.importorskip("music21", reason="music21 not installed locally")

from engines.notation.music21_engine import Music21NotationEngine  # noqa: E402
from notation.staffing import grand_staff_from_midi  # noqa: E402


def _placeholder_tempo_midi() -> bytes:
    """Four source-60-BPM quarter notes carried by Basic-Pitch-like 120 metadata."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=120)
    midi.time_signature_changes.append(
        pretty_midi.TimeSignature(numerator=4, denominator=4, time=0.0)
    )
    instrument = pretty_midi.Instrument(program=0)
    for index, pitch in enumerate((60, 62, 64, 65)):
        instrument.notes.append(
            pretty_midi.Note(
                velocity=80,
                pitch=pitch,
                start=float(index),
                end=float(index + 1),
            )
        )
    midi.instruments.append(instrument)
    output = io.BytesIO()
    midi.write(output)
    return output.getvalue()


def _note_quarter_lengths(score) -> list[float]:
    return sorted(float(element.quarterLength) for element in score.recurse().notes)


def _measure_count(score) -> int:
    from music21 import stream

    return max(
        len(list(staff.getElementsByClass(stream.Measure)))
        for staff in score.getElementsByClass(stream.PartStaff)
    )


def _midi_note_tuples(midi_bytes: bytes) -> list[tuple[int, float, float]]:
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    return sorted(
        (note.pitch, round(float(note.start), 6), round(float(note.end), 6))
        for instrument in midi.instruments
        if not instrument.is_drum
        for note in instrument.notes
    )


def test_source_grid_prevents_placeholder_tempo_from_doubling_note_values():
    midi_bytes = _placeholder_tempo_midi()

    embedded_metadata_score = grand_staff_from_midi(midi_bytes)
    source_grid_score = grand_staff_from_midi(
        midi_bytes,
        beat_times=[0.0, 1.0, 2.0, 3.0, 4.0],
        meter_signature=(4, 4),
    )

    # Control reproduces the historical failure: 120-BPM placeholder metadata
    # makes each one-second source quarter look like a half note.
    assert _note_quarter_lengths(embedded_metadata_score) == [2.0, 2.0, 2.0, 2.0]
    assert _measure_count(embedded_metadata_score) == 2

    # The exact same note events become one 4/4 measure of quarter notes when
    # the already-selected source-audio metric grid owns score timing.
    assert _note_quarter_lengths(source_grid_score) == [1.0, 1.0, 1.0, 1.0]
    assert _measure_count(source_grid_score) == 1


def test_music21_engine_uses_source_grid_without_mutating_note_evidence():
    midi_bytes = _placeholder_tempo_midi()
    original_notes = _midi_note_tuples(midi_bytes)

    result = Music21NotationEngine().convert(
        midi_bytes,
        beat_times=[0.0, 1.0, 2.0, 3.0, 4.0],
        adaptive=True,
        downbeats=[0.0, 4.0],
        notation_ready=True,
        piano_grand_staff=True,
    )

    from music21 import converter

    score = converter.parseData(result.musicxml.decode("utf-8"), format="musicxml")
    assert _note_quarter_lengths(score) == [1.0, 1.0, 1.0, 1.0]
    assert _midi_note_tuples(result.notation_midi) == original_notes
    assert result.quantization_report["timing_mode"] == "metrical_grid"
