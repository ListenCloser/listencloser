"""Tests for GuitarSet / BabySlakh annotation parsers."""

from __future__ import annotations

import io
import json

import pretty_midi

from evaluation.datasets.parsers import (
    parse_babyslakh_midi,
    parse_guitarset_harmony,
    parse_guitarset_jams,
)


class TestGuitarSetJams:
    def _jams(self, notes):
        return json.dumps(
            {
                "annotations": [
                    {"namespace": "pitch_contour", "data": []},
                    {
                        "namespace": "note_midi",
                        "data": [
                            {"time": n[0], "duration": n[1], "value": n[2], "confidence": None}
                            for n in notes
                        ],
                    },
                ],
                "file_metadata": {},
                "sandbox": {},
            }
        )

    def test_parses_note_midi_and_rounds_fractional_pitch(self):
        jams = self._jams(
            [
                (0.0, 0.5, 60.2),  # rounds to 60
                (0.5, 0.5, 64.6),  # rounds to 65
            ]
        )
        notes = parse_guitarset_jams(jams)
        assert len(notes) == 2
        assert notes[0]["pitch"] == 60
        assert notes[0]["start"] == 0.0
        assert notes[0]["end"] == 0.5
        assert notes[1]["pitch"] == 65

    def test_ignores_non_note_midi_namespaces(self):
        jams = json.dumps(
            {
                "annotations": [
                    {"namespace": "chord", "data": [{"time": 0, "value": "C:maj"}]},
                    {"namespace": "note_midi", "data": []},
                ],
            }
        )
        assert parse_guitarset_jams(jams) == []

    def test_skips_missing_value(self):
        jams = json.dumps(
            {
                "annotations": [
                    {"namespace": "note_midi", "data": [{"time": 0, "duration": 0.5}]},
                ],
            }
        )
        assert parse_guitarset_jams(jams) == []


class TestBabySlakhMidi:
    def _midi(self, drums=True, notes=2):
        pm = pretty_midi.PrettyMIDI(initial_tempo=120)
        inst = pretty_midi.Instrument(program=0, is_drum=False)
        for i in range(notes):
            inst.notes.append(
                pretty_midi.Note(velocity=80, pitch=60 + i, start=i * 0.5, end=i * 0.5 + 0.4)
            )
        pm.instruments.append(inst)
        if drums:
            drum = pretty_midi.Instrument(program=0, is_drum=True)
            drum.notes.append(pretty_midi.Note(velocity=90, pitch=36, start=0.0, end=0.1))
            pm.instruments.append(drum)
        buf = io.BytesIO()
        pm.write(buf)
        return buf.getvalue()

    def test_excludes_drums(self):
        notes = parse_babyslakh_midi(self._midi(drums=True, notes=3), exclude_drums=True)
        pitches = [n["pitch"] for n in notes]
        assert 36 not in pitches  # drum note excluded
        assert len(notes) == 3

    def test_includes_drums_when_requested(self):
        notes = parse_babyslakh_midi(self._midi(drums=True, notes=1), exclude_drums=False)
        pitches = [n["pitch"] for n in notes]
        assert 36 in pitches  # drum note included

    def test_note_fields(self):
        notes = parse_babyslakh_midi(self._midi(drums=False, notes=1))
        assert notes[0]["pitch"] == 60
        assert notes[0]["start"] == 0.0
        assert notes[0]["velocity"] == 80


class TestGuitarSetHarmony:
    def _jams(self, chords, key_mode=None):
        annotations = [
            {
                "namespace": "chord",
                "data": [
                    {"time": c[0], "duration": c[1], "value": c[2], "confidence": None}
                    for c in chords
                ],
            },
            {
                "namespace": "chord",
                "data": [{"time": 0, "duration": 1, "value": "C:maj/3", "confidence": None}],
            },
        ]
        if key_mode is not None:
            annotations.append(
                {
                    "namespace": "key_mode",
                    "data": [{"time": 0, "duration": 1, "value": key_mode, "confidence": 1}],
                }
            )
        return json.dumps({"annotations": annotations})

    def test_major_and_minor_qualities(self):
        jams = self._jams(
            [
                (0.0, 2.0, "C:maj"),
                (2.0, 2.0, "A:min"),
            ],
            key_mode="C:major",
        )
        result = parse_guitarset_harmony(jams)
        assert [c["quality"] for c in result["chords"]] == ["M", "m"]
        assert [c["root"] for c in result["chords"]] == ["C", "A"]

    def test_enharmonic_normalization(self):
        # GuitarSet chords use sharps (D#), key_mode uses flats (Eb). Roots
        # must be normalized to the flat spelling for consistent comparison.
        jams = self._jams([(0.0, 2.0, "D#:maj")], key_mode="Eb:major")
        result = parse_guitarset_harmony(jams)
        assert result["chords"][0]["root"] == "Eb"
        assert result["key"]["tonic"] == "Eb"

    def test_no_chord_label_is_skipped(self):
        # "N" (no-chord) has no root; it must not produce a chord entry.
        jams = self._jams([(0.0, 2.0, "C:maj"), (2.0, 2.0, "N")], key_mode="C:major")
        result = parse_guitarset_harmony(jams)
        assert [c["root"] for c in result["chords"]] == ["C"]

    def test_key_mode(self):
        jams = self._jams([(0.0, 2.0, "C:maj")], key_mode="D:minor")
        result = parse_guitarset_harmony(jams)
        assert result["key"]["tonic"] == "D"
        assert result["key"]["mode"] == "minor"
        assert result["key"]["confidence"] == 1.0

    def test_timestamps_and_duration(self):
        jams = self._jams([(1.25, 2.5, "C:maj")], key_mode="C:major")
        result = parse_guitarset_harmony(jams)
        assert result["chords"][0]["start"] == 1.25
        assert result["chords"][0]["end"] == 3.75  # 1.25 + 2.5

    def test_unknown_quality_falls_back_to_raw(self):
        jams = self._jams([(0.0, 2.0, "G:maj7")], key_mode="C:major")
        result = parse_guitarset_harmony(jams)
        assert result["chords"][0]["quality"] == "maj7"
        assert result["chords"][0]["root"] == "G"

    def test_missing_key_mode_yields_empty_key(self):
        jams = self._jams([(0.0, 2.0, "C:maj")])
        result = parse_guitarset_harmony(jams)
        assert result["key"] == {}
