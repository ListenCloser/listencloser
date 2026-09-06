"""Deterministic tests for piano grand-staff reconstruction.

The staff-assignment algorithm is a pure function over pitch events, so it can
be verified without music21 or real audio.  A separate test verifies that
``grand_staff_from_midi`` preserves note content.
"""

from __future__ import annotations

import io

import pytest

pytest.importorskip("pretty_midi", reason="pretty_midi not installed locally")

import pretty_midi  # noqa: E402

from notation.staffing import assign_staffs, grand_staff_from_midi, split_pitches  # noqa: E402


class TestStaffAssignment:
    def test_simple_low_high_split(self):
        assert assign_staffs([[36], [72], [36], [72]]) == [
            "bass",
            "treble",
            "bass",
            "treble",
        ]

    def test_overlapping_chord_around_middle_stays_together(self):
        # A C major triad around middle C is a single readable chord.
        assert assign_staffs([[60, 64, 67]]) == ["treble"]
        assert assign_staffs([[48, 52, 55]]) == ["bass"]

    def test_left_hand_crossing_above_middle_c_stays_on_bass(self):
        assert assign_staffs([[36], [43], [48], [64], [55], [48]]) == [
            "bass",
            "bass",
            "bass",
            "bass",
            "bass",
            "bass",
        ]

    def test_right_hand_dipping_below_middle_c_stays_on_treble(self):
        assert assign_staffs([[72], [76], [79], [60], [76]]) == [
            "treble",
            "treble",
            "treble",
            "treble",
            "treble",
        ]

    def test_wide_chord_spans_both_staves(self):
        assert assign_staffs([[36, 48, 72, 84]]) == ["split"]

    def test_stable_under_small_pitch_changes(self):
        # A clearly-registered line must not flip staffs under a +-1 semitone shift.
        treble_line = [67, 71, 74, 71, 67]
        bass_line = [40, 43, 48, 43, 40]
        for shift in (0, 1, 2):
            shifted_treble = [[p + shift] for p in treble_line]
            shifted_bass = [[p + shift] for p in bass_line]
            assert assign_staffs(shifted_treble) == ["treble"] * 5
            assert assign_staffs(shifted_bass) == ["bass"] * 5

    def test_split_pitches_at_largest_gap(self):
        lower, upper = split_pitches([36, 48, 72, 84])
        assert lower == [36, 48]
        assert upper == [72, 84]


def _midi_bytes(notes: list[tuple[float, float, int]]) -> bytes:
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    pm.time_signature_changes.append(
        pretty_midi.TimeSignature(numerator=4, denominator=4, time=0.0)
    )
    inst = pretty_midi.Instrument(program=0)
    for start, end, pitch in notes:
        inst.notes.append(pretty_midi.Note(velocity=80, pitch=pitch, start=start, end=end))
    pm.instruments.append(inst)
    buf = io.BytesIO()
    pm.write(buf)
    return buf.getvalue()


def _score_pitch_count(score) -> int:
    from music21 import stream

    total = 0
    for p in score.getElementsByClass(stream.PartStaff):
        for el in p.recurse().getElementsByClass(["Note", "Chord"]):
            total += len(el.pitches) if hasattr(el, "pitches") else 1
    return total


class TestGrandStaffFromMidi:
    def test_note_count_preserved_without_barline_crossings(self):
        # Notes confined to a single measure (no ties) must survive intact.
        midi = _midi_bytes(
            [
                (0.0, 0.5, 60),
                (0.5, 1.0, 64),
                (1.0, 1.5, 67),
                (0.0, 0.5, 36),  # simultaneous bass note -> chord on bass staff
            ]
        )
        score = grand_staff_from_midi(midi)
        assert _score_pitch_count(score) == 4

    def test_produces_two_staves_with_clefs(self):
        from music21 import stream

        midi = _midi_bytes([(0.0, 0.5, 36), (0.5, 1.0, 72), (1.0, 1.5, 48), (1.5, 2.0, 67)])
        score = grand_staff_from_midi(midi)
        staves = list(score.getElementsByClass(stream.PartStaff))
        assert len(staves) == 2
        clef_names = set()
        for staff in staves:
            for clef in staff.recurse().getElementsByClass("Clef"):
                clef_names.add(type(clef).__name__)
        assert clef_names == {"TrebleClef", "BassClef"}

    def test_bass_notes_on_bass_staff_treble_on_treble(self):
        from music21 import stream

        midi = _midi_bytes([(0.0, 0.5, 36), (0.5, 1.0, 76)])
        score = grand_staff_from_midi(midi)
        for staff in score.getElementsByClass(stream.PartStaff):
            clefs = [type(c).__name__ for c in staff.recurse().getElementsByClass("Clef")]
            pitches = [el.pitch.midi for el in staff.recurse().getElementsByClass("Note")]
            if "TrebleClef" in clefs:
                assert pitches == [76]
            else:
                assert pitches == [36]
