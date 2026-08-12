"""Tests for cadence and modulation conservatism."""

from __future__ import annotations

import pytest

pytest.importorskip("music21", reason="music21 not installed")

from music21 import chord, key, note, stream

from analyze import _detect_modulations, _key_from_pc_vector, _m21_cadences


def _make_score(chords: list[tuple[str, float]]):
    """Build a single-part score of chords at given quarter-note offsets."""
    s = stream.Score()
    p = stream.Part()
    m = stream.Measure()
    for ch_str, offset in chords:
        c = chord.Chord(ch_str.split())
        c.offset = offset
        c.quarterLength = 1.0
        m.insert(c)
    p.append(m)
    s.insert(0, p)
    return s


class TestCadenceConservatism:
    def test_v_i_mid_phrase_is_not_strong_cadence(self):
        """V-I in the middle of a measure should carry only an evidence score."""
        score = _make_score([("C E G", 0.0), ("G B D", 1.0), ("C E G", 2.0)])
        detected = key.Key("C")
        cands = _m21_cadences(score, detected)
        for c in cands:
            assert c["evidence_score"] <= 0.8
            assert "evidence" in c
            assert "confidence" not in c

    def test_cadence_candidate_has_evidence(self):
        score = _make_score([("G B D", 0.0), ("C E G", 1.0)])
        detected = key.Key("C")
        cands = _m21_cadences(score, detected)
        assert isinstance(cands, list)
        for c in cands:
            assert c["type"] in ("authentic", "plagal", "half", "deceptive")
            assert "chords" in c
            assert "evidence_score" in c


class TestModulationConservatism:
    def test_one_window_change_is_not_modulation(self):
        """A stable single-key piece should produce no modulation events."""
        s = stream.Score()
        p = stream.Part()
        m = stream.Measure()
        c_major_scale = ["C", "D", "E", "F", "G", "A", "B", "C5"]
        for i, pitch in enumerate(c_major_scale * 8):
            n = note.Note(pitch)
            n.offset = i * 0.5
            m.insert(n)
        p.append(m)
        s.insert(0, p)
        mods = _detect_modulations(s, 120.0)
        # A stable piece should produce no modulation/tonicization events.
        assert len(mods) == 0

    def test_modulation_has_evidence_not_confidence(self):
        s = stream.Score()
        p = stream.Part()
        m = stream.Measure()
        for i, pitch in enumerate(["C", "D", "E", "F", "G", "A", "B", "C5"] * 8):
            n = note.Note(pitch)
            n.offset = i * 0.5
            m.insert(n)
        p.append(m)
        s.insert(0, p)
        mods = _detect_modulations(s, 120.0)
        for mod in mods:
            assert mod["kind"] in ("possible_tonicization", "possible_modulation")
            assert "run_length_windows" in mod
            assert "duration_seconds" in mod
            assert "confidence" not in mod


class TestKeyFromPCVector:
    def test_empty_vector_returns_none(self):
        import numpy as np

        result = _key_from_pc_vector(np.zeros(12))
        assert result is None
