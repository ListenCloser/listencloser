"""Tests that engine-aware wrappers route through the registry.

All tests mock the production modules so they run without music deps.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

_MOCKED_MODULES = ["basic_pitch", "basic_pitch.inference", "soundfile", "librosa"]


@pytest.fixture(scope="module", autouse=True)
def _mock_music_modules():
    """Scope the music-module mocks to this module.

    Previously the mocks were installed at module import time and leaked into
    every other test file in the same process (replacing ``basic_pitch`` with a
    MagicMock globally), which broke the real-model integration tests. The real
    modules are restored after this module finishes.
    """
    saved = {name: sys.modules.get(name) for name in _MOCKED_MODULES}
    for name in _MOCKED_MODULES:
        sys.modules.pop(name, None)
        sys.modules[name] = MagicMock()
    yield
    for name in _MOCKED_MODULES:
        sys.modules.pop(name, None)
        if saved[name] is not None:
            sys.modules[name] = saved[name]


class TestTranscriptionWrapper:
    def test_wrapper_resolves_engine_via_registry(self):
        from engines.base import TranscriptionResult
        from engines.transcription.basic_pitch import BasicPitchEngine

        engine = BasicPitchEngine()
        fake_notes = [{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}]
        fake_result = TranscriptionResult(
            midi=b"midi",
            wav=b"wav",
            notes=fake_notes,
            num_notes=1,
            cleanup_report={"kept": 1},
            provenance=engine.provenance,
        )
        engine.transcribe = MagicMock(return_value=fake_result)

        with patch("engines.registry.get_transcription_engine", return_value=engine):
            import music_features as mf

            result = mf.transcribe_with_engine(b"audio", fmt="wav")
            assert result["num_notes"] == 1
            assert result["provenance"]["engine"] == "basic_pitch"

    def test_wrapper_passes_parameters(self):
        from engines.base import TranscriptionResult
        from engines.transcription.basic_pitch import BasicPitchEngine

        engine = BasicPitchEngine()
        engine.transcribe = MagicMock(
            return_value=TranscriptionResult(
                midi=b"x",
                wav=b"x",
                notes=[],
                num_notes=0,
                cleanup_report={},
                provenance=engine.provenance,
            )
        )

        with patch("engines.registry.get_transcription_engine", return_value=engine):
            import music_features as mf

            mf.transcribe_with_engine(b"a", onset_threshold=0.7, frame_threshold=0.4)
            assert engine.transcribe.called


class TestBeatWrapper:
    def test_wrapper_resolves_engine_via_registry(self):
        from engines.base import BeatTrackingResult
        from engines.beats.librosa_engine import LibrosaBeatEngine

        engine = LibrosaBeatEngine()
        engine.analyze = MagicMock(
            return_value=BeatTrackingResult(
                bpm=120.0,
                beats=[0.0, 0.5],
                downbeats=None,
                beat_positions=[0, 1],
                provenance=engine.provenance,
            )
        )

        with patch("engines.registry.get_beat_engine", return_value=engine):
            import music_features as mf

            result = mf.estimate_beats_with_engine(b"wav")
            assert result["bpm"] == 120.0
            assert result["downbeats"] is None
            assert result["provenance"]["engine"] == "librosa"


class TestNotationWrapper:
    def test_wrapper_resolves_engine_via_registry(self):
        from engines.base import NotationResult
        from engines.notation.music21_engine import Music21NotationEngine

        engine = Music21NotationEngine()
        engine.convert = MagicMock(
            return_value=NotationResult(
                notation_midi=b"midi",
                musicxml=b"xml",
                quantization_report={"notes": 5},
                provenance=engine.provenance,
            )
        )

        with patch("engines.registry.get_notation_engine", return_value=engine):
            import music_features as mf

            result = mf.notation_with_engine(b"midi", [0.0, 0.5])
            assert result["provenance"]["engine"] == "music21"
            assert result["musicxml"] == b"xml"


class TestEnvEngineSelection:
    def test_env_var_affects_engine_selection(self, monkeypatch):
        monkeypatch.setenv("TRANSCRIPTION_ENGINE", "basic_pitch")
        from engines.registry import get_transcription_engine

        engine = get_transcription_engine()
        assert engine.ENGINE == "basic_pitch"

    def test_unknown_engine_env_var_raises(self, monkeypatch):
        monkeypatch.setenv("BEAT_ENGINE", "made_up_nonexistent")
        from engines.registry import get_beat_engine

        with pytest.raises(ValueError, match="Unknown beat engine"):
            get_beat_engine()
