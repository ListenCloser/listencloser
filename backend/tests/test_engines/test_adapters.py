"""Tests for engine adapters (mocked so no ML models run)."""

from __future__ import annotations

import os
from contextlib import suppress
from typing import Any

import pytest

from engines.base import (
    BeatTrackingResult,
    EngineProvenance,
    HarmonyResult,
    MelodyResult,
    TranscriptionResult,
)
from engines.beats.librosa_engine import LibrosaBeatEngine
from engines.harmony.music21_engine import Music21HarmonyEngine
from engines.melody.skyline_engine import SkylineMelodyEngine
from engines.transcription.basic_pitch import BasicPitchEngine


class TestBasicPitchAdapter:
    def test_transcribe_returns_result(self):
        engine = BasicPitchEngine()
        assert engine.provenance.engine == "basic_pitch"

    def test_provenance_includes_parameters(self):
        engine = BasicPitchEngine(onset_threshold=0.7, frame_threshold=0.4)
        p = engine.provenance
        assert p.parameters["onset_threshold"] == 0.7
        assert p.parameters["frame_threshold"] == 0.4

    def test_result_has_provenance(self):
        fake_notes = [{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 64}]
        result = TranscriptionResult(
            midi=b"fake-midi",
            wav=b"fake-wav",
            notes=fake_notes,
            num_notes=1,
            cleanup_report={"kept_notes": 1},
            provenance=EngineProvenance(
                engine="basic_pitch", library_version="0.4.0", parameters={"onset_threshold": 0.5}
            ),
        )
        assert result.num_notes == 1
        d = result.to_dict()
        assert d["provenance"]["engine"] == "basic_pitch"


class TestLibrosaBeatAdapter:
    def test_analyze_returns_result(self, monkeypatch):
        monkeypatch.setattr(
            "engines.beats.librosa_engine._librosa_version",
            lambda: "0.10.0",
        )
        engine = LibrosaBeatEngine()
        assert engine.provenance.library_version == "0.10.0"

    def test_result_structure(self):
        result = BeatTrackingResult(
            bpm=120.0,
            beats=[0.0, 0.5, 1.0],
            downbeats=[0.0],
            beat_positions=[0, 1, 2],
            provenance=EngineProvenance(engine="librosa", library_version="0.10"),
        )
        assert result.bpm == 120.0
        d = result.to_dict()
        assert d["beat_count"] == 3
        assert d["provenance"]["engine"] == "librosa"


class TestHarmonyResult:
    def test_to_dict_includes_provenance(self):
        result = HarmonyResult(
            key=None,
            chords=[],
            roman_numerals=[],
            cadences=[],
            voice_leading=None,
            phrases=[],
            provenance=EngineProvenance(engine="music21", library_version="10.5"),
            component_provenance={
                "key": EngineProvenance(engine="music21", library_version="10.5"),
                "cadences": EngineProvenance(engine="custom-rule", library_version="custom"),
            },
        )
        d = result.to_dict()
        assert d["key"] is None
        assert d["provenance"]["engine"] == "music21"
        assert d["component_provenance"]["cadences"]["engine"] == "custom-rule"


class TestMelodyResult:
    def test_to_dict_includes_provenance(self):
        result = MelodyResult(
            melody=None,
            provenance=EngineProvenance(
                engine="skyline",
                library_version="0.2.10",
                parameters={"heuristic": "greedy_continuity_skyline"},
            ),
        )
        d = result.to_dict()
        assert d["melody"] is None
        assert d["provenance"]["engine"] == "skyline"


class TestMusic21HarmonyAdapter:
    def test_provenance(self):
        pytest.importorskip("music21")
        engine = Music21HarmonyEngine()
        assert engine.provenance.engine == "music21"

    def test_analyze_returns_conservative_result(self, monkeypatch):
        """On parse failure the engine returns no-evidence results, not fabrications."""
        pytest.importorskip("music21")
        import music21.converter

        def boom(*_a, **_k):
            raise RuntimeError("boom")

        monkeypatch.setattr(music21.converter, "parse", boom)
        engine = Music21HarmonyEngine()
        result = engine.analyze(b"not-a-midi")
        assert result.key is None
        assert result.chords == []
        assert result.roman_numerals == []
        assert result.cadences == []
        assert result.voice_leading is None
        assert result.phrases == []
        assert result.provenance.engine == "music21"


class TestSkylineMelodyAdapter:
    def test_provenance(self):
        engine = SkylineMelodyEngine()
        assert engine.provenance.engine == "skyline"
        assert engine.provenance.parameters["heuristic"] == "greedy_continuity_skyline"

    def test_analyze_returns_none_melody_for_garbage(self):
        engine = SkylineMelodyEngine()
        result = engine.analyze(b"not-a-midi")
        assert result.melody is None
        assert result.provenance.engine == "skyline"


class TestTimingExcludesSetup:
    """Verify that measured inference runtime excludes prepare() and warm-up."""

    def test_runtime_excludes_prepare_and_warmup(self):
        """Prepare and warm-up sleep time must NOT be counted in inference runtime."""
        import tempfile
        import time

        class SlowAdapter:
            engine_info = type(
                "Info",
                (),
                {
                    "name": "slow_test",
                    "category": "transcription",
                    "repo_url": "",
                    "license": "",
                    "install_cmd": "",
                    "model_size_mb": 0,
                    "requires_gpu": False,
                    "notes": "",
                },
            )()

            def __init__(self):
                self._prepared = False
                self._warmed = False

            def is_available(self) -> bool:
                return True

            def prepare(self) -> None:
                time.sleep(0.1)
                self._prepared = True

            def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
                time.sleep(0.05)
                self._warmed = True
                return {"midi": b"", "notes": [], "num_notes": 0, "cleanup_report": {}}

            def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
                raise NotImplementedError

            def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
                raise NotImplementedError

            def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
                raise NotImplementedError

        from evaluation.engines import _run_clip_on_engine
        from evaluation.models import EvalClip

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(
                b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x40\x1f\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00"
            )
            temp_audio = f.name

        try:
            clip = EvalClip(id="test_clip", audio=temp_audio, category="solo_piano")
            adapter = SlowAdapter()
            result = _run_clip_on_engine(adapter, clip, "transcription", warmup=True)

            assert result.success
            assert result.runtime_s < 0.1
            assert result.runtime_s > 0.03
            assert result.peak_memory_mb >= 0
        finally:
            with suppress(Exception):
                os.unlink(temp_audio)

    def test_failed_prepare_returns_zero_runtime(self):
        """If prepare() fails, runtime should be 0 (not mislabel setup time as inference)."""
        import time

        class FailingPrepareAdapter:
            engine_info = type(
                "Info",
                (),
                {
                    "name": "fail_prepare",
                    "category": "transcription",
                    "repo_url": "",
                    "license": "",
                    "install_cmd": "",
                    "model_size_mb": 0,
                    "requires_gpu": False,
                    "notes": "",
                },
            )()

            def is_available(self) -> bool:
                return True

            def prepare(self) -> None:
                time.sleep(0.1)
                raise RuntimeError("Model load failed")

            def transcribe(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
                raise NotImplementedError("Should not be called")

            def estimate_beats(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
                raise NotImplementedError

            def analyze_harmony(self, midi_bytes: bytes, **kwargs) -> dict[str, Any]:
                raise NotImplementedError

            def analyze_structure(self, audio_bytes: bytes, **kwargs) -> dict[str, Any]:
                raise NotImplementedError

        from evaluation.engines import _run_clip_on_engine
        from evaluation.models import EvalClip

        clip = EvalClip(id="test_clip", audio=b"dummy", category="solo_piano")
        adapter = FailingPrepareAdapter()
        result = _run_clip_on_engine(adapter, clip, "transcription", warmup=True)

        assert not result.success
        assert "Model load failed" in result.error
        assert result.runtime_s == 0.0
        assert result.peak_memory_mb == 0.0
