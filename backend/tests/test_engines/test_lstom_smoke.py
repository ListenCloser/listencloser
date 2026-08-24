"""Production smoke test for LStoM melody engine.

This test MUST pass in any environment where the model is deployed.
Unlike the regression tests, this test will FAIL (not skip) if the
model cannot load, has wrong metadata, or produces invalid output.

Run: pytest tests/test_engines/test_lstom_smoke.py -v
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pretty_midi

from engines.melody.lstom_engine import _THRESHOLD, LStoMMelodyEngine

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
# pop_ensemble.mid is a synthetic pop-like MIDI (melody + accompaniment, 150 notes)
# that the LStoM model can process. simple_melody.mid doesn't trigger the model.
SMOKE_TEST_MIDI = FIXTURE_DIR / "music_eval" / "pop_ensemble.mid"
EMPTY_MIDI = FIXTURE_DIR / "music_eval" / "simple_melody.mid"

# Paths as strings (as used by lstom_engine)
_MODEL_DIR = str(Path(__file__).resolve().parent.parent.parent / "engines" / "melody")
_MODEL_PATH = f"{_MODEL_DIR}/lstom_model.pt"
_METADATA_PATH = f"{_MODEL_DIR}/lstom_model_metadata.json"


class TestLStoMProductionSmoke:
    """MUST-pass production smoke tests.

    These tests verify the model is loadable, has correct metadata,
    and produces valid output. If any of these fail in CI, the
    deployment is broken.
    """

    def test_model_file_exists(self):
        """Model weights file must exist."""
        assert Path(_MODEL_PATH).exists(), f"Model weights not found: {_MODEL_PATH}"

    def test_model_file_size(self):
        """Model file must be reasonable size (not truncated)."""
        size_mb = Path(_MODEL_PATH).stat().st_size / (1024 * 1024)
        assert 8.0 < size_mb < 12.0, (
            f"Model file size {size_mb:.1f}MB outside expected range (8-12MB)"
        )

    def test_metadata_file_exists(self):
        """Model metadata file must exist."""
        assert Path(_METADATA_PATH).exists(), f"Metadata not found: {_METADATA_PATH}"

    def test_metadata_valid_json(self):
        """Metadata must be valid JSON with required fields."""
        with open(_METADATA_PATH) as f:
            meta = json.load(f)
        assert "model_version" in meta
        assert "model_name" in meta
        assert "sha256" in meta
        assert "architecture" in meta
        assert "feature_schema" in meta
        assert "runtime" in meta
        assert "benchmark" in meta

    def test_metadata_matches_weights(self):
        """Metadata checksum must match actual model weights."""
        with open(_METADATA_PATH) as f:
            meta = json.load(f)
        actual_sha = hashlib.sha256(Path(_MODEL_PATH).read_bytes()).hexdigest()
        expected_sha = meta["sha256"]
        assert actual_sha == expected_sha, (
            f"Model checksum mismatch: expected {expected_sha[:16]}..., "
            f"got {actual_sha[:16]}..."
        )

    def test_engine_loads(self):
        """Engine must load successfully."""
        engine = LStoMMelodyEngine()
        assert engine is not None

    def test_provenance_fields(self):
        """Engine provenance must have all required fields."""
        engine = LStoMMelodyEngine()
        prov = engine.provenance
        assert prov.engine == "lstom"
        assert prov.model == "lstom_biLSTM_pop909"
        assert prov.library_version == "1.0.0"
        assert prov.parameters["training_dataset"] == "POP909"
        assert prov.parameters["threshold"] == _THRESHOLD

    def test_produces_valid_melody(self):
        """Engine must produce valid melody output on test fixture."""
        engine = LStoMMelodyEngine()
        midi_bytes = SMOKE_TEST_MIDI.read_bytes()
        result = engine.analyze(midi_bytes)

        assert result.melody is not None, "LStoM returned no melody"
        m = result.melody

        # All required fields present
        for field in [
            "low_pitch",
            "high_pitch",
            "range_semitones",
            "unique_pitch_classes",
            "stepwise_ratio",
            "leap_ratio",
            "quality_score",
            "heuristic",
        ]:
            assert field in m, f"Missing field: {field}"

        # Value ranges
        assert 0 <= m["low_pitch"] <= 127
        assert 0 <= m["high_pitch"] <= 127
        assert m["low_pitch"] <= m["high_pitch"]
        assert m["range_semitones"] == m["high_pitch"] - m["low_pitch"]
        assert 0 <= m["stepwise_ratio"] <= 1.0
        assert 0 <= m["leap_ratio"] <= 1.0
        assert 0 <= m["quality_score"] <= 1.0
        assert m["heuristic"] == "lstom_biLSTM"

    def test_no_bass_contamination(self):
        """Melody must stay in treble range (no bass pickup)."""
        engine = LStoMMelodyEngine()
        midi_bytes = SMOKE_TEST_MIDI.read_bytes()
        result = engine.analyze(midi_bytes)
        assert result.melody["low_pitch"] >= 48, (
            f"Low pitch {result.melody['low_pitch']} suggests bass contamination"
        )

    def test_deterministic_output(self):
        """Same input must produce identical output."""
        engine = LStoMMelodyEngine()
        midi_bytes = SMOKE_TEST_MIDI.read_bytes()
        r1 = engine.analyze(midi_bytes)
        r2 = engine.analyze(midi_bytes)

        assert r1.melody["low_pitch"] == r2.melody["low_pitch"]
        assert r1.melody["high_pitch"] == r2.melody["high_pitch"]
        assert r1.melody["stepwise_ratio"] == r2.melody["stepwise_ratio"]
        assert r1.melody["quality_score"] == r2.melody["quality_score"]

    def test_handles_empty_midi(self):
        """Engine handles empty/short MIDI gracefully."""
        engine = LStoMMelodyEngine()
        pm = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(
            pretty_midi.Note(velocity=64, pitch=60, start=0.0, end=0.5)
        )
        pm.instruments.append(inst)
        buf = io.BytesIO()
        pm.write(buf)

        result = engine.analyze(buf.getvalue())
        assert result.melody is None

    def test_handles_corrupt_midi(self):
        """Engine handles corrupt MIDI gracefully."""
        engine = LStoMMelodyEngine()
        result = engine.analyze(b"not valid midi data")
        assert result.melody is None

    def test_output_is_canonical_melody_result(self):
        """Output must be a MelodyResult with no extra tensors."""
        engine = LStoMMelodyEngine()
        midi_bytes = SMOKE_TEST_MIDI.read_bytes()
        result = engine.analyze(midi_bytes)

        # Must be MelodyResult type
        from engines.base import MelodyResult

        assert isinstance(result, MelodyResult)

        # No torch tensors leaking
        import torch

        for key, val in result.melody.items():
            assert not isinstance(val, torch.Tensor), (
                f"Field '{key}' is a torch.Tensor — must be JSON-serializable"
            )
