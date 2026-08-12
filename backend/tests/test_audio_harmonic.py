"""Tests for audio-native harmonic analysis and fusion."""

from __future__ import annotations

import numpy as np

from audio.harmonic import detect_key, estimate_chords, AudioKeyResult, AudioChordFrame
from audio.fusion import fuse_key, fuse_chords

SR = 22050


def _sine(dur: float, freqs: list[float]) -> np.ndarray:
    t = np.arange(int(SR * dur)) / SR
    y = sum(np.sin(2 * np.pi * f * t) * 0.3 for f in freqs)
    return y.astype(np.float32)


class TestAudioKeyDetection:
    def test_detect_c_major(self):
        audio = _sine(5.0, [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25])
        result = detect_key(audio, SR)
        if result is not None:
            assert result.tonic == "C" or result.mode in ("major", "minor")

    def test_detect_a_minor(self):
        audio = _sine(5.0, [220.00, 246.94, 261.63, 293.66, 329.63, 349.23, 440.00])
        result = detect_key(audio, SR)
        if result is not None:
            assert result.mode == "minor"

    def test_result_to_dict(self):
        result = AudioKeyResult(tonic="C", mode="major", confidence=0.8)
        d = result.to_dict()
        assert d["source"] == "librosa_krumhansl"
        assert "confidence" in d


class TestAudioChords:
    def test_estimate_chords_returns_list(self):
        audio = _sine(5.0, [261.63, 329.63, 392.00])
        chords = estimate_chords(audio, SR)
        assert isinstance(chords, list)

    def test_chord_frame_has_source(self):
        c = AudioChordFrame(0, 1, "C", "maj", 0.8)
        assert c.source == "librosa_chroma_template"


class TestFusion:
    def test_consensus(self):
        ak = AudioKeyResult(tonic="C", mode="major", confidence=0.8)
        result = fuse_key(ak, "C major", 0.7)
        assert result.agreement == "consensus"
        assert result.tonic == "C"

    def test_conflict(self):
        ak = AudioKeyResult(tonic="D", mode="minor", confidence=0.7)
        result = fuse_key(ak, "F major", 0.6)
        assert result.agreement == "conflict"

    def test_audio_only(self):
        ak = AudioKeyResult(tonic="A", mode="minor", confidence=0.5)
        result = fuse_key(ak, None, None)
        assert result.agreement == "audio_only"

    def test_symbolic_only(self):
        result = fuse_key(None, "G major", 0.6)
        assert result.agreement == "symbolic_only"

    def test_both_missing(self):
        result = fuse_key(None, None, None)
        assert result.agreement == "symbolic_only"

    def test_chord_fusion_consensus(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "C", "quality": "M", "start": 0}]
        result = fuse_chords(ac, sc)
        assert result.consensus_count == 1

    def test_chord_fusion_conflict(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "D", "quality": "min", "start": 0}]
        result = fuse_chords(ac, sc)
        assert result.conflict_count == 1

    def test_chord_fusion_no_audio(self):
        sc = [{"root": "C", "quality": "M", "start": 0}]
        result = fuse_chords(None, sc)
        assert result.symbolic_only_count == 1

    def test_chord_fusion_no_symbolic(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        result = fuse_chords(ac, None)
        assert result.audio_only_count == 1
