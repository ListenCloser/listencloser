"""Deterministic A/B relations over promoted rhythm-density evidence.

This module deliberately layers on the generic relation vocabulary without
changing the first perceptual relation primitive. It accepts only the promoted
MIDI+beats rhythm-density contract and emits literal numeric comparisons over
explicit seconds-authoritative spans.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Literal
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from domain.relation_observations import (
    RelationObservation,
    RelationSufficiency,
    SecondsSpanLocator,
)

_RELATION_ENGINE_VERSION = "1.0"
_RELATIVE_DENOMINATOR_EPSILON = 1e-9
_NUMERIC_ATOL = 1e-12
_NUMERIC_RTOL = 1e-9


class RhythmDensityEvidenceRef(BaseModel):
    """#371-compatible reference to one persisted rhythm-density Insight."""

    model_config = ConfigDict(frozen=True)

    type: Literal["external"] = "external"
    namespace: Literal["rhythm_density_insight"] = "rhythm_density_insight"
    id: str


class RhythmDensityMeasurement(BaseModel):
    """Literal A/B aggregate over compatible beat-relative density windows."""

    model_config = ConfigDict(frozen=True)

    feature: Literal["rhythm_density"] = "rhythm_density"
    aggregate: Literal["median"] = "median"
    unit: Literal["events_per_beat"] = "events_per_beat"
    normalization: Literal["events_per_beat"] = "events_per_beat"
    coordinate_unit: Literal["beats"] = "beats"
    window_size: float = Field(gt=0)
    step_size: float = Field(gt=0)
    subject_value: float
    comparison_value: float
    delta: float
    relative_delta: float | None = None
    direction: Literal["higher", "lower", "unchanged"]
    subject_window_count: int = Field(ge=1)
    comparison_window_count: int = Field(ge=1)


class RhythmDensityRelationObservation(RelationObservation):
    """RelationObservation specialization for promoted rhythm-density evidence."""

    kind: Literal["rhythm_density_span_comparison"] = "rhythm_density_span_comparison"
    support_refs: list[RhythmDensityEvidenceRef] = Field(default_factory=list)
    measurements: list[RhythmDensityMeasurement] = Field(default_factory=list)


class RhythmDensityEvidence(BaseModel):
    """Persisted promoted rhythm-density evidence plus authoritative lineage."""

    model_config = ConfigDict(frozen=True)

    evidence_id: UUID
    source_version_id: UUID
    windows: list[dict[str, Any]] = Field(default_factory=list)
    pulse_provenance: dict[str, Any] | None = None


def _provenance(
    evidence: RhythmDensityEvidence,
    contract: dict[str, float | str] | None,
) -> dict[str, Any]:
    provenance: dict[str, Any] = {
        "engine": "rhythm_density_span_compare",
        "engine_version": _RELATION_ENGINE_VERSION,
        "aggregate": "median",
        "source_version_id": str(evidence.source_version_id),
        "evidence_id": str(evidence.evidence_id),
        "coverage_policy": (
            "selected spans must be covered to within one evidence step at each boundary; "
            "only fully-contained beat-relative density windows are aggregated"
        ),
        "relative_denominator_epsilon": _RELATIVE_DENOMINATOR_EPSILON,
        "semantic_interpretation_emitted": False,
    }
    if contract:
        provenance["evidence_contract"] = dict(contract)
    if evidence.pulse_provenance is not None:
        provenance["pulse_provenance"] = evidence.pulse_provenance
    return provenance


def _withheld(
    evidence: RhythmDensityEvidence,
    subject: SecondsSpanLocator,
    comparison: SecondsSpanLocator,
    reasons: Sequence[str],
    contract: dict[str, float | str] | None = None,
) -> RhythmDensityRelationObservation:
    return RhythmDensityRelationObservation(
        subject_locator=subject,
        comparison_locator=comparison,
        support_refs=[],
        measurements=[],
        sufficiency=RelationSufficiency(status="withhold", reasons=list(reasons)),
        provenance=_provenance(evidence, contract),
    )


def _validate_locator(
    locator: SecondsSpanLocator,
    evidence: RhythmDensityEvidence,
    label: str,
) -> list[str]:
    reasons: list[str] = []
    if not math.isfinite(locator.start_seconds) or not math.isfinite(locator.end_seconds):
        reasons.append(f"{label} span boundaries must be finite")
        return reasons
    if locator.start_seconds < 0:
        reasons.append(f"{label} span starts before the source")
    if locator.end_seconds <= locator.start_seconds:
        reasons.append(f"{label} span must have positive duration")
    if locator.source_artifact_version_id != evidence.source_version_id:
        reasons.append(f"{label} span source version does not match rhythm density evidence")
    return reasons


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validated_windows(
    evidence: RhythmDensityEvidence,
) -> tuple[list[dict[str, float]], dict[str, float | str] | None, list[str]]:
    reasons: list[str] = []
    normalized: list[dict[str, float]] = []
    contract: dict[str, float | str] | None = None
    previous_start: float | None = None

    if not evidence.windows:
        return [], None, ["promoted rhythm density evidence has no windows"]

    for index, raw_window in enumerate(evidence.windows):
        if not isinstance(raw_window, dict):
            reasons.append(f"rhythm density window {index} must be an object")
            continue

        mode = raw_window.get("mode")
        unit = raw_window.get("unit")
        coordinate_unit = raw_window.get("coordinate_unit")
        if mode != "beat_relative":
            reasons.append(f"rhythm density window {index} is not beat_relative")
        if unit != "events_per_beat":
            reasons.append(f"rhythm density window {index} is not events_per_beat")
        if coordinate_unit != "beats":
            reasons.append(f"rhythm density window {index} coordinate unit is not beats")

        numeric_keys = ("start", "end", "density", "window_size", "step_size")
        if any(not _finite_number(raw_window.get(key)) for key in numeric_keys):
            reasons.append(f"rhythm density window {index} has non-finite numeric fields")
            continue

        start = float(raw_window["start"])
        end = float(raw_window["end"])
        density = float(raw_window["density"])
        window_size = float(raw_window["window_size"])
        step_size = float(raw_window["step_size"])
        if start < 0:
            reasons.append(f"rhythm density window {index} starts before the source")
        if end <= start:
            reasons.append(f"rhythm density window {index} has non-positive duration")
        if density < 0:
            reasons.append(f"rhythm density window {index} has negative density")
        if window_size <= 0 or step_size <= 0:
            reasons.append(f"rhythm density window {index} has invalid window or step size")
        if previous_start is not None and start < previous_start:
            reasons.append("rhythm density windows are not ordered by start time")
        previous_start = start

        current_contract: dict[str, float | str] = {
            "mode": str(mode),
            "unit": str(unit),
            "coordinate_unit": str(coordinate_unit),
            "window_size": window_size,
            "step_size": step_size,
        }
        if contract is None:
            contract = current_contract
        else:
            for key in ("mode", "unit", "coordinate_unit"):
                if current_contract[key] != contract[key]:
                    reasons.append(f"rhythm density windows disagree on {key}")
            for key in ("window_size", "step_size"):
                if not math.isclose(
                    float(current_contract[key]),
                    float(contract[key]),
                    rel_tol=_NUMERIC_RTOL,
                    abs_tol=_NUMERIC_ATOL,
                ):
                    reasons.append(f"rhythm density windows disagree on {key}")

        normalized.append({"start": start, "end": end, "density": density})

    if reasons:
        return [], contract, reasons
    return normalized, contract, []


def _coverage_tolerance_seconds(
    windows: Sequence[dict[str, float]],
    contract: dict[str, float | str],
) -> float:
    """Estimate one evidence step in seconds from the beat-relative series."""
    window_size = float(contract["window_size"])
    step_size = float(contract["step_size"])
    duration_based_hops = [
        (window["end"] - window["start"]) * step_size / window_size for window in windows
    ]
    observed_start_hops = [
        windows[index]["start"] - windows[index - 1]["start"]
        for index in range(1, len(windows))
        if windows[index]["start"] > windows[index - 1]["start"]
    ]
    return max([*duration_based_hops, *observed_start_hops], default=0.0)


def _coverage_error_for_span(
    windows: Sequence[dict[str, float]],
    contract: dict[str, float | str],
    locator: SecondsSpanLocator,
    label: str,
) -> str | None:
    """Reject a span whose edges are more than one evidence step outside coverage.

    Beat-relative windows need not align exactly with arbitrary user-selected
    seconds boundaries, so the relation follows the existing perceptual-series
    policy and tolerates at most one evidence step of boundary slack. This still
    rejects a persisted prefix that is materially shorter than the requested
    span, including historical 50-window truncation.
    """
    if not windows:
        return f"{label} span has no rhythm density evidence coverage"

    coverage_start = windows[0]["start"]
    coverage_end = max(window["end"] for window in windows)
    boundary_tolerance = _coverage_tolerance_seconds(windows, contract) + _NUMERIC_ATOL
    if (
        coverage_start - locator.start_seconds > boundary_tolerance
        or locator.end_seconds - coverage_end > boundary_tolerance
    ):
        return (
            f"{label} span extends outside rhythm density evidence coverage "
            "by more than one evidence step"
        )
    return None


def _values_for_span(
    windows: Sequence[dict[str, float]],
    locator: SecondsSpanLocator,
    label: str,
) -> tuple[np.ndarray | None, str | None]:
    selected = [
        window["density"]
        for window in windows
        if window["start"] >= locator.start_seconds - _NUMERIC_ATOL
        and window["end"] <= locator.end_seconds + _NUMERIC_ATOL
    ]
    if not selected:
        return None, f"{label} span contains no complete rhythm density windows"
    return np.asarray(selected, dtype=float), None


def _relative_delta(delta: float, comparison: float) -> float | None:
    if abs(comparison) <= _RELATIVE_DENOMINATOR_EPSILON:
        return None
    return delta / abs(comparison)


def _direction(delta: float) -> Literal["higher", "lower", "unchanged"]:
    if math.isclose(delta, 0.0, rel_tol=_NUMERIC_RTOL, abs_tol=_NUMERIC_ATOL):
        return "unchanged"
    return "higher" if delta > 0 else "lower"


def compare_rhythm_density_spans(
    evidence: RhythmDensityEvidence,
    *,
    subject_locator: SecondsSpanLocator,
    comparison_locator: SecondsSpanLocator,
) -> RhythmDensityRelationObservation:
    """Compare promoted beat-relative event density over two explicit spans.

    Each requested span boundary must be covered to within one evidence step,
    and only complete density windows fully contained inside that span are
    eligible. The relation does not infer sections, resample evidence, mix
    seconds and beat units, or attach semantic meaning to numeric direction.
    """

    reasons = [
        *_validate_locator(subject_locator, evidence, "subject"),
        *_validate_locator(comparison_locator, evidence, "comparison"),
    ]
    windows, contract, contract_reasons = _validated_windows(evidence)
    reasons.extend(contract_reasons)
    if reasons:
        return _withheld(evidence, subject_locator, comparison_locator, reasons, contract)

    assert contract is not None
    for label, locator in (
        ("subject", subject_locator),
        ("comparison", comparison_locator),
    ):
        coverage_error = _coverage_error_for_span(windows, contract, locator, label)
        if coverage_error:
            reasons.append(coverage_error)
    if reasons:
        return _withheld(evidence, subject_locator, comparison_locator, reasons, contract)

    subject_values, subject_error = _values_for_span(windows, subject_locator, "subject")
    comparison_values, comparison_error = _values_for_span(
        windows, comparison_locator, "comparison"
    )
    if subject_error:
        reasons.append(subject_error)
    if comparison_error:
        reasons.append(comparison_error)
    if subject_values is None or comparison_values is None:
        return _withheld(
            evidence,
            subject_locator,
            comparison_locator,
            reasons or ["compatible rhythm density evidence is unavailable"],
            contract,
        )

    subject_aggregate = float(np.median(subject_values))
    comparison_aggregate = float(np.median(comparison_values))
    delta = subject_aggregate - comparison_aggregate
    if not math.isfinite(delta):
        return _withheld(
            evidence,
            subject_locator,
            comparison_locator,
            ["rhythm density aggregate delta is non-finite"],
            contract,
        )

    measurement = RhythmDensityMeasurement(
        window_size=float(contract["window_size"]),
        step_size=float(contract["step_size"]),
        subject_value=subject_aggregate,
        comparison_value=comparison_aggregate,
        delta=delta,
        relative_delta=_relative_delta(delta, comparison_aggregate),
        direction=_direction(delta),
        subject_window_count=len(subject_values),
        comparison_window_count=len(comparison_values),
    )
    return RhythmDensityRelationObservation(
        subject_locator=subject_locator,
        comparison_locator=comparison_locator,
        support_refs=[RhythmDensityEvidenceRef(id=f"{evidence.evidence_id}:rhythm_density")],
        measurements=[measurement],
        sufficiency=RelationSufficiency(status="supported"),
        provenance=_provenance(evidence, contract),
    )


__all__ = [
    "RhythmDensityEvidence",
    "RhythmDensityEvidenceRef",
    "RhythmDensityMeasurement",
    "RhythmDensityRelationObservation",
    "compare_rhythm_density_spans",
]
