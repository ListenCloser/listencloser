"""Truthfulness tests for withheld cadence analysis."""

from __future__ import annotations

import pytest

pytest.importorskip("music21", reason="music21 not installed")

from music21 import chord, key, roman, stream  # noqa: E402

from engines.harmony.music21_engine import (  # noqa: E402
    Music21HarmonyEngine,
    _m21_cadences,
)


def _dominant_tonic_score() -> tuple[stream.Score, key.Key]:
    score = stream.Score()
    part = stream.Part()
    measure = stream.Measure(number=1)

    dominant = chord.Chord(["G3", "B3", "D4"], quarterLength=1.0)
    tonic = chord.Chord(["C4", "E4", "G4"], quarterLength=2.0)
    measure.append(dominant)
    measure.append(tonic)
    part.append(measure)
    score.insert(0, part)
    return score, key.Key("C")


def test_textbook_v_i_is_not_sufficient_cadence_evidence() -> None:
    score, detected_key = _dominant_tonic_score()
    chords = list(score.parts[0].recurse().getElementsByClass("Chord"))

    # Establish that the fixture is exactly the progression the retired
    # adjacent-RN rule used to label as an authentic cadence.
    assert roman.romanNumeralFromChord(chords[0], detected_key).figure == "V"
    assert roman.romanNumeralFromChord(chords[1], detected_key).figure == "I"

    # A progression alone does not establish phrase closure. Until #1043 has a
    # validated cadence detector, the symbolic harmony route must abstain.
    assert _m21_cadences(score, detected_key) == []


def test_cadence_provenance_records_withheld_abstention() -> None:
    cadence_provenance = Music21HarmonyEngine().component_provenance()["cadences"]

    assert cadence_provenance.engine == "unavailable"
    assert cadence_provenance.parameters == {"status": "withheld", "returns_empty": True}
