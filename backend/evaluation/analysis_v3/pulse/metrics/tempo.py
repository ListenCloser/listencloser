"""Tempo evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class TempoResult:
    absolute_error: float | None
    relative_error_pct: float | None
    is_correct: bool | None
    is_octave_error: bool | None
    is_half_double_error: bool | None
    predicted_bpm: float | None
    reference_bpm: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "absolute_error": round(self.absolute_error, 2)
            if self.absolute_error is not None
            else None,
            "relative_error_pct": round(self.relative_error_pct, 2)
            if self.relative_error_pct is not None
            else None,
            "is_correct": self.is_correct,
            "is_octave_error": self.is_octave_error,
            "is_half_double_error": self.is_half_double_error,
            "predicted_bpm": round(self.predicted_bpm, 2)
            if self.predicted_bpm is not None
            else None,
            "reference_bpm": round(self.reference_bpm, 2)
            if self.reference_bpm is not None
            else None,
        }


def _validate_tolerance_pct(tolerance_pct: float) -> None:
    if tolerance_pct < 0:
        raise ValueError("Tempo tolerance must be non-negative")


def compute_tempo_error(
    predicted_bpm: float | None,
    reference_bpm: float | None,
    tolerance_pct: float = 4.0,
) -> TempoResult:
    """Compute tempo error metrics using a percentage tolerance."""
    _validate_tolerance_pct(tolerance_pct)

    if predicted_bpm is None or reference_bpm is None or reference_bpm <= 0:
        return TempoResult(
            absolute_error=None,
            relative_error_pct=None,
            is_correct=None,
            is_octave_error=None,
            is_half_double_error=None,
            predicted_bpm=predicted_bpm,
            reference_bpm=reference_bpm,
        )

    abs_error = abs(predicted_bpm - reference_bpm)
    rel_error = abs_error / reference_bpm * 100
    tolerance = tolerance_pct / 100.0

    is_correct = rel_error <= tolerance_pct
    is_octave = check_octave_errors(predicted_bpm, reference_bpm, tolerance)
    is_half_double = check_half_double_errors(predicted_bpm, reference_bpm, tolerance)

    return TempoResult(
        absolute_error=abs_error,
        relative_error_pct=rel_error,
        is_correct=is_correct,
        is_octave_error=is_octave,
        is_half_double_error=is_half_double,
        predicted_bpm=predicted_bpm,
        reference_bpm=reference_bpm,
    )


def compute_tempo_accuracy(
    results: list[TempoResult],
    tolerance_pct: float = 4.0,
) -> dict[str, Any]:
    """Compute aggregate strict and octave-aware tempo accuracy."""
    _validate_tolerance_pct(tolerance_pct)
    valid = [r for r in results if r.relative_error_pct is not None]
    if not valid:
        return {
            "accuracy": None,
            "octave_aware_accuracy": None,
            "count": 0,
            "correct": 0,
            "total": 0,
            "octave_errors": 0,
            "half_double_errors": 0,
            "mean_absolute_error": None,
            "mean_relative_error_pct": None,
        }

    tolerance = tolerance_pct / 100.0
    strict_correct = [
        r.relative_error_pct is not None and r.relative_error_pct <= tolerance_pct for r in valid
    ]
    octave_flags = [
        check_octave_errors(r.predicted_bpm, r.reference_bpm, tolerance)
        if r.predicted_bpm is not None and r.reference_bpm is not None
        else False
        for r in valid
    ]
    half_double_flags = [
        check_half_double_errors(r.predicted_bpm, r.reference_bpm, tolerance)
        if r.predicted_bpm is not None and r.reference_bpm is not None
        else False
        for r in valid
    ]

    correct = sum(strict_correct)
    octave_aware_correct = sum(
        is_correct or is_octave
        for is_correct, is_octave in zip(strict_correct, octave_flags, strict=True)
    )

    return {
        "accuracy": round(correct / len(valid), 4),
        "octave_aware_accuracy": round(octave_aware_correct / len(valid), 4),
        "count": len(valid),
        "correct": correct,
        "total": len(valid),
        "octave_errors": sum(octave_flags),
        "half_double_errors": sum(half_double_flags),
        "mean_absolute_error": round(
            np.mean([r.absolute_error for r in valid if r.absolute_error is not None]), 2
        ),
        "mean_relative_error_pct": round(
            np.mean([r.relative_error_pct for r in valid if r.relative_error_pct is not None]),
            2,
        ),
    }


def check_octave_errors(
    predicted_bpm: float,
    reference_bpm: float,
    tolerance: float = 0.04,
) -> bool:
    """Check if predicted tempo is an octave error (2x or 0.5x)."""
    if reference_bpm <= 0:
        return False
    for factor in (0.5, 2.0):
        target_bpm = reference_bpm * factor
        relative_error = abs(predicted_bpm - target_bpm) / target_bpm
        if relative_error <= tolerance:
            return True
    return False


def check_half_double_errors(
    predicted_bpm: float,
    reference_bpm: float,
    tolerance: float = 0.04,
) -> bool:
    """Check if predicted tempo is a half/double error."""
    return check_octave_errors(predicted_bpm, reference_bpm, tolerance)
