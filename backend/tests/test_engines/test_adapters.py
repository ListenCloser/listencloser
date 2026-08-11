"""Tests for engine adapters (mocked so no ML models run)."""

from __future__ import annotations

from engines.base import (
    BeatTrackingResult,
    EngineProvenance,
    NotationResult,
    TranscriptionResult,
)
from engines.beats.librosa_engine import LibrosaBeatEngine
from engines.notation.music21_engine import Music21NotationEngine
from engines.structure.allin1_engine import AllInOneEngine
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


class TestAllInOneAdapter:
    def test_disabled_by_default(self):
        engine = AllInOneEngine()
        result = engine.analyze(b"fake-wav")
        assert result is not None
        assert not result.enabled
        assert result.beats == []

    def test_provenance_includes_model(self):
        engine = AllInOneEngine()
        p = engine.provenance
        assert p.model == "harmonix-all"


class TestMusic21NotationAdapter:
    def test_provenance(self):
        engine = Music21NotationEngine()
        assert engine.provenance.engine == "music21"

    def test_result_has_provenance(self):
        result = NotationResult(
            notation_midi=b"midi",
            musicxml=b"xml",
            quantization_report={"notes": 10},
            provenance=EngineProvenance(engine="music21", library_version="9.1"),
        )
        d = result.to_dict()
        assert d["provenance"]["engine"] == "music21"
