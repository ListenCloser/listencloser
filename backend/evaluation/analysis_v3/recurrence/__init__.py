"""Bounded Analysis V3 recurrence evaluation helpers for #812."""

from .baseline import (
    RECURRENCE_DIMENSIONS,
    FixedPerceptualMatrix,
    RecurrenceMatch,
    build_fixed_perceptual_matrix,
    find_numpy_recurrence_matches,
)

__all__ = [
    "RECURRENCE_DIMENSIONS",
    "FixedPerceptualMatrix",
    "RecurrenceMatch",
    "build_fixed_perceptual_matrix",
    "find_numpy_recurrence_matches",
]
