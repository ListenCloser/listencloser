"""Tests for transcription engine selection via job parameters."""

from __future__ import annotations


class TestTranscriptionEngineSelection:
    def test_default_is_basic_pitch(self):
        from engines.registry import get_transcription_engine
        from engines.transcription.basic_pitch import BasicPitchEngine

        engine = get_transcription_engine()
        assert isinstance(engine, BasicPitchEngine)

    def test_threshold_propagation(self):
        from engines.registry import get_transcription_engine
        from engines.transcription.basic_pitch import BasicPitchEngine

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
        from engines.transcription.basic_pitch import BasicPitchEngine
        from music_features import get_transcription_engine_for_job

        engine = get_transcription_engine_for_job(
            name="basic_pitch", onset_threshold=0.6, frame_threshold=0.25,
        )
        assert isinstance(engine, BasicPitchEngine)

    def test_env_var_selection(self, monkeypatch):
        monkeypatch.setenv("TRANSCRIPTION_ENGINE", "basic_pitch")
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine()
        assert engine.ENGINE == "basic_pitch"
