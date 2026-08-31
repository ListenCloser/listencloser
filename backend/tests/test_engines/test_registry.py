"""Tests for engine registry selection."""

from __future__ import annotations

import pytest

from engines.beats.beat_this_engine import BeatThisEngine
from engines.beats.librosa_engine import LibrosaBeatEngine
from engines.harmony.music21_engine import Music21HarmonyEngine
from engines.melody.lstom_engine import LStoMMelodyEngine
from engines.melody.skyline_engine import SkylineMelodyEngine
from engines.notation.musescore_engine import MuseScoreNotationEngine
from engines.registry import (
    get_beat_engine,
    get_harmony_engine,
    get_melody_engine,
    get_notation_engine,
    get_structure_engine,
    get_transcription_engine,
)
from engines.structure.allin1_engine import AllInOneEngine
from engines.transcription.basic_pitch import BasicPitchEngine


class TestRegistryDefaults:
    def test_default_transcription_is_basic_pitch(self):
        engine = get_transcription_engine()
        assert isinstance(engine, BasicPitchEngine)

    def test_default_beat_is_beat_this(self, monkeypatch):
        monkeypatch.delenv("BEAT_ENGINE", raising=False)
        engine = get_beat_engine()
        assert isinstance(engine, BeatThisEngine)

    def test_explicit_librosa_rollback(self):
        engine = get_beat_engine(name="librosa")
        assert isinstance(engine, LibrosaBeatEngine)

    def test_default_structure_is_allin1(self):
        engine = get_structure_engine()
        assert isinstance(engine, AllInOneEngine)

    def test_default_notation_is_musescore(self, monkeypatch):
        monkeypatch.delenv("NOTATION_ENGINE", raising=False)
        engine = get_notation_engine()
        assert isinstance(engine, MuseScoreNotationEngine)

    def test_default_harmony_is_music21(self):
        engine = get_harmony_engine()
        assert isinstance(engine, Music21HarmonyEngine)

    def test_default_melody_is_lstom(self):
        engine = get_melody_engine()
        assert isinstance(engine, LStoMMelodyEngine)


class TestRegistryExplicitSelection:
    def test_select_basic_pitch_explicitly(self):
        engine = get_transcription_engine("basic_pitch")
        assert isinstance(engine, BasicPitchEngine)

    def test_select_librosa_explicitly(self):
        engine = get_beat_engine("librosa")
        assert isinstance(engine, LibrosaBeatEngine)

    def test_select_beat_this_explicitly(self):
        engine = get_beat_engine("beat_this")
        assert isinstance(engine, BeatThisEngine)

    def test_music21_notation_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown notation engine"):
            get_notation_engine("music21")

    def test_unknown_engine_raises(self):
        with pytest.raises(ValueError, match="Unknown transcription engine"):
            get_transcription_engine("nonexistent")
        with pytest.raises(ValueError, match="Unknown beat engine"):
            get_beat_engine("made_up")
        with pytest.raises(ValueError, match="Unknown notation engine"):
            get_notation_engine("made_up")
        with pytest.raises(ValueError, match="Unknown harmony engine"):
            get_harmony_engine("made_up")
        with pytest.raises(ValueError, match="Unknown melody engine"):
            get_melody_engine("made_up")

    def test_select_harmony_explicitly(self):
        engine = get_harmony_engine("music21")
        assert isinstance(engine, Music21HarmonyEngine)

    def test_select_melody_explicitly(self):
        engine = get_melody_engine("skyline")
        assert isinstance(engine, SkylineMelodyEngine)

    def test_env_var_selection(self, monkeypatch):
        monkeypatch.setenv("TRANSCRIPTION_ENGINE", "basic_pitch")
        engine = get_transcription_engine()
        assert isinstance(engine, BasicPitchEngine)


class TestProvenance:
    def test_basic_pitch_provenance(self):
        engine = BasicPitchEngine(onset_threshold=0.5, frame_threshold=0.3)
        p = engine.provenance
        assert p.engine == "basic_pitch"
        assert p.parameters["onset_threshold"] == 0.5
        assert p.parameters["frame_threshold"] == 0.3

    def test_librosa_provenance(self):
        engine = LibrosaBeatEngine()
        p = engine.provenance
        assert p.engine == "librosa"
        # library_version may be "unknown" if librosa not installed locally

    def test_musescore_provenance(self):
        engine = MuseScoreNotationEngine(executable="/test/musescore")
        engine._version = "MuseScore Studio 4 test"
        p = engine.provenance
        assert p.engine == "musescore"
        assert p.library_version == "MuseScore Studio 4 test"

    def test_provenance_to_dict(self):
        engine = BasicPitchEngine()
        d = engine.provenance.to_dict()
        assert isinstance(d, dict)
        assert "engine" in d
        assert "library_version" in d
        assert "parameters" in d
