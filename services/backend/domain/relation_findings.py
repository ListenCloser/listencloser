"""Product-facing finding contract for validated relation observations.

This layer translates already-supported deterministic relations into concise,
auditable product copy. It deliberately stays literal: RMS is not called loudness,
spectral centroid is not called brightness, and onset strength is not called
activity or excitement. Unsupported, experimental, or internally inconsistent
relations fail closed instead of producing prose.
"""

from __future__ import annotations

import math
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.perceptual_report import FeatureName
from domain.relation_observations import (
    EvidenceRef,
    RelationMeasurement,
    RelationObservation,
    RelationSufficiency,
    SecondsSpanLocator,
)

FindingAction = Literal["focus", "compare", "evidence"]

_FEATURE_CONTRACTS: dict[FeatureName, tuple[str, str]] = {
    "rms": ("linear_amplitude", "none"),
    "spectral_centroid": ("hz", "none"),
    "relative_band_energy": (
        "fraction_of_frame_power",
        "per_frame_total_stft_power",
    ),
    "onset_strength": (
        "librosa_onset_strength",
        "librosa_default_log_power_mel_flux",
    ),
}


class GroundedFindingMeasurement(BaseModel):
    """One user-facing literal clause tied to the exact evidence reference."""

    model_config = ConfigDict(frozen=True)

    support_ref: EvidenceRef
    feature: FeatureName
    direction: Literal["higher", "lower", "mixed", "unchanged"]
    summary: str
    unit: str | None
    normalization: str
    subject_value: float | list[float]
    comparison_value: float | list[float]
    delta: float | list[float]
    components: list[str] = Field(default_factory=list)


class GroundedRelationFinding(BaseModel):
    """Relation-first product finding with enough support to audit every clause."""

    model_config = ConfigDict(frozen=True)

    id: str
    source_relation_id: UUID
    kind: Literal["perceptual_span_comparison"] = "perceptual_span_comparison"
    relation_kind: Literal["compare"] = "compare"
    trust_class: Literal["deterministic_derived"] = "deterministic_derived"
    maturity: Literal["production"] = "production"
    subject_locator: SecondsSpanLocator
    comparison_locator: SecondsSpanLocator
    support_refs: list[EvidenceRef]
    measurements: list[GroundedFindingMeasurement]
    sufficiency: RelationSufficiency
    headline: str
    evidence_summary: str
    available_actions: list[FindingAction]
    provenance: dict[str, Any] = Field(default_factory=dict)


def _valid_locator(locator: SecondsSpanLocator) -> bool:
    return (
        math.isfinite(locator.start_seconds)
        and math.isfinite(locator.end_seconds)
        and locator.start_seconds >= 0
        and locator.end_seconds > locator.start_seconds
    )


def _finite_scalar(value: float | list[float]) -> float | None:
    if isinstance(value, list):
        return None
    scalar = float(value)
    return scalar if math.isfinite(scalar) else None


def _relative_scalar(value: float | list[float | None] | None) -> float | None:
    if value is None or isinstance(value, list):
        return None
    scalar = float(value)
    return scalar if math.isfinite(scalar) else None


def _direction_word(direction: str) -> str | None:
    if direction == "higher":
        return "higher"
    if direction == "lower":
        return "lower"
    return None


def _percent_delta_summary(label: str, measurement: RelationMeasurement) -> str | None:
    direction = _direction_word(measurement.direction)
    if measurement.direction == "unchanged":
        return f"Median {label} is unchanged across the two spans."
    if direction is None:
        return None

    relative_delta = _relative_scalar(measurement.relative_delta)
    if relative_delta is not None:
        return (
            f"Median {label} is {abs(relative_delta) * 100:.1f}% {direction} "
            "than in the comparison span."
        )

    subject = _finite_scalar(measurement.subject_value)
    comparison = _finite_scalar(measurement.comparison_value)
    if subject is None or comparison is None:
        return None
    return f"Median {label} is {direction} ({subject:.4g} vs {comparison:.4g})."


def _centroid_summary(measurement: RelationMeasurement) -> str | None:
    if measurement.direction == "unchanged":
        return "Median spectral centroid is unchanged across the two spans."
    direction = _direction_word(measurement.direction)
    delta = _finite_scalar(measurement.delta)
    if direction is None or delta is None:
        return None
    return (
        f"Median spectral centroid is {abs(delta):.0f} Hz {direction} "
        "than in the comparison span."
    )


def _band_energy_summary(measurement: RelationMeasurement) -> str | None:
    if not (
        isinstance(measurement.subject_value, list)
        and isinstance(measurement.comparison_value, list)
        and isinstance(measurement.delta, list)
    ):
        return None
    if not measurement.components:
        return None
    size = len(measurement.components)
    if not (
        len(measurement.subject_value) == size
        and len(measurement.comparison_value) == size
        and len(measurement.delta) == size
    ):
        return None

    deltas = [float(value) for value in measurement.delta]
    if not all(math.isfinite(value) for value in deltas):
        return None
    if measurement.direction == "unchanged":
        return "Relative band-energy distribution is unchanged across the two spans."

    changes = ", ".join(
        f"{component.replace('_', '-')}: {delta * 100:+.1f} pp"
        for component, delta in zip(measurement.components, deltas, strict=True)
    )
    return f"Relative band-energy change is {changes}."


def _measurement_summary(measurement: RelationMeasurement) -> str | None:
    expected_unit, expected_normalization = _FEATURE_CONTRACTS[measurement.feature]
    if measurement.unit != expected_unit or measurement.normalization != expected_normalization:
        return None

    if measurement.feature == "rms":
        return _percent_delta_summary("RMS amplitude", measurement)
    if measurement.feature == "spectral_centroid":
        return _centroid_summary(measurement)
    if measurement.feature == "onset_strength":
        return _percent_delta_summary("onset-strength value", measurement)
    if measurement.feature == "relative_band_energy":
        return _band_energy_summary(measurement)
    return None


def compose_grounded_relation_finding(
    observation: RelationObservation,
) -> GroundedRelationFinding | None:
    """Compose one literal product finding, or withhold if support is insufficient.

    The composer intentionally does not decide whether Loop, Show, Isolate, or Ask
    are available. Those actions require live playback, representation, source, or
    Ask-visibility state that this pure relation does not prove.
    """

    if observation.sufficiency.status != "supported":
        return None
    if not _valid_locator(observation.subject_locator) or not _valid_locator(
        observation.comparison_locator
    ):
        return None
    if (
        observation.subject_locator.source_artifact_version_id
        != observation.comparison_locator.source_artifact_version_id
    ):
        return None
    if not observation.support_refs or not observation.measurements:
        return None
    if len(observation.support_refs) != len(observation.measurements):
        return None
    unique_support_ids = {ref.id for ref in observation.support_refs}
    if len(unique_support_ids) != len(observation.support_refs):
        return None

    composed_measurements: list[GroundedFindingMeasurement] = []
    for support_ref, measurement in zip(
        observation.support_refs,
        observation.measurements,
        strict=True,
    ):
        if not support_ref.id.endswith(f":{measurement.feature}"):
            return None
        summary = _measurement_summary(measurement)
        if summary is None:
            return None
        composed_measurements.append(
            GroundedFindingMeasurement(
                support_ref=support_ref,
                feature=measurement.feature,
                direction=measurement.direction,
                summary=summary,
                unit=measurement.unit,
                normalization=measurement.normalization,
                subject_value=measurement.subject_value,
                comparison_value=measurement.comparison_value,
                delta=measurement.delta,
                components=list(measurement.components),
            )
        )

    changed_count = sum(item.direction != "unchanged" for item in composed_measurements)
    if changed_count == 0:
        headline = "The supported comparison found no measurable change in these audio features."
    elif len(composed_measurements) == 1:
        headline = composed_measurements[0].summary
    else:
        headline = (
            f"This passage differs from the comparison span across {changed_count} "
            f"of {len(composed_measurements)} supported audio measurements."
        )

    return GroundedRelationFinding(
        id=f"relation-finding-{observation.id}",
        source_relation_id=observation.id,
        kind=observation.kind,
        relation_kind=observation.relation_kind,
        trust_class=observation.trust_class,
        maturity=observation.maturity,
        subject_locator=observation.subject_locator,
        comparison_locator=observation.comparison_locator,
        support_refs=list(observation.support_refs),
        measurements=composed_measurements,
        sufficiency=observation.sufficiency,
        headline=headline,
        evidence_summary=" ".join(item.summary for item in composed_measurements),
        available_actions=["focus", "compare", "evidence"],
        provenance=dict(observation.provenance),
    )


__all__ = [
    "FindingAction",
    "GroundedFindingMeasurement",
    "GroundedRelationFinding",
    "compose_grounded_relation_finding",
]
