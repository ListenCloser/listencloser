"""Source separation metrics using mir_eval."""

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


def compute_sdr(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> float | None:
    """Compute Signal-to-Distortion Ratio."""
    try:
        from mir_eval.separation import bss_eval_sources

        if estimated.ndim == 1:
            estimated = estimated.reshape(1, -1)
        if reference.ndim == 1:
            reference = reference.reshape(1, -1)

        min_len = min(estimated.shape[-1], reference.shape[-1])
        estimated = estimated[..., :min_len]
        reference = reference[..., :min_len]

        sdr, sir, sar, _ = bss_eval_sources(reference, estimated)
        return float(np.mean(sdr))
    except Exception:
        return None


def compute_sir(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> float | None:
    """Compute Signal-to-Interference Ratio."""
    try:
        from mir_eval.separation import bss_eval_sources

        if estimated.ndim == 1:
            estimated = estimated.reshape(1, -1)
        if reference.ndim == 1:
            reference = reference.reshape(1, -1)

        min_len = min(estimated.shape[-1], reference.shape[-1])
        estimated = estimated[..., :min_len]
        reference = reference[..., :min_len]

        sdr, sir, sar, _ = bss_eval_sources(reference, estimated)
        return float(np.mean(sir))
    except Exception:
        return None


def compute_sar(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> float | None:
    """Compute Signal-to-Artifact Ratio."""
    try:
        from mir_eval.separation import bss_eval_sources

        if estimated.ndim == 1:
            estimated = estimated.reshape(1, -1)
        if reference.ndim == 1:
            reference = reference.reshape(1, -1)

        min_len = min(estimated.shape[-1], reference.shape[-1])
        estimated = estimated[..., :min_len]
        reference = reference[..., :min_len]

        sdr, sir, sar, _ = bss_eval_sources(reference, estimated)
        return float(np.mean(sar))
    except Exception:
        return None


def compute_separation_metrics(
    estimated: np.ndarray,
    reference: np.ndarray,
) -> SeparationMetrics:
    """Compute all separation metrics."""
    sdr = compute_sdr(estimated, reference)
    sir = compute_sir(estimated, reference)
    sar = compute_sar(estimated, reference)

    return SeparationMetrics(
        sdr=sdr,
        sir=sir,
        sar=sar,
        stoi=None,
    )
