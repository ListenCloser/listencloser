"""Tests for cadence conservatism."""

from __future__ import annotations

import pytest

pytest.importorskip("music21", reason="music21 not installed")

from music21 import chord, key, stream  # noqa: E402

from analyze import _m21_cadences  # noqa: E402


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
