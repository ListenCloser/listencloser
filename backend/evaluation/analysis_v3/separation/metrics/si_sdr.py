"""Canonical objective quality metric for the Analysis V3 separation bakeoff.

The decision quantity is SI-SDR improvement of a separated stem over the original
mixture against the exact same isolated reference. This module is evaluation-only
and intentionally does not alter production routing or runtime dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SeparationQualityDelta:
    mixture_si_sdr_db: float
    stem_si_sdr_db: float

    @property
    def improvement_db(self) -> float:
        return self.stem_si_sdr_db - self.mixture_si_sdr_db

    def to_dict(self) -> dict[str, float]:
        return {
            "mixture_si_sdr_db": round(self.mixture_si_sdr_db, 3),
            "stem_si_sdr_db": round(self.stem_si_sdr_db, 3),
            "improvement_db": round(self.improvement_db, 3),
        }


def _as_channel_first(audio: np.ndarray) -> np.ndarray:
    samples = np.asarray(audio, dtype=np.float64)
    if samples.ndim == 1:
        return samples.reshape(1, -1)
    if samples.ndim != 2:
        raise ValueError(f"Unsupported audio rank: {samples.ndim}")

    if samples.shape[0] <= 8 and samples.shape[0] < samples.shape[1]:
        return samples
    if samples.shape[1] <= 8 and samples.shape[1] < samples.shape[0]:
        return samples.T
    raise ValueError(f"Ambiguous audio channel layout: {samples.shape}")


def _fast_bss_eval_si_sdr(reference_channel: np.ndarray, estimated_channel: np.ndarray) -> float:
    try:
        import fast_bss_eval
    except ImportError as exc:  # pragma: no cover - benchmark environment guard
        raise RuntimeError(
            "fast-bss-eval==0.1.4 is required for the separation objective benchmark"
        ) from exc

    score = fast_bss_eval.si_sdr(
        reference_channel.reshape(1, -1),
        estimated_channel.reshape(1, -1),
        zero_mean=True,
        clamp_db=100.0,
    )
    return float(np.asarray(score).reshape(-1)[0])


def compute_si_sdr(
    estimated: np.ndarray,
    reference: np.ndarray,
    silence_epsilon: float = 1e-8,
) -> float | None:
    """Compute mean channel-wise scale-invariant SDR.

    Inputs may be mono, channel-first, or channel-last. Matching channel layouts
    are scored channel-by-channel and averaged. If channel counts differ, both
    signals are folded to mono first. Silent reference channels are withheld
    rather than producing a meaningless score.
    """
    estimated_channels = _as_channel_first(estimated)
    reference_channels = _as_channel_first(reference)
    sample_count = min(estimated_channels.shape[-1], reference_channels.shape[-1])
    if sample_count == 0:
        return None

    estimated_channels = estimated_channels[..., :sample_count]
    reference_channels = reference_channels[..., :sample_count]

    if estimated_channels.shape[0] != reference_channels.shape[0]:
        estimated_channels = estimated_channels.mean(axis=0, keepdims=True)
        reference_channels = reference_channels.mean(axis=0, keepdims=True)

    scores: list[float] = []
    for estimated_channel, reference_channel in zip(
        estimated_channels,
        reference_channels,
        strict=True,
    ):
        centered_reference = reference_channel - np.mean(reference_channel)
        reference_energy = float(np.dot(centered_reference, centered_reference))
        if reference_energy <= silence_epsilon:
            continue
        scores.append(_fast_bss_eval_si_sdr(reference_channel, estimated_channel))

    return float(np.mean(scores)) if scores else None


def compare_si_sdr_mixture_vs_stem(
    mixture: np.ndarray,
    estimated_stem: np.ndarray,
    reference_stem: np.ndarray,
) -> SeparationQualityDelta | None:
    """Measure SI-SDR gain from separation against one exact reference stem."""
    mixture_score = compute_si_sdr(mixture, reference_stem)
    stem_score = compute_si_sdr(estimated_stem, reference_stem)
    if mixture_score is None or stem_score is None:
        return None
    return SeparationQualityDelta(
        mixture_si_sdr_db=mixture_score,
        stem_si_sdr_db=stem_score,
    )
