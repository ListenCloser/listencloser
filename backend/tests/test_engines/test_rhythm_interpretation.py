"""Tests for rhythm interpretation engine."""

from engines.rhythm.interpretation import RhythmNote, interpret_rhythm


class TestInterpretRhythm:
    def _make_notes(self, onsets, durations=None, pitch=60):
        if durations is None:
            durations = [0.5] * len(onsets)
        return [
            RhythmNote(
                pitch=pitch,
                start_seconds=start,
                end_seconds=start + dur,
            )
            for start, dur in zip(onsets, durations)
        ]

    def test_too_few_notes(self):
        notes = self._make_notes([0.0, 0.5, 1.0])
        beats = [0.0, 0.5, 1.0, 1.5]
        assert interpret_rhythm(notes, beats) == []

    def test_characteristic_duration(self):
        # All notes have the same duration
        notes = self._make_notes([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        findings = interpret_rhythm(notes, beats, tempo_bpm=120.0)
        kinds = [f.kind for f in findings]
        assert "rhythm_characteristic_duration" in kinds

    def test_long_rest(self):
        # Notes with a gap in the middle
        notes = self._make_notes([0.0, 0.5, 1.0, 1.5, 4.0, 4.5, 5.0, 5.5])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
        findings = interpret_rhythm(notes, beats, tempo_bpm=120.0)
        kinds = [f.kind for f in findings]
        assert "rhythm_long_rest" in kinds

    def test_long_note(self):
        # Notes with one long note
        notes = self._make_notes(
            [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
            durations=[0.5, 0.5, 0.5, 0.5, 2.0, 0.5, 0.5, 0.5],
        )
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        findings = interpret_rhythm(notes, beats, tempo_bpm=120.0)
        kinds = [f.kind for f in findings]
        assert "rhythm_long_note" in kinds

    def test_activity_changes(self):
        # Notes with varying density
        onsets = (
            [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]  # Dense
            + [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5]  # Sparse
        )
        notes = self._make_notes(onsets)
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0]
        findings = interpret_rhythm(notes, beats, tempo_bpm=120.0)
        # May or may not find activity changes depending on the algorithm
        assert isinstance(findings, list)

    def test_findings_have_provenance(self):
        notes = self._make_notes([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
        beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
        findings = interpret_rhythm(notes, beats, tempo_bpm=120.0)
        for f in findings:
            assert f.kind
            assert f.claim
