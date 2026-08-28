"""Meter evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MeterResult:
    numerator_correct: bool | None
    denominator_correct: bool | None
    meter_correct: bool | None
    predicted_numerator: int | None
    predicted_denominator: int | None
    reference_numerator: int | None
    reference_denominator: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "numerator_correct": self.numerator_correct,
            "denominator_correct": self.denominator_correct,
            "meter_correct": self.meter_correct,
            "predicted_numerator": self.predicted_numerator,
            "predicted_denominator": self.predicted_denominator,
            "reference_numerator": self.reference_numerator,
            "reference_denominator": self.reference_denominator,
        }


def compute_meter_accuracy(
    predicted_numerator: int | None,
    predicted_denominator: int | None,
    reference_numerator: int | None,
    reference_denominator: int | None,
) -> MeterResult:
    """Compute meter accuracy."""
    num_correct = None
    den_correct = None
    meter_correct = None

    if predicted_numerator is not None and reference_numerator is not None:
        num_correct = predicted_numerator == reference_numerator

    if predicted_denominator is not None and reference_denominator is not None:
        den_correct = predicted_denominator == reference_denominator

    if num_correct is not None and den_correct is not None:
        meter_correct = num_correct and den_correct

    return MeterResult(
        numerator_correct=num_correct,
        denominator_correct=den_correct,
        meter_correct=meter_correct,
        predicted_numerator=predicted_numerator,
        predicted_denominator=predicted_denominator,
        reference_numerator=reference_numerator,
        reference_denominator=reference_denominator,
    )
