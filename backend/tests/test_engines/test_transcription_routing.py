"""Tests for transcription engine selection via job parameters."""

from __future__ import annotations

from engines.base import EngineProvenance, TranscriptionResult
from engines.transcription.basic_pitch import BasicPitchEngine


class TestTranscriptionEngineSelection:
    def test_default_is_basic_pitch(self):
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine()
        assert isinstance(engine, BasicPitchEngine)

    def test_threshold_propagation(self):
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine(onset_threshold=0.7, frame_threshold=0.15)
        assert isinstance(engine, BasicPitchEngine)
        assert engine._onset_threshold == 0.7
        assert engine._frame_threshold == 0.15

    def test_unknown_engine_raises(self):
        import pytest

        from engines.registry import get_transcription_engine

        with pytest.raises(ValueError, match="Unknown transcription engine"):
            get_transcription_engine("nonexistent")

    def test_get_transcription_engine_for_job(self):
        from music_features import get_transcription_engine_for_job

        engine = get_transcription_engine_for_job(
            name="basic_pitch",
            onset_threshold=0.6,
            frame_threshold=0.25,
        )
        assert isinstance(engine, BasicPitchEngine)

    def test_env_var_selection(self, monkeypatch):
        monkeypatch.setenv("TRANSCRIPTION_ENGINE", "basic_pitch")
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine()
        assert engine.ENGINE == "basic_pitch"

    def test_profile_solo_piano_routes_to_transkun(self):
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine(profile="solo_piano")
        assert engine.ENGINE == "transkun"

    def test_profile_general_routes_to_basic_pitch(self):
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine(profile="general")
        assert engine.ENGINE == "basic_pitch"

    def test_profile_auto_routes_to_basic_pitch(self):
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine(profile="auto")
        assert engine.ENGINE == "basic_pitch"

    def test_explicit_name_overrides_profile(self):
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine(name="basic_pitch", profile="solo_piano")
        assert engine.ENGINE == "basic_pitch"

    def test_unknown_profile_raises(self):
        import pytest

        from engines.registry import get_transcription_engine

        with pytest.raises(ValueError, match="Unknown transcription profile"):
            get_transcription_engine(profile="nonexistent")


class TestProductionHandler:
    def test_transcription_result_has_expected_attributes(self):
        """TranscriptionResult exposes midi/wav/notes/num_notes/cleanup_report/provenance."""
        result = TranscriptionResult(
            midi=b"fake-midi",
            wav=b"fake-wav",
            notes=[{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}],
            num_notes=1,
            cleanup_report={"kept_notes": 1},
            provenance=EngineProvenance(engine="basic_pitch", library_version="0.4"),
        )
        assert result.midi == b"fake-midi"
        assert result.wav == b"fake-wav"
        assert len(result.notes) == 1
        assert result.num_notes == 1
        assert result.cleanup_report["kept_notes"] == 1
        assert result.provenance.engine == "basic_pitch"

    def test_engine_result_to_dict(self):
        result = TranscriptionResult(
            midi=b"m",
            wav=b"w",
            notes=[],
            num_notes=0,
            cleanup_report={},
            provenance=EngineProvenance(engine="test", library_version="1.0"),
        )
        d = result.to_dict()
        assert d["provenance"]["engine"] == "test"
        assert d["num_notes"] == 0
