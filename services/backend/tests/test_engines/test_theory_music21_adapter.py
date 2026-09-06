"""Regression tests for the mir_eval + music21 production theory adapter."""

from __future__ import annotations

from engines.theory.theory_engine import TheoryEngine


def test_preserves_slash_bass_as_inversion() -> None:
    engine = TheoryEngine()
    result = engine.analyze(
        [{"root": "C", "quality": "maj/3", "start": 0.0, "end": 2.0}],
        global_key="C major",
    )

    assert len(result.roman_numerals) == 1
    assert result.roman_numerals[0].numeral == "I6"
    assert result.roman_numerals[0].inversion == "first"


def test_withholds_no_chord_instead_of_hallucinating_tonic() -> None:
    engine = TheoryEngine()
    result = engine.analyze(
        [{"root": "N", "quality": "N", "start": 0.0, "end": 2.0}],
        global_key="C major",
    )

    assert result.roman_numerals == []
    assert result.harmonic_functions == []


def test_preserves_half_diminished_seventh_evidence() -> None:
    engine = TheoryEngine()
    result = engine.analyze(
        [{"root": "B", "quality": "hdim7", "start": 0.0, "end": 2.0}],
        global_key="C major",
    )

    assert len(result.roman_numerals) == 1
    numeral = result.roman_numerals[0]
    assert "vii" in numeral.numeral.lower()
    assert "7" in numeral.numeral
    assert numeral.seventh is True


def test_direct_secondary_numeral_uses_music21_metadata() -> None:
    engine = TheoryEngine()
    result = engine.analyze(
        [{"numeral": "V/V", "start": 0.0, "end": 2.0}],
        global_key="C major",
    )

    assert len(result.roman_numerals) == 1
    numeral = result.roman_numerals[0]
    assert numeral.numeral == "V/V"
    assert numeral.is_secondary is True
    assert numeral.secondary_target == "V"
    assert result.harmonic_functions[0].function == "DOMINANT"


def test_provenance_names_oss_theory_stack() -> None:
    provenance = TheoryEngine().provenance

    assert provenance.engine == "theory_interpreter"
    assert provenance.model == "mir_eval_harte_to_music21"
    assert provenance.parameters["mir_eval_version"] == "0.8.2"
    assert provenance.parameters["input_contract"] == "trusted_key_plus_lv_chordia_jams"
