"""Tests for the theory interpretation engine."""

from __future__ import annotations

import pytest


class TestTheoryEngine:
    """Tests for TheoryEngine."""

    def test_import(self):
        """Engine can be imported."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        assert engine is not None

    def test_provenance(self):
        """Engine reports correct provenance."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        p = engine.provenance
        assert p.engine == "theory_interpreter"

    def test_analyze_empty(self):
        """Engine handles empty input."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        result = engine.analyze([], global_key="C major")
        assert result.roman_numerals == []
        assert result.harmonic_functions == []

    def test_analyze_chord_names(self):
        """Engine converts chord names to Roman numerals."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        chords = [
            {"root": "C", "quality": "maj", "start": 0.0, "end": 2.0},
            {"root": "G", "quality": "maj", "start": 2.0, "end": 4.0},
            {"root": "F", "quality": "maj", "start": 4.0, "end": 6.0},
        ]
        result = engine.analyze(chords, global_key="C major")
        assert len(result.roman_numerals) == 3
        assert result.roman_numerals[0].numeral == "I"
        assert result.roman_numerals[1].numeral == "V"
        assert result.roman_numerals[2].numeral == "IV"

    def test_analyze_minor_key(self):
        """Engine handles minor keys."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        chords = [
            {"root": "A", "quality": "min", "start": 0.0, "end": 2.0},
            {"root": "E", "quality": "maj", "start": 2.0, "end": 4.0},
            {"root": "D", "quality": "min", "start": 4.0, "end": 6.0},
        ]
        result = engine.analyze(chords, global_key="A minor")
        assert len(result.roman_numerals) == 3
        assert result.roman_numerals[0].numeral == "i"
        assert result.roman_numerals[1].numeral == "V"
        assert result.roman_numerals[2].numeral == "iv"

    def test_harmonic_function(self):
        """Engine classifies harmonic function."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        chords = [
            {"root": "C", "quality": "maj", "start": 0.0, "end": 2.0},
            {"root": "G", "quality": "maj", "start": 2.0, "end": 4.0},
            {"root": "F", "quality": "maj", "start": 4.0, "end": 6.0},
        ]
        result = engine.analyze(chords, global_key="C major")
        assert len(result.harmonic_functions) == 3
        assert result.harmonic_functions[0].function == "TONIC"
        assert result.harmonic_functions[1].function == "DOMINANT"
        assert result.harmonic_functions[2].function == "SUBDOMINANT"

    def test_key_detection(self):
        """Engine detects key from chord sequence."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        chords = [
            {"root": "C", "quality": "maj", "start": 0.0, "end": 2.0},
            {"root": "G", "quality": "maj", "start": 2.0, "end": 4.0},
            {"root": "F", "quality": "maj", "start": 4.0, "end": 6.0},
        ]
        result = engine.analyze(chords)
        assert result.global_key is not None

    def test_seventh_chords(self):
        """Engine handles seventh chords."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        chords = [
            {"root": "G", "quality": "7", "start": 0.0, "end": 2.0},
            {"root": "C", "quality": "maj", "start": 2.0, "end": 4.0},
        ]
        result = engine.analyze(chords, global_key="C major")
        assert result.roman_numerals[0].numeral == "V7"
        assert result.roman_numerals[0].seventh is True

    def test_minor_seventh_chords(self):
        """Engine handles minor seventh chords."""
        from engines.theory.theory_engine import TheoryEngine
        engine = TheoryEngine()
        chords = [
            {"root": "D", "quality": "min7", "start": 0.0, "end": 2.0},
            {"root": "G", "quality": "7", "start": 2.0, "end": 4.0},
            {"root": "C", "quality": "maj", "start": 4.0, "end": 6.0},
        ]
        result = engine.analyze(chords, global_key="C major")
        assert result.roman_numerals[0].numeral == "ii7"
        assert result.roman_numerals[1].numeral == "V7"
        assert result.roman_numerals[2].numeral == "I"


class TestRegistryIntegration:
    """Tests for theory engine registry integration."""

    def test_theory_engine_in_registry(self):
        """Theory engine can be retrieved from the registry."""
        from engines.registry import get_theory_engine
        engine = get_theory_engine()
        assert engine is not None
        assert hasattr(engine, "analyze")

    def test_unknown_engine_raises(self):
        """Unknown engine names raise ValueError."""
        from engines.registry import get_theory_engine
        with pytest.raises(ValueError, match="Unknown theory engine"):
            get_theory_engine("nonexistent")
