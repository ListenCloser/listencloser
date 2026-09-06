"""Tests for conservative symbolic analysis."""

from __future__ import annotations

import pretty_midi

from analyze import _beat_phase_distribution, _midi_rhythm
from engines.harmony.music21_engine import _m21_phrases
from engines.melody.skyline_engine import _midi_melody, _pick_melody_note


def _note(pitch, start, end, vel=80):
    return pretty_midi.Note(velocity=vel, pitch=pitch, start=start, end=end)


def _midi(notes, time_sigs=None):
    pm = pretty_midi.PrettyMIDI(initial_tempo=120)
    inst = pretty_midi.Instrument(program=0)
    inst.notes = notes
    pm.instruments.append(inst)
    if time_sigs:
        for num, den, t in time_sigs:
            pm.time_signature_changes.append(pretty_midi.TimeSignature(num, den, t))
    return pm


class TestPhrases:
    def test_phrases_return_empty(self):
        """Phrase analysis is removed — must not fabricate phrase spans."""
        assert _m21_phrases(None) == []


class TestMelodyHeuristic:
    def test_prefers_sustained_nearby_over_isolated_high(self):
        sustained = _note(60, 0.0, 1.0)
        spike = _note(84, 0.0, 0.05)
        chosen, margin = _pick_melody_note([sustained, spike], None)
        assert chosen is not None
        assert chosen.pitch == 60
        assert margin > 0

    def test_prefers_stepwise_continuation(self):
        near = _note(62, 1.0, 1.5)
        far = _note(72, 1.0, 1.5)
        prev = _note(60, 0.0, 0.5)
        chosen, _ = _pick_melody_note([near, far], prev)
        assert chosen is not None
        assert chosen.pitch == 62

    def test_melody_has_quality_score(self):
        import io
        import os
        import tempfile

        pm = _midi([_note(60, 0.0, 0.5), _note(64, 0.5, 1.0)])
        buf = io.BytesIO()
        pm.write(buf)
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(buf.getvalue())
            path = f.name
        try:
            result = _midi_melody(path)
            assert result is not None
            assert "quality_score" in result
            assert result["heuristic"] == "greedy_continuity_skyline"
        finally:
            os.unlink(path)


class TestRhythmSyncopation:
    def test_beat_phase_distribution_reports_measurement_not_syncopation(self):
        result = _beat_phase_distribution([0.0, 0.24, 0.51, 0.76, 1.0], [0.0, 1.0, 2.0])
        assert [bucket["count"] for bucket in result] == [3, 0, 1, 1]
        assert sum(bucket["fraction"] for bucket in result) == 1.0

    def _write(self, pm):
        import io
        import tempfile

        buf = io.BytesIO()
        pm.write(buf)
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(buf.getvalue())
            return f.name

    def test_syncopation_unavailable_without_beat_grid(self):
        """The off-beat onset fraction is not reported without a beat grid."""
        import os

        pm = _midi([_note(60, 0.0, 0.5), _note(64, 0.25, 0.75)])
        path = self._write(pm)
        try:
            result = _midi_rhythm(path)
            assert result is not None
            assert result["offbeat_onset_available"] is False
            assert result["offbeat_onset_ratio"] is None
            assert result["rhythmic_density"] > 0
        finally:
            os.unlink(path)
