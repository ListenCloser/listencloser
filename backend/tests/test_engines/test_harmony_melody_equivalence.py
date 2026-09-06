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
        assert harmony.chords == [
            {"root": "C", "quality": "M", "start": 0.0, "end": 1.0},
            {"root": "F", "quality": "M", "start": 1.0, "end": 2.0},
            {"root": "C", "quality": "M", "start": 2.0, "end": 3.0},
            {"root": "F", "quality": "M", "start": 3.0, "end": 4.0},
        ]
        assert harmony.roman_numerals == [
            {"figure": "V", "root": "C", "quality": "M", "start": 0.0, "end": 1.0},
            {"figure": "I", "root": "F", "quality": "M", "start": 1.0, "end": 2.0},
            {"figure": "V", "root": "C", "quality": "M", "start": 2.0, "end": 3.0},
            {"figure": "I", "root": "F", "quality": "M", "start": 3.0, "end": 4.0},
        ]
        assert harmony.cadences == []
        assert harmony.voice_leading is None
        assert harmony.phrases == []
        assert harmony.provenance.engine == "music21"

    def test_straight_eighths_harmony_matches_golden(self):
        harmony = Music21HarmonyEngine().analyze(_eighths_bytes(), tempo_bpm=120.0)
        assert harmony.key == {"tonic": "C", "mode": "minor", "confidence": 0.435}
        assert harmony.chords == []
        assert harmony.roman_numerals == []
        assert harmony.cadences == []
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
    @pytest.mark.integration
    @pytest.mark.worker
    def test_analyze_midi_includes_engine_provenance(self):
        analysis = analyze_midi(str(PIANO_SYNTHETIC))
        hp = analysis["harmony_provenance"]
        assert hp["key"]["engine"] == "music21"
        assert hp["chords"]["engine"] == "music21"
        assert hp["roman_numerals"]["engine"] == "music21"
        assert hp["cadences"]["engine"] == "unavailable"
        assert hp["cadences"]["parameters"] == {"status": "withheld", "returns_empty": True}
        assert analysis["melody_provenance"]["engine"] == "lstom"
        assert analysis["key"] == {"tonic": "F", "mode": "major", "confidence": 0.813}
        # LStoM returns None for very short MIDI (<50 notes) — provenance
        # still records that lstom was the engine that ran.
        if analysis["melody"] is not None:
            assert analysis["melody"]["heuristic"] == "lstom_biLSTM"

    def test_withheld_components_do_not_claim_music21(self):
        """Withheld cadence provenance must not imply music21 produced it."""
        hp = Music21HarmonyEngine().component_provenance()
        assert hp["cadences"].engine == "unavailable"
        assert hp["cadences"].parameters == {"status": "withheld", "returns_empty": True}
        assert hp["phrases"].parameters["returns_empty"] is True

    @pytest.mark.integration
    @pytest.mark.worker
    def test_analyze_midi_matches_engine_outputs(self):
        from engines.melody.lstom_engine import LStoMMelodyEngine

        midi_bytes = _read_bytes(PIANO_SYNTHETIC)
        analysis = analyze_midi(str(PIANO_SYNTHETIC))
        harmony = Music21HarmonyEngine().analyze(midi_bytes, tempo_bpm=120.0)
        melody = LStoMMelodyEngine().analyze(midi_bytes)
        assert analysis["key"] == harmony.key
        assert analysis["chords"] == harmony.chords
        # Truthfulness invariant: the pipeline suppresses Roman numerals when
        # there is no chord evidence, even though the engine can still derive
        # them from the raw score.
        if harmony.chords:
            assert analysis["roman_numerals"] == harmony.roman_numerals
        else:
            assert analysis["roman_numerals"] == []
        assert analysis["melody"] == melody.melody


class TestIntentionalBehaviorChange:
    @pytest.mark.integration
    @pytest.mark.worker
    def test_harmony_failure_keeps_rhythm_and_melody(self, monkeypatch):
        """Intentional (only) behavior change vs pre-refactor: a harmony-engine
        failure no longer aborts the whole analysis. Rhythm/melody still run
        and harmony stays in its conservative no-evidence state."""

        def boom(*_args, **_kwargs):
            raise RuntimeError("harmony engine exploded")

        monkeypatch.setattr("analyze.get_harmony_engine", boom)
        analysis = analyze_midi(str(PIANO_SYNTHETIC))
        assert analysis["key"] is None
        assert analysis["chords"] == []
        assert analysis["roman_numerals"] == []
        assert analysis["harmony_provenance"] == {}
        # LStoM may return None for very short MIDI (<50 notes), so check
        # that melody_provenance is present (engine ran) regardless of output.
        assert "melody_provenance" in analysis
        assert analysis["rhythm"] is not None
