"""Deterministic metrics for manually annotated audio-language evaluation outputs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

CONDITIONS = ("audio_only", "evidence_only", "audio_plus_evidence")


def _validate_rating(row: dict[str, Any], name: str) -> None:
    value = row.get(name)
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric or null")
    if not 1 <= float(value) <= 5:
        raise ValueError(f"{name} must be in [1, 5]")


def _validate_assessment(row: dict[str, Any]) -> None:
    condition = row.get("condition")
    if condition not in CONDITIONS:
        raise ValueError(f"condition must be one of {CONDITIONS}")

    for name in ("case_id", "question_id"):
        value = row.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")

    count_names = (
        "supported_claims",
        "contradicted_claims",
        "unsupported_claims",
        "total_claims",
    )
    for name in count_names:
        value = row.get(name)
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    if (
        row["supported_claims"]
        + row["contradicted_claims"]
        + row["unsupported_claims"]
        != row["total_claims"]
    ):
        raise ValueError("claim categories must sum to total_claims")

    for name in ("expected_support_refs", "cited_support_refs"):
        value = row.get(name)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{name} must be a list of strings")

    for name in ("should_abstain", "abstained", "requires_temporal_grounding"):
        if type(row.get(name)) is not bool:
            raise ValueError(f"{name} must be a boolean")

    temporal_correct = row.get("temporal_grounding_correct")
    if row["requires_temporal_grounding"]:
        if type(temporal_correct) is not bool:
            raise ValueError(
                "temporal_grounding_correct must be boolean when temporal grounding is required"
            )
    elif temporal_correct is not None and type(temporal_correct) is not bool:
        raise ValueError("temporal_grounding_correct must be boolean or null")

    _validate_rating(row, "usefulness_rating")
    _validate_rating(row, "specificity_rating")


def _mean_present(items: list[dict[str, Any]], name: str) -> float | None:
    values = [float(row[name]) for row in items if row.get(name) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _assessment_keys(items: list[dict[str, Any]]) -> list[str]:
    return sorted(f"{row['case_id']}::{row['question_id']}" for row in items)


def score_assessments(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate grounding metrics from manual claim-level annotations."""
    items = list(rows)
    if not items:
        raise ValueError("at least one assessment is required")
    for row in items:
        _validate_assessment(row)

    assessment_keys = _assessment_keys(items)
    if len(set(assessment_keys)) != len(assessment_keys):
        raise ValueError("duplicate case_id/question_id assessments are not allowed per condition")

    total_claims = sum(row["total_claims"] for row in items)
    supported = sum(row["supported_claims"] for row in items)
    contradicted = sum(row["contradicted_claims"] for row in items)
    unsupported = sum(row["unsupported_claims"] for row in items)

    expected_ref_count = 0
    cited_ref_count = 0
    cited_expected_count = 0
    for row in items:
        expected = set(row["expected_support_refs"])
        cited = set(row["cited_support_refs"])
        expected_ref_count += len(expected)
        cited_ref_count += len(cited)
        cited_expected_count += len(expected & cited)

    temporal_items = [row for row in items if row["requires_temporal_grounding"]]

    return {
        "num_items": len(items),
        "assessment_keys": assessment_keys,
        "total_claims": total_claims,
        "supported_claim_rate": round(supported / total_claims, 6) if total_claims else None,
        "contradiction_rate": (
            round(contradicted / total_claims, 6) if total_claims else None
        ),
        "unsupported_claim_rate": (
            round(unsupported / total_claims, 6) if total_claims else None
        ),
        "citation_recall": (
            round(cited_expected_count / expected_ref_count, 6)
            if expected_ref_count
            else None
        ),
        "citation_precision": (
            round(cited_expected_count / cited_ref_count, 6) if cited_ref_count else None
        ),
        "abstention_accuracy": round(
            sum(row["should_abstain"] == row["abstained"] for row in items) / len(items),
            6,
        ),
        "temporal_grounding_accuracy": (
            round(
                sum(row["temporal_grounding_correct"] is True for row in temporal_items)
                / len(temporal_items),
                6,
            )
            if temporal_items
            else None
        ),
        "mean_usefulness_rating": _mean_present(items, "usefulness_rating"),
        "mean_specificity_rating": _mean_present(items, "specificity_rating"),
    }


def score_by_condition(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    items = list(rows)
    if not items:
        raise ValueError("at least one assessment is required")
    for row in items:
        _validate_assessment(row)

    grouped: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        matches = [row for row in items if row["condition"] == condition]
        if matches:
            grouped[condition] = score_assessments(matches)
    return grouped


def _not_worse(
    baseline: dict[str, Any], combined: dict[str, Any], field: str, *, higher_is_better: bool
) -> bool:
    left = baseline.get(field)
    right = combined.get(field)
    if left is None or right is None:
        return True
    return right >= left if higher_is_better else right <= left


def grounded_value_gate(grouped: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Test whether raw audio adds grounded value over evidence-only explanation.

    This intentionally avoids a weighted composite. Audio+evidence must cover
    exactly the same cases/questions, improve factual support and human-rated
    usefulness, and not worsen trust metrics.
    """
    baseline = grouped.get("evidence_only")
    combined = grouped.get("audio_plus_evidence")
    if baseline is None or combined is None:
        return {
            "evaluable": False,
            "passes": False,
            "reason": "both evidence_only and audio_plus_evidence conditions are required",
        }

    if baseline.get("assessment_keys") != combined.get("assessment_keys"):
        return {
            "evaluable": False,
            "passes": False,
            "reason": (
                "evidence_only and audio_plus_evidence must contain the same "
                "case_id/question_id coverage"
            ),
            "evidence_only_keys": baseline.get("assessment_keys"),
            "audio_plus_evidence_keys": combined.get("assessment_keys"),
        }

    required = (
        "supported_claim_rate",
        "contradiction_rate",
        "unsupported_claim_rate",
        "mean_usefulness_rating",
        "mean_specificity_rating",
    )
    if any(baseline.get(field) is None or combined.get(field) is None for field in required):
        return {
            "evaluable": False,
            "passes": False,
            "reason": (
                "both conditions require annotated claims plus usefulness and specificity ratings"
            ),
        }

    criteria = {
        "matched_case_question_coverage": True,
        "supported_claim_rate_improves": (
            combined["supported_claim_rate"] > baseline["supported_claim_rate"]
        ),
        "contradiction_rate_not_worse": (
            combined["contradiction_rate"] <= baseline["contradiction_rate"]
        ),
        "unsupported_claim_rate_not_worse": (
            combined["unsupported_claim_rate"] <= baseline["unsupported_claim_rate"]
        ),
        "citation_recall_not_worse": _not_worse(
            baseline, combined, "citation_recall", higher_is_better=True
        ),
        "citation_precision_not_worse": _not_worse(
            baseline, combined, "citation_precision", higher_is_better=True
        ),
        "abstention_accuracy_not_worse": (
            combined["abstention_accuracy"] >= baseline["abstention_accuracy"]
        ),
        "temporal_grounding_not_worse": _not_worse(
            baseline, combined, "temporal_grounding_accuracy", higher_is_better=True
        ),
        "usefulness_improves": (
            combined["mean_usefulness_rating"] > baseline["mean_usefulness_rating"]
        ),
        "specificity_not_worse": (
            combined["mean_specificity_rating"] >= baseline["mean_specificity_rating"]
        ),
    }
    return {
        "evaluable": True,
        "passes": all(criteria.values()),
        "criteria": criteria,
        "evidence_only": baseline,
        "audio_plus_evidence": combined,
        "rule": (
            "audio_plus_evidence must use matched case/question coverage, improve supported-claim "
            "rate and usefulness, and not worsen contradiction, unsupported claims, citation "
            "quality, abstention, temporal grounding, or specificity"
        ),
    }
