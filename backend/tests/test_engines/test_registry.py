"""Tests for engine registry selection."""

from __future__ import annotations

import pytest

from engines.beats.librosa_engine import LibrosaBeatEngine
from engines.harmony.music21_engine import Music21HarmonyEngine
from engines.melody.skyline_engine import SkylineMelodyEngine
from engines.notation.musescore_engine import MuseScoreNotationEngine
from engines.registry import (
    get_beat_engine,
    get_harmony_engine,
    get_melody_engine,
    get_notation_engine,
    get_transcription_engine,
)


class TestRegistryDefaults:
    @pytest.mark.integration
    @pytest.mark.worker
    def test_default_transcription_is_basic_pitch(self):
        from engines.transcription.basic_pitch import BasicPitchEngine
        assert isinstance(get_transcription_engine(), BasicPitchEngine)

    @pytest.mark.integration
    @pytest.mark.worker
    def test_default_beat_is_beat_this(self, monkeypatch):
        from engines.beats.beat_this_engine import BeatThisEngine
        monkeypatch.delenv("BEAT_ENGINE", raising=False)
        assert isinstance(get_beat_engine(), BeatThisEngine)

    def test_explicit_librosa_rollback(self):
        assert isinstance(get_beat_engine(name="librosa"), LibrosaBeatEngine)

    def test_default_notation_is_musescore(self, monkeypatch):
        monkeypatch.delenv("NOTATION_ENGINE", raising=False)
        assert isinstance(get_notation_engine(), MuseScoreNotationEngine)

    def test_default_harmony_is_music21(self):
        assert isinstance(get_harmony_engine(), Music21HarmonyEngine)

    @pytest.mark.integration
    @pytest.mark.worker
    def test_default_melody_is_midibert(self, monkeypatch):
        from engines.melody.midibert_engine import MidiBERTMelodyEngine
        monkeypatch.delenv("MELODY_ENGINE", raising=False)
        assert isinstance(get_melody_engine(), MidiBERTMelodyEngine)


class TestRegistryExplicitSelection:
    @pytest.mark.integration
    @pytest.mark.worker
    def test_select_basic_pitch_explicitly(self):
        from engines.transcription.basic_pitch import BasicPitchEngine
        assert isinstance(get_transcription_engine("basic_pitch"), BasicPitchEngine)

    def test_select_librosa_explicitly(self):
        assert isinstance(get_beat_engine("librosa"), LibrosaBeatEngine)

    @pytest.mark.integration
    @pytest.mark.worker
    def test_select_beat_this_explicitly(self):
        from engines.beats.beat_this_engine import BeatThisEngine
        assert isinstance(get_beat_engine("beat_this"), BeatThisEngine)

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
        assert isinstance(get_harmony_engine("music21"), Music21HarmonyEngine)

    def test_select_melody_explicitly(self):
        assert isinstance(get_melody_engine("skyline"), SkylineMelodyEngine)

    @pytest.mark.integration
    @pytest.mark.worker
    def test_env_var_selection(self, monkeypatch):
        from engines.transcription.basic_pitch import BasicPitchEngine
        monkeypatch.setenv("TRANSCRIPTION_ENGINE", "basic_pitch")
        assert isinstance(get_transcription_engine(), BasicPitchEngine)


class TestProvenance:
    @pytest.mark.integration
    @pytest.mark.worker
    def test_basic_pitch_provenance(self):
        from engines.transcription.basic_pitch import BasicPitchEngine
        engine = BasicPitchEngine(onset_threshold=0.5, frame_threshold=0.3)
        p = engine.provenance
        assert p.engine == "basic_pitch"
        assert p.parameters["onset_threshold"] == 0.5
        assert p.parameters["frame_threshold"] == 0.3

    def test_librosa_provenance(self):
        assert LibrosaBeatEngine().provenance.engine == "librosa"

    def test_musescore_provenance(self):
        engine = MuseScoreNotationEngine(executable="/test/musescore")
        engine._version = "MuseScore Studio 4 test"
        assert engine.provenance.library_version == "MuseScore Studio 4 test"

    @pytest.mark.integration
    @pytest.mark.worker
    def test_provenance_to_dict(self):
        from engines.transcription.basic_pitch import BasicPitchEngine
        d = BasicPitchEngine().provenance.to_dict()
        assert isinstance(d, dict)
        assert "engine" in d
        assert "library_version" in d
        assert "parameters" in d
