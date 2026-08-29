"""Objective source-separation metrics.

Stage 2 uses ``fast-bss-eval`` for SI-SDR rather than a bespoke metric. The
headline objective comparison is gain over the original mixture against the same
isolated reference stem. Legacy ``mir_eval`` BSS Eval helpers remain available
for compatibility but are not the primary decision metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SeparationMetrics:
    sdr: float | None
    sir: float | None
    sar: float | None
    stoi: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sdr": round(self.sdr, 2) if self.sdr is not None else None,
            "sir": round(self.sir, 2) if self.sir is not None else None,
            "sar": round(self.sar, 2) if self.sar is not None else None,
            "stoi": round(self.stoi, 4) if self.stoi is not None else None,
        }


@dataclass(frozen=True)
class SeparationQualityDelta:
    """Objective gain from mixture audio to a separated stem."""

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
            "fast-bss-eval==0.1.4 is required for the Stage 2 separation benchmark"
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
    """Compute mean channel-wise SI-SDR with ``fast-bss-eval``.

    Inputs may be mono, channel-first, or channel-last. Stereo channels are
    scored independently and averaged; they are never treated as permutable
    sources. If channel counts differ, both signals are folded to mono first.
    Completely silent reference channels are withheld.
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
    """Measure how much separation improves SI-SDR against a reference stem."""
    mixture_score = compute_si_sdr(mixture, reference_stem)
    stem_score = compute_si_sdr(estimated_stem, reference_stem)
    if mixture_score is None or stem_score is None:
        return None
    return SeparationQualityDelta(
        mixture_si_sdr_db=mixture_score,
        stem_si_sdr_db=stem_score,
    )


def compute_sdr(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> float | None:
    """Compute legacy BSS Eval Signal-to-Distortion Ratio."""
    try:
        from mir_eval.separation import bss_eval_sources

        if estimated.ndim == 1:
            estimated = estimated.reshape(1, -1)
        if reference.ndim == 1:
            reference = reference.reshape(1, -1)

        min_len = min(estimated.shape[-1], reference.shape[-1])
        estimated = estimated[..., :min_len]
        reference = reference[..., :min_len]

        sdr, _, _, _ = bss_eval_sources(reference, estimated)
        return float(np.mean(sdr))
    except Exception:
        return None


def compute_sir(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> float | None:
    """Compute legacy BSS Eval Signal-to-Interference Ratio."""
    try:
        from mir_eval.separation import bss_eval_sources

        if estimated.ndim == 1:
            estimated = estimated.reshape(1, -1)
        if reference.ndim == 1:
            reference = reference.reshape(1, -1)

        min_len = min(estimated.shape[-1], reference.shape[-1])
        estimated = estimated[..., :min_len]
        reference = reference[..., :min_len]

        _, sir, _, _ = bss_eval_sources(reference, estimated)
        return float(np.mean(sir))
    except Exception:
        return None


def compute_sar(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> float | None:
    """Compute legacy BSS Eval Signal-to-Artifact Ratio."""
    try:
        from mir_eval.separation import bss_eval_sources

        if estimated.ndim == 1:
            estimated = estimated.reshape(1, -1)
        if reference.ndim == 1:
            reference = reference.reshape(1, -1)

        min_len = min(estimated.shape[-1], reference.shape[-1])
        estimated = estimated[..., :min_len]
        reference = reference[..., :min_len]

        _, _, sar, _ = bss_eval_sources(reference, estimated)
        return float(np.mean(sar))
    except Exception:
        return None


def compute_separation_metrics(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> SeparationMetrics:
    """Compute legacy separation metrics for compatibility."""
    return SeparationMetrics(
        sdr=compute_sdr(estimated, reference),
        sir=compute_sir(estimated, reference),
        sar=compute_sar(estimated, reference),
        stoi=None,
    )
