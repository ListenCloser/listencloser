"""Tests for audio-native harmonic analysis and fusion.

Key/chord detection tests mock librosa so the tonic/mode rotation mapping is
verified deterministically. Fusion tests operate on constructed results.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from audio.fusion import fuse_chords, fuse_key
from audio.harmonic import AudioChordFrame, AudioKeyResult, detect_key

SR = 22050

_KS_MAJOR = np.array(
    [
        6.35,
        2.23,
        3.48,
        2.33,
        4.38,
        4.09,
        2.52,
        5.19,
        2.39,
        3.66,
        2.29,
        2.88,
    ]
)
_KS_MINOR = np.array(
    [
        6.33,
        2.68,
        3.52,
        5.38,
        2.60,
        3.53,
        2.54,
        4.75,
        3.98,
        2.69,
        3.34,
        3.17,
    ]
)
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _mock_librosa_for_key(chroma_mean: np.ndarray):
    """Return a patch context where librosa returns a fixed chroma."""
    m = MagicMock()
    m.effects.harmonic.return_value = np.zeros(1000, dtype=np.float32)
    chroma = np.tile(chroma_mean.reshape(-1, 1), (1, 10))
    m.feature.chroma_cqt.return_value = chroma
    m.__version__ = "mock"
    return patch.dict("sys.modules", {"librosa": m})


class TestAudioKeyDetection:
    def _detect_with_chroma(self, chroma_mean: np.ndarray) -> AudioKeyResult | None:
        with _mock_librosa_for_key(chroma_mean):
            return detect_key(np.zeros(1000, dtype=np.float32), SR)

    def test_c_major_rotation(self):
        chroma = _KS_MAJOR.copy()
        result = self._detect_with_chroma(chroma)
        assert result is not None
        assert result.tonic == "C"
        assert result.mode == "major"

    def test_g_major_rotation(self):
        # A G-major chroma is a C-major profile shifted so that G is the tonic.
        # Build by placing the major profile mass at G (pitch class 7).
        chroma = np.zeros(12)
        chroma[7] = _KS_MAJOR[0]  # tonic mass at G
        chroma[(7 + 4) % 12] = _KS_MAJOR[4]
        chroma[(7 + 7) % 12] = _KS_MAJOR[7]
        result = self._detect_with_chroma(chroma)
        assert result is not None
        assert result.tonic == "G"

    def test_a_minor_rotation(self):
        # A minor: tonic mass at A (pitch class 9), minor profile.
        chroma = np.zeros(12)
        for i, weight in enumerate(_KS_MINOR):
            chroma[(9 + i) % 12] = weight
        result = self._detect_with_chroma(chroma)
        assert result is not None
        assert result.tonic == "A"
        assert result.mode == "minor"

    def test_e_minor_rotation(self):
        # E minor: tonic mass at E (pitch class 4), minor profile.
        chroma = np.zeros(12)
        for i, weight in enumerate(_KS_MINOR):
            chroma[(4 + i) % 12] = weight
        result = self._detect_with_chroma(chroma)
        assert result is not None
        assert result.tonic == "E"
        assert result.mode == "minor"

    def test_uses_score_not_confidence(self):
        result = AudioKeyResult(
            tonic="C",
            mode="major",
            score=0.8,
            best_score=0.8,
            second_best_score=0.3,
        )
        d = result.to_dict()
        assert "score" in d
        assert "best_score" in d
        assert "confidence" not in d


class TestFusion:
    def test_consensus(self):
        ak = AudioKeyResult(
            tonic="C", mode="major", score=0.8, best_score=0.8, second_best_score=0.3
        )
        result = fuse_key(ak, "C major", 0.7)
        assert result.agreement == "consensus"
        assert result.tonic == "C"

    def test_conflict_no_single_tonic(self):
        ak = AudioKeyResult(
            tonic="D", mode="minor", score=0.7, best_score=0.7, second_best_score=0.2
        )
        result = fuse_key(ak, "F major", 0.6)
        assert result.agreement == "conflict"
        assert result.tonic is None

    def test_audio_only(self):
        ak = AudioKeyResult(
            tonic="A", mode="minor", score=0.5, best_score=0.5, second_best_score=0.1
        )
        result = fuse_key(ak, None, None)
        assert result.agreement == "audio_only"

    def test_symbolic_only(self):
        result = fuse_key(None, "G major", 0.6)
        assert result.agreement == "symbolic_only"

    def test_both_missing_returns_unavailable(self):
        result = fuse_key(None, None, None)
        assert result.agreement == "unavailable"
        assert result.tonic is None

    def test_chord_consensus_overlap(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "C", "quality": "maj", "start": 0.5}]
        result = fuse_chords(ac, sc)
        assert result.consensus_count == 1

    def test_chord_conflict_same_time(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "D", "quality": "min", "start": 0}]
        result = fuse_chords(ac, sc)
        assert result.conflict_count == 1

    def test_chord_no_overlap_no_consensus(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "C", "quality": "maj", "start": 50.0}]
        result = fuse_chords(ac, sc)
        assert result.consensus_count == 0

    def test_chord_quality_not_confused(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "C", "quality": "min", "start": 0}]
        result = fuse_chords(ac, sc)
        assert result.consensus_count == 0

    def test_chord_major_not_minor(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "C", "quality": "minor", "start": 0}]
        result = fuse_chords(ac, sc)
        assert result.consensus_count == 0

    def test_one_to_one_matching(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8), AudioChordFrame(1, 2, "G", "maj", 0.7)]
        sc = [
            {"root": "C", "quality": "maj", "start": 0},
            {"root": "C", "quality": "maj", "start": 1.1},
        ]
        result = fuse_chords(ac, sc)
        assert result.consensus_count == 1

    def test_chord_fusion_no_audio(self):
        sc = [{"root": "C", "quality": "maj", "start": 0}]
        result = fuse_chords(None, sc)
        assert result.symbolic_only_count == 1

    def test_chord_fusion_no_symbolic(self):
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        result = fuse_chords(ac, None)
        assert result.audio_only_count == 1

    def test_custom_onset_tolerance_changes_matching(self):
        """A tighter tolerance must reject matches a wider tolerance accepts."""
        ac = [AudioChordFrame(0, 1, "C", "maj", 0.8)]
        sc = [{"root": "C", "quality": "maj", "start": 1.5}]
        # With tolerance 2.0, onset diff 1.5 matches.
        wide = fuse_chords(ac, sc, onset_tolerance=2.0)
        assert wide.consensus_count == 1
        # With tolerance 0.5, onset diff 1.5 does not match.
        narrow = fuse_chords(ac, sc, onset_tolerance=0.5)
        assert narrow.consensus_count == 0
