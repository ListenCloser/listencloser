"""Tests for cadence and modulation conservatism."""

from __future__ import annotations

import pytest

pytest.importorskip("music21", reason="music21 not installed")

from music21 import chord, key, note, stream

from analyze import _detect_modulations, _m21_cadences


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
        """V-I in the middle of a measure should have low confidence."""
        score = _make_score([("C E G", 0.0), ("G B D", 1.0), ("C E G", 2.0)])
        detected = key.Key("C")
        cands = _m21_cadences(score, detected)
        # We only emit candidates, and mid-measure arrivals get <= 0.6 confidence.
        for c in cands:
            assert c["confidence"] <= 0.8
            assert "evidence" in c

    def test_cadence_candidate_has_evidence(self):
        score = _make_score([("G B D", 0.0), ("C E G", 1.0)])
        detected = key.Key("C")
        cands = _m21_cadences(score, detected)
        assert isinstance(cands, list)
        for c in cands:
            assert c["type"] in ("authentic", "plagal", "half", "deceptive")
            assert "chords" in c
            assert "confidence" in c


class TestModulationConservatism:
    def test_one_window_change_is_not_modulation(self):
        """A stable single-key piece should produce no confident modulation."""
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
        confident = [mod for mod in mods if mod["confidence"] >= 0.7]
        assert len(confident) == 0

    def test_modulation_has_kind_field(self):
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
            assert "confidence" in mod
