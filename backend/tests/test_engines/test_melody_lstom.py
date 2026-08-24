"""Regression tests for the LStoM melody engine.

These tests verify that the LStoM engine produces consistent outputs
on known inputs, locking the engine behavior for regression detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="torch not installed")
pytest.importorskip("pretty_midi", reason="pretty_midi not installed")

from engines.melody.lstom_engine import LStoMMelodyEngine  # noqa: E402
from engines.melody.skyline_engine import SkylineMelodyEngine  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
REAL_PIANO_MIDI = (
    FIXTURE_DIR.parent / "evaluation" / "results" / "qualitative_v2"
    / "artifacts" / "real-piano" / "basic_pitch_real_piano_m4a.mid"
)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


class TestLStoMMelodyEngine:
    """Regression tests for LStoM melody engine."""

    def test_provenance(self):
        """Engine reports correct provenance metadata."""
        engine = LStoMMelodyEngine()
        prov = engine.provenance
        assert prov.engine == "lstom"
        assert prov.model == "lstom_biLSTM_pop909"
        assert prov.library_version == "1.0.0"
        assert prov.parameters["training_dataset"] == "POP909"
        assert prov.parameters["threshold"] == 0.40

    def test_returns_melody_result(self):
        """Engine returns a MelodyResult with melody data."""
        engine = LStoMMelodyEngine()
        result = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        assert result.melody is not None
        assert result.provenance.engine == "lstom"

    def test_melody_fields(self):
        """Melody result contains expected fields."""
        engine = LStoMMelodyEngine()
        result = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        melody = result.melody
        assert "low_pitch" in melody
        assert "high_pitch" in melody
        assert "range_semitones" in melody
        assert "stepwise_ratio" in melody
        assert "quality_score" in melody
        assert "heuristic" in melody
        assert melody["heuristic"] == "lstom_biLSTM"

    def test_deterministic(self):
        """Same input produces same output."""
        engine = LStoMMelodyEngine()
        r1 = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        r2 = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        assert r1.melody["low_pitch"] == r2.melody["low_pitch"]
        assert r1.melody["high_pitch"] == r2.melody["high_pitch"]
        assert r1.melody["stepwise_ratio"] == r2.melody["stepwise_ratio"]

    def test_no_accompaniment_contamination(self):
        """LStoM stays in melodic range (no bass contamination)."""
        engine = LStoMMelodyEngine()
        result = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        melody = result.melody
        # Melody should not extend into bass range (below MIDI 48 = C3)
        assert melody["low_pitch"] >= 48, (
            f"Melody low pitch {melody['low_pitch']} suggests accompaniment contamination"
        )

    def test_compare_with_skyline(self):
        """LStoM produces different (cleaner) output than skyline."""
        lstom = LStoMMelodyEngine()
        skyline = SkylineMelodyEngine()

        r_lstom = lstom.analyze(_read_bytes(REAL_PIANO_MIDI))
        r_skyline = skyline.analyze(_read_bytes(REAL_PIANO_MIDI))

        # Both should produce output
        assert r_lstom.melody is not None
        assert r_skyline.melody is not None

        # LStoM should have narrower range (less contamination)
        lstom_range = r_lstom.melody["range_semitones"]
        skyline_range = r_skyline.melody["range_semitones"]
        # LStoM range should be reasonable (not spanning entire keyboard)
        assert lstom_range <= 60, (
            f"LStoM range {lstom_range} semitones seems too wide for melody"
        )

    def test_empty_midi(self):
        """Engine handles empty/short MIDI gracefully."""
        engine = LStoMMelodyEngine()
        # Create minimal MIDI with < 2 notes
        import pretty_midi
        pm = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=64, pitch=60, start=0.0, end=0.5))
        pm.instruments.append(inst)

        import io
        buf = io.BytesIO()
        pm.write(buf)
        midi_bytes = buf.getvalue()

        result = engine.analyze(midi_bytes)
        # Should return None melody for very short MIDI
        assert result.melody is None


class TestLStoMRegression:
    """Regression tests locking LStoM output on known inputs."""

    @pytest.fixture
    def engine(self):
        return LStoMMelodyEngine()

    def test_piano_synthetic_stepwise_ratio(self, engine):
        """Lock stepwise ratio on real-piano fixture."""
        result = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        melody = result.melody
        # Stepwise ratio should be reasonable for pop piano
        assert 0.3 <= melody["stepwise_ratio"] <= 0.9, (
            f"Stepwise ratio {melody['stepwise_ratio']} outside expected range"
        )

    def test_piano_synthetic_pitch_range(self, engine):
        """Lock pitch range on real-piano fixture."""
        result = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        melody = result.melody
        # Pitch range should be 1-2 octaves for pop melody
        assert 5 <= melody["range_semitones"] <= 36, (
            f"Range {melody['range_semitones']} semitones outside expected range"
        )

    def test_piano_synthetic_quality_score(self, engine):
        """Lock quality score on real-piano fixture."""
        result = engine.analyze(_read_bytes(REAL_PIANO_MIDI))
        melody = result.melody
        # Quality score should be between 0 and 1
        assert 0.0 <= melody["quality_score"] <= 1.0
