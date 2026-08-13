"""Characterization/equivalence tests for the harmony and melody engines.

These lock the engine outputs to the pre-refactor analysis results so the
seam extraction is behavior-preserving. Deterministic, offline-safe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("music21", reason="music21 not installed")

from analyze import analyze_midi  # noqa: E402
from engines.harmony.music21_engine import Music21HarmonyEngine  # noqa: E402
from engines.melody.skyline_engine import SkylineMelodyEngine  # noqa: E402
from tests.fixtures.rhythmic import straight_eighths  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
PIANO_SYNTHETIC = FIXTURE_DIR / "music_eval" / "piano-synthetic.mid"


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _eighths_bytes() -> bytes:
    return straight_eighths()


class TestHarmonyEngineEquivalence:
    def test_piano_synthetic_harmony_matches_golden(self):
        harmony = Music21HarmonyEngine().analyze(_read_bytes(PIANO_SYNTHETIC))
        assert harmony.key == {"tonic": "F", "mode": "major", "confidence": 0.813}
        assert harmony.chords == []
        assert harmony.roman_numerals == [
            {"figure": "V", "root": "C", "quality": "M", "start": 0.0, "end": 1.0},
            {"figure": "I", "root": "F", "quality": "M", "start": 1.0, "end": 2.0},
            {"figure": "V", "root": "C", "quality": "M", "start": 2.0, "end": 3.0},
            {"figure": "I", "root": "F", "quality": "M", "start": 3.0, "end": 4.0},
        ]
        assert harmony.cadences
        assert all(c["evidence_score"] <= 0.8 for c in harmony.cadences)
        assert harmony.voice_leading is None
        assert harmony.phrases == []
        assert harmony.provenance.engine == "music21"

    def test_straight_eighths_harmony_matches_golden(self):
        harmony = Music21HarmonyEngine().analyze(_eighths_bytes(), tempo_bpm=120.0)
        assert harmony.key == {"tonic": "C", "mode": "minor", "confidence": 0.435}
        assert harmony.chords == []
        assert harmony.roman_numerals == []
        assert harmony.cadences == []
        assert harmony.modulations == []
        assert harmony.voice_leading is None
        assert harmony.phrases == []


class TestMelodyEngineEquivalence:
    def test_piano_synthetic_melody_matches_golden(self):
        melody = SkylineMelodyEngine().analyze(_read_bytes(PIANO_SYNTHETIC)).melody
        assert melody == {
            "low_pitch": 67,
            "high_pitch": 69,
            "range_semitones": 2,
            "unique_pitch_classes": 2,
            "stepwise_ratio": 1.0,
            "leap_ratio": 0.0,
            "quality_score": 0.032,
            "heuristic": "greedy_continuity_skyline",
        }

    def test_straight_eighths_melody_matches_golden(self):
        melody = SkylineMelodyEngine().analyze(_eighths_bytes()).melody
        assert melody == {
            "low_pitch": 60,
            "high_pitch": 67,
            "range_semitones": 7,
            "unique_pitch_classes": 8,
            "stepwise_ratio": 0.933,
            "leap_ratio": 0.067,
            "quality_score": 0.0,
            "heuristic": "greedy_continuity_skyline",
        }


class TestAnalyzeRoutesThroughEngines:
    def test_analyze_midi_includes_engine_provenance(self):
        analysis = analyze_midi(str(PIANO_SYNTHETIC))
        assert analysis["harmony_provenance"]["engine"] == "music21"
        assert analysis["melody_provenance"]["engine"] == "skyline"
        assert analysis["key"] == {"tonic": "F", "mode": "major", "confidence": 0.813}
        assert analysis["melody"]["heuristic"] == "greedy_continuity_skyline"

    def test_analyze_midi_matches_engine_outputs(self):
        midi_bytes = _read_bytes(PIANO_SYNTHETIC)
        analysis = analyze_midi(str(PIANO_SYNTHETIC))
        harmony = Music21HarmonyEngine().analyze(midi_bytes, tempo_bpm=120.0)
        melody = SkylineMelodyEngine().analyze(midi_bytes)
        assert analysis["key"] == harmony.key
        assert analysis["chords"] == harmony.chords
        assert analysis["roman_numerals"] == harmony.roman_numerals
        assert analysis["melody"] == melody.melody
