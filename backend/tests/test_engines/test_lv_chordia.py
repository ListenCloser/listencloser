"""Tests for the lv-chordia production harmony engine."""

from __future__ import annotations

import os
import tempfile
import wave

import pytest


def _make_silence_wav(duration_sec: float = 1.0, sr: int = 22050) -> bytes:
    """Create a silent WAV file in memory."""
    n_samples = int(sr * duration_sec)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        with wave.open(f.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(b"\x00\x00" * n_samples)
        with open(f.name, "rb") as rf:
            data = rf.read()
        os.unlink(f.name)
    return data


def _make_sine_wav(freq: float = 440.0, duration_sec: float = 2.0, sr: int = 22050) -> bytes:
    """Create a WAV file with a sine wave."""
    import math

    n_samples = int(sr * duration_sec)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        with wave.open(f.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            for i in range(n_samples):
                sample = int(32767 * math.sin(2 * math.pi * freq * i / sr))
                wf.writeframes(sample.to_bytes(2, "little", signed=True))
        with open(f.name, "rb") as rf:
            data = rf.read()
        os.unlink(f.name)
    return data


class TestLvChordiaEngine:
    """Tests for LvChordiaHarmonyEngine."""

    def test_import(self):
        """Engine can be imported."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        assert engine is not None

    @pytest.mark.integration
    def test_provenance(self):
        """Engine reports correct provenance."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        p = engine.provenance
        assert p.engine == "lv-chordia"
        assert "1.1.0" in p.library_version
        assert p.model == "ensemble_5models_hmm"

    def test_component_provenance(self):
        """Engine reports component provenance for chords only."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        cp = engine.component_provenance()
        assert "chords" in cp
        assert cp["chords"].engine == "lv-chordia"

    def test_analyze_requires_audio(self):
        """Engine raises RuntimeError when no audio provided."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        with pytest.raises(RuntimeError, match="requires audio"):
            engine.analyze(midi_bytes=b"")

    @pytest.mark.integration
    def test_analyze_silence(self):
        """Engine produces chord output from silence."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        audio = _make_silence_wav(2.0)
        result = engine.analyze(midi_bytes=b"", audio_bytes=audio)
        assert result.chords is not None
        assert isinstance(result.chords, list)

    @pytest.mark.integration
    def test_analyze_sine(self):
        """Engine produces chord output from a sine wave."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        audio = _make_sine_wav(440.0, 2.0)
        result = engine.analyze(midi_bytes=b"", audio_bytes=audio)
        assert result.chords is not None
        assert isinstance(result.chords, list)

    @pytest.mark.integration
    def test_chord_format(self):
        """Chord output has the expected format."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        audio = _make_silence_wav(2.0)
        result = engine.analyze(midi_bytes=b"", audio_bytes=audio)
        for ch in result.chords:
            assert "root" in ch
            assert "quality" in ch
            assert "start" in ch
            assert "end" in ch
            assert isinstance(ch["start"], float)
            assert isinstance(ch["end"], float)
            assert ch["end"] > ch["start"]

    def test_n_chord_represents_no_harmony(self):
        """N chord label represents no harmony, not a fake chord."""
        from engines.harmony.lv_chordia_engine import _parse_chord_label

        root, quality = _parse_chord_label("N")
        assert root == "N"
        assert quality == "N"

    def test_parse_chord_label(self):
        """Chord label parsing handles standard JAMS format."""
        from engines.harmony.lv_chordia_engine import _parse_chord_label

        assert _parse_chord_label("C:maj") == ("C", "maj")
        assert _parse_chord_label("F:min7") == ("F", "min7")
        assert _parse_chord_label("G:7") == ("G", "7")
        assert _parse_chord_label("N") == ("N", "N")

    @pytest.mark.integration
    def test_empty_result_fields(self):
        """Non-chord fields are empty (not fabricated)."""
        from engines.harmony.lv_chordia_engine import LvChordiaHarmonyEngine

        engine = LvChordiaHarmonyEngine()
        audio = _make_silence_wav(2.0)
        result = engine.analyze(midi_bytes=b"", audio_bytes=audio)
        assert result.key is None
        assert result.roman_numerals == []
        assert result.cadences == []
        assert result.voice_leading is None
        assert result.phrases == []


class TestMergeAdjacentChords:
    """Tests for _merge_adjacent_identical_chords."""

    def test_empty_list(self):
        """Empty input returns empty output."""
        from domain.capabilities import _merge_adjacent_identical_chords

        assert _merge_adjacent_identical_chords([]) == []

    def test_single_chord(self):
        """Single chord is returned unchanged."""
        from domain.capabilities import _merge_adjacent_identical_chords

        chords = [{"root": "C", "quality": "maj", "start": 0.0, "end": 2.0}]
        result = _merge_adjacent_identical_chords(chords)
        assert len(result) == 1
        assert result[0]["root"] == "C"

    def test_merge_identical_adjacent(self):
        """Two identical adjacent chords are merged."""
        from domain.capabilities import _merge_adjacent_identical_chords

        chords = [
            {"root": "C", "quality": "maj", "start": 0.0, "end": 2.0},
            {"root": "C", "quality": "maj", "start": 2.0, "end": 4.0},
        ]
        result = _merge_adjacent_identical_chords(chords)
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 4.0

    def test_no_merge_different_root(self):
        """Different roots are not merged."""
        from domain.capabilities import _merge_adjacent_identical_chords

        chords = [
            {"root": "C", "quality": "maj", "start": 0.0, "end": 2.0},
            {"root": "G", "quality": "maj", "start": 2.0, "end": 4.0},
        ]
        result = _merge_adjacent_identical_chords(chords)
        assert len(result) == 2

    def test_no_merge_different_quality(self):
        """Different qualities are not merged."""
        from domain.capabilities import _merge_adjacent_identical_chords

        chords = [
            {"root": "C", "quality": "maj", "start": 0.0, "end": 2.0},
            {"root": "C", "quality": "min", "start": 2.0, "end": 4.0},
        ]
        result = _merge_adjacent_identical_chords(chords)
        assert len(result) == 2

    def test_no_merge_noncontiguous(self):
        """Non-contiguous chords are not merged."""
        from domain.capabilities import _merge_adjacent_identical_chords

        chords = [
            {"root": "C", "quality": "maj", "start": 0.0, "end": 2.0},
            {"root": "C", "quality": "maj", "start": 3.0, "end": 5.0},
        ]
        result = _merge_adjacent_identical_chords(chords)
        assert len(result) == 2


class TestRegistryIntegration:
    """Tests for registry integration."""

    def test_lv_chordia_in_registry(self):
        """lv-chordia can be retrieved from the registry."""
        from engines.registry import get_harmony_engine

        engine = get_harmony_engine("lv_chordia")
        assert engine is not None
        assert hasattr(engine, "analyze")

    def test_music21_still_in_registry(self):
        """music21 remains available in the registry."""
        from engines.registry import get_harmony_engine

        engine = get_harmony_engine("music21")
        assert engine is not None
        assert hasattr(engine, "analyze")

    def test_unknown_engine_raises(self):
        """Unknown engine names raise ValueError."""
        from engines.registry import get_harmony_engine

        with pytest.raises(ValueError, match="Unknown harmony engine"):
            get_harmony_engine("nonexistent")
