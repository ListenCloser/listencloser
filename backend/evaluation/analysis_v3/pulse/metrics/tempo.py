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


def compute_tempo_error(
    predicted_bpm: float | None,
    reference_bpm: float | None,
) -> TempoResult:
    """Compute tempo error metrics."""
    if predicted_bpm is None or reference_bpm is None:
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
    rel_error = abs_error / reference_bpm * 100 if reference_bpm > 0 else 0.0

    is_correct = rel_error <= 4.0

    is_octave = check_octave_errors(predicted_bpm, reference_bpm)
    is_half_double = check_half_double_errors(predicted_bpm, reference_bpm)

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
    """Compute aggregate tempo accuracy."""
    valid = [r for r in results if r.is_correct is not None]
    if not valid:
        return {"accuracy": None, "count": 0}

    correct = sum(1 for r in valid if r.is_correct)
    octave_errors = sum(1 for r in valid if r.is_octave_error)
    half_double_errors = sum(1 for r in valid if r.is_half_double_error)

    return {
        "accuracy": round(correct / len(valid), 4),
        "correct": correct,
        "total": len(valid),
        "octave_errors": octave_errors,
        "half_double_errors": half_double_errors,
        "mean_absolute_error": round(
            np.mean([r.absolute_error for r in valid if r.absolute_error is not None]), 2
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
    ratio = predicted_bpm / reference_bpm
    return abs(ratio - 2.0) <= tolerance or abs(ratio - 0.5) <= tolerance


def check_half_double_errors(
    predicted_bpm: float,
    reference_bpm: float,
    tolerance: float = 0.04,
) -> bool:
    """Check if predicted tempo is a half/double error."""
    return check_octave_errors(predicted_bpm, reference_bpm, tolerance)
