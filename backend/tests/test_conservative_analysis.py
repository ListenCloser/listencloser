"""Tests for conservative symbolic analysis."""

from __future__ import annotations

import pretty_midi

from analyze import _m21_phrases, _midi_melody, _midi_rhythm, _pick_melody_note


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
    def _write(self, pm):
        import io
        import tempfile

        buf = io.BytesIO()
        pm.write(buf)
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(buf.getvalue())
            return f.name

    def test_syncopation_unavailable_without_beat_hierarchy(self):
        """Syncopation is not reported from raw performance MIDI."""
        import os

        pm = _midi([_note(60, 0.0, 0.5), _note(64, 0.25, 0.75)])
        path = self._write(pm)
        try:
            result = _midi_rhythm(path)
            assert result is not None
            assert result["syncopation_available"] is False
            assert result["syncopation_ratio"] is None
            assert result["rhythmic_density"] > 0
        finally:
            os.unlink(path)
