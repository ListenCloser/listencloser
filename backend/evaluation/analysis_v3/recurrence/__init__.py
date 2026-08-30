"""Bounded Analysis V3 recurrence evaluation helpers for #812."""

from .baseline import (
    FixedPerceptualMatrix,
    RecurrenceMatch,
    RECURRENCE_DIMENSIONS,
    build_fixed_perceptual_matrix,
    find_numpy_recurrence_matches,
)

__all__ = [
    "FixedPerceptualMatrix",
    "RecurrenceMatch",
    "RECURRENCE_DIMENSIONS",
    "build_fixed_perceptual_matrix",
    "find_numpy_recurrence_matches",
]
