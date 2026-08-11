from __future__ import annotations

import io

import pretty_midi

from music_features import _clean_midi


def _midi_with(notes: list[tuple[int, float, float, int]]) -> bytes:
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes = [
        pretty_midi.Note(velocity=velocity, pitch=pitch, start=start, end=end)
        for pitch, start, end, velocity in notes
    ]
    midi.instruments.append(instrument)
    out = io.BytesIO()
    midi.write(out)
    return out.getvalue()


def test_performance_cleanup_removes_only_explainable_noise():
    cleaned, report = _clean_midi(
        _midi_with(
            [
                (60, 0.0, 0.5, 80),
                (60, 0.2, 0.7, 60),  # overlapping duplicate merges into the first
                (64, 0.1, 0.14, 90),  # too short
                (67, 0.1, 0.2, 10),  # quiet and short
                (12, 0.0, 1.0, 90),  # outside piano range
            ]
        )
    )
    parsed = pretty_midi.PrettyMIDI(io.BytesIO(cleaned))
    notes = parsed.instruments[0].notes

    assert len(notes) == 1
    assert notes[0].pitch == 60
    assert notes[0].start == 0.0
    assert notes[0].end >= 0.69
    assert report == {
        "profile": "performance_conservative_v1",
        "input_notes": 5,
        "kept_notes": 1,
        "removed_short": 1,
        "removed_low_velocity": 1,
        "removed_out_of_range": 1,
        "merged_overlaps": 1,
    }


def test_performance_cleanup_does_not_snap_valid_timing():
    cleaned, report = _clean_midi(_midi_with([(69, 0.113, 0.431, 72)]))
    note = pretty_midi.PrettyMIDI(io.BytesIO(cleaned)).instruments[0].notes[0]

    assert abs(note.start - 0.113) < 0.002
    assert abs(note.end - 0.431) < 0.002
    assert report["kept_notes"] == 1
