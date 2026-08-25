"""Tests for melody interpretation engine."""

from engines.melody.interpretation import (
    MelodyNote,
    _classify_contour,
    _interval_name,
    _pitch_name,
    interpret_melody,
)


class TestPitchName:
    def test_middle_c(self):
        assert _pitch_name(60) == "C4"

    def test_a440(self):
        assert _pitch_name(69) == "A4"

    def test_high_c(self):
        assert _pitch_name(84) == "C6"


class TestIntervalName:
    def test_unison(self):
        assert _interval_name(0) == "unison"

    def test_octave(self):
        assert _interval_name(12) == "octave"

    def test_perfect_fifth(self):
        assert _interval_name(7) == "perfect 5th"


class TestClassifyContour:
    def test_ascending(self):
        assert _classify_contour([60, 62, 64, 65, 67]) == "ascending"

    def test_descending(self):
        assert _classify_contour([72, 70, 68, 67, 65]) == "descending"

    def test_static(self):
        assert _classify_contour([60, 60, 60, 60]) == "static"

    def test_arch(self):
        assert _classify_contour([60, 62, 64, 67, 64, 62, 60]) == "arch"


class TestInterpretMelody:
    def _make_notes(self, pitches, start_interval=0.5):
        return [
            MelodyNote(
                pitch=p,
                start_seconds=i * start_interval,
                end_seconds=(i + 1) * start_interval,
            )
            for i, p in enumerate(pitches)
        ]

    def test_too_few_notes(self):
        notes = self._make_notes([60, 62, 64])
        assert interpret_melody(notes) == []

    def test_register_events(self):
        notes = self._make_notes([60, 62, 64, 65, 67, 69, 71, 72])
        findings = interpret_melody(notes)
        kinds = [f.kind for f in findings]
        assert "melody_register_peak" in kinds
        assert "melody_register_low" in kinds

        peak = next(f for f in findings if f.kind == "melody_register_peak")
        assert peak.evidence["pitch"] == 72
        assert peak.start_seconds == 3.5

        low = next(f for f in findings if f.kind == "melody_register_low")
        assert low.evidence["pitch"] == 60
        assert low.start_seconds == 0.0

    def test_interval_summary(self):
        notes = self._make_notes([60, 62, 64, 65, 67, 69, 71, 72])
        findings = interpret_melody(notes)
        kinds = [f.kind for f in findings]
        assert "melody_interval_summary" in kinds

        summary = next(f for f in findings if f.kind == "melody_interval_summary")
        assert summary.evidence["stepwise_ratio"] == 1.0
        assert summary.evidence["leap_ratio"] == 0.0

    def test_large_leap(self):
        # C4, G4 (perfect 5th), C5, D5, E5, F5, G5, A5
        notes = self._make_notes([60, 67, 72, 74, 76, 77, 79, 81])
        findings = interpret_melody(notes)
        kinds = [f.kind for f in findings]
        assert "melody_large_leap" not in kinds  # 7 semitones is not "large" (>=8)

        # Now with an octave leap
        notes = self._make_notes([60, 72, 74, 76, 77, 79, 81, 83])
        findings = interpret_melody(notes)
        kinds = [f.kind for f in findings]
        assert "melody_large_leap" in kinds

    def test_contour_detection(self):
        notes = self._make_notes([60, 62, 64, 65, 67, 69, 71, 72])
        findings = interpret_melody(notes)
        kinds = [f.kind for f in findings]
        assert "melody_contour_ascending" in kinds

    def test_findings_have_provenance(self):
        notes = [
            MelodyNote(pitch=60, start_seconds=0.0, end_seconds=0.5, note_id="n1"),
            MelodyNote(pitch=62, start_seconds=0.5, end_seconds=1.0, note_id="n2"),
            MelodyNote(pitch=64, start_seconds=1.0, end_seconds=1.5, note_id="n3"),
            MelodyNote(pitch=65, start_seconds=1.5, end_seconds=2.0, note_id="n4"),
            MelodyNote(pitch=67, start_seconds=2.0, end_seconds=2.5, note_id="n5"),
            MelodyNote(pitch=69, start_seconds=2.5, end_seconds=3.0, note_id="n6"),
            MelodyNote(pitch=71, start_seconds=3.0, end_seconds=3.5, note_id="n7"),
            MelodyNote(pitch=72, start_seconds=3.5, end_seconds=4.0, note_id="n8"),
        ]
        findings = interpret_melody(notes)
        peak = next(f for f in findings if f.kind == "melody_register_peak")
        assert peak.note_ids == ["n8"]
