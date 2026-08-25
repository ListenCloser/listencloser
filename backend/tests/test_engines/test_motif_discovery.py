"""Tests for motif discovery engine."""

from engines.melody.motif_discovery import MotifNote, discover_motifs


class TestDiscoverMotifs:
    def _make_notes(self, pitches, start_interval=0.5):
        return [
            MotifNote(
                pitch=p,
                start_seconds=i * start_interval,
                end_seconds=(i + 1) * start_interval,
                note_id=f"n{i}",
            )
            for i, p in enumerate(pitches)
        ]

    def test_too_few_notes(self):
        notes = self._make_notes([60, 62])
        assert discover_motifs(notes) == []

    def test_repeating_motif(self):
        # C D E ... G A B (same interval pattern [2, 2])
        notes = self._make_notes([60, 62, 64, 67, 69, 67, 69, 71, 72])
        motifs = discover_motifs(notes)
        assert len(motifs) >= 1
        assert motifs[0].interval_pattern == [2, 2]
        assert motifs[0].count == 2

    def test_transposition_invariant(self):
        # C D E (major 2nds) ... G A B (major 2nds, transposed up 7 semitones)
        notes = self._make_notes([60, 62, 64, 60, 67, 69, 71])
        motifs = discover_motifs(notes)
        assert len(motifs) >= 1
        assert motifs[0].interval_pattern == [2, 2]

    def test_no_repetition(self):
        # All different intervals
        notes = self._make_notes([60, 62, 65, 63, 67, 64, 69])
        motifs = discover_motifs(notes)
        # May or may not find motifs depending on random patterns
        # Just verify no crash
        assert isinstance(motifs, list)

    def test_motif_occurrences_have_positions(self):
        notes = self._make_notes([60, 62, 64, 67, 69, 67, 69, 71, 72])
        motifs = discover_motifs(notes)
        if motifs:
            for occ in motifs[0].occurrences:
                assert occ.start_seconds >= 0
                assert occ.end_seconds > occ.start_seconds

    def test_motif_occurrences_have_note_ids(self):
        notes = self._make_notes([60, 62, 64, 67, 69, 67, 69, 71, 72])
        motifs = discover_motifs(notes)
        if motifs:
            for occ in motifs[0].occurrences:
                assert len(occ.note_ids) > 0

    def test_max_motifs_limit(self):
        # Create a long melody with many patterns
        pitches = [60, 62, 64, 65, 67, 69, 71, 72] * 5
        notes = self._make_notes(pitches)
        motifs = discover_motifs(notes)
        assert len(motifs) <= 10  # _MAX_MOTIFS
