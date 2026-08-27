import numpy as np
import pytest

from evaluation.structure_librosa import chroma_novelty, pick_boundary_frames, propose_boundaries


def test_chroma_novelty_peaks_at_a_clear_feature_transition():
    chroma = np.zeros((12, 40))
    chroma[0, :20] = 1
    chroma[7, 20:] = 1

    novelty = chroma_novelty(chroma, comparison_frames=3)

    assert novelty.argmax() in range(17, 23)
    assert novelty[0] == 0
    assert novelty[-1] == 0


def test_peak_picker_is_deterministic_and_respects_separation():
    novelty = np.zeros(100)
    novelty[[20, 24, 70]] = [0.8, 1.0, 0.9]

    peaks = pick_boundary_frames(
        novelty, hop_length=100, sample_rate=100, min_separation_seconds=10, prominence=0.2
    )

    assert peaks.tolist() == [24, 70]


def test_short_audio_has_no_spurious_boundary():
    audio = np.zeros(512)

    result = propose_boundaries(audio, 22_050)

    assert result.proposals == ()
    assert result.duration_seconds > 0


def test_invalid_chroma_shape_is_rejected():
    with pytest.raises(ValueError, match="shape"):
        chroma_novelty(np.zeros(10))
