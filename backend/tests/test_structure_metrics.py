"""Regression tests for task-standard structural boundary evaluation."""

from __future__ import annotations

import pytest

from evaluation.analysis_metrics import compute_analysis_metrics
from evaluation.models import Reference
from evaluation.structure_metrics import compute_structure_boundary_metrics


def _sections(points: list[float]) -> list[dict[str, float]]:
    sections = []
    for start, end in zip(points, points[1:], strict=False):
        sections.append({"start": start, "end": end})
    return sections


def test_perfect_boundaries():
    reference = _sections([0.0, 5.0, 10.0, 15.0])
    metrics = compute_structure_boundary_metrics(reference, reference)
    assert metrics.reference_boundary_count == 4
    assert metrics.predicted_boundary_count == 4
    assert metrics.reference_interior_boundary_count == 2
    assert metrics.predicted_interior_boundary_count == 2
    assert metrics.f1_05 == pytest.approx(1.0)
    assert metrics.f1_3 == pytest.approx(1.0)
    assert metrics.f1_trimmed_05 == pytest.approx(1.0)
    assert metrics.f1_trimmed_3 == pytest.approx(1.0)


def test_task_and_interior_metrics_are_distinct():
    reference = _sections([0.0, 5.0, 10.0])
    predicted = _sections([0.0, 5.75, 10.0])
    metrics = compute_structure_boundary_metrics(predicted, reference)
    assert metrics.f1_05 == pytest.approx(2.0 / 3.0)
    assert metrics.f1_trimmed_05 == pytest.approx(0.0)
    assert metrics.f1_3 == pytest.approx(1.0)
    assert metrics.f1_trimmed_3 == pytest.approx(1.0)


def test_duplicate_predictions_do_not_double_count():
    reference = _sections([0.0, 5.0, 10.0])
    predicted = _sections([0.0, 4.8, 5.2, 10.0])
    metrics = compute_structure_boundary_metrics(predicted, reference)
    assert metrics.reference_boundary_count == 3
    assert metrics.predicted_boundary_count == 4
    assert metrics.reference_interior_boundary_count == 1
    assert metrics.predicted_interior_boundary_count == 2
    assert metrics.precision_05 == pytest.approx(0.75)
    assert metrics.recall_05 == pytest.approx(1.0)
    assert metrics.f1_05 == pytest.approx(6.0 / 7.0)
    assert metrics.precision_trimmed_05 == pytest.approx(0.5)
    assert metrics.recall_trimmed_05 == pytest.approx(1.0)
    assert metrics.f1_trimmed_05 == pytest.approx(2.0 / 3.0)


def test_missing_predictions_score_zero():
    reference = _sections([0.0, 5.0, 10.0])
    metrics = compute_structure_boundary_metrics([], reference)
    assert metrics.precision_05 == pytest.approx(0.0)
    assert metrics.recall_05 == pytest.approx(0.0)
    assert metrics.f1_05 == pytest.approx(0.0)
    assert metrics.f1_trimmed_05 == pytest.approx(0.0)


def test_single_segment_only_has_task_standard_endpoint_score():
    reference = _sections([0.0, 10.0])
    metrics = compute_structure_boundary_metrics(reference, reference)
    assert metrics.reference_boundary_count == 2
    assert metrics.reference_interior_boundary_count == 0
    assert metrics.f1_05 == pytest.approx(1.0)
    assert metrics.f1_3 == pytest.approx(1.0)
    assert metrics.f1_trimmed_05 is None
    assert metrics.f1_trimmed_3 is None


def test_analysis_metrics_expose_task_and_interior_scores():
    reference = Reference(sections=_sections([0.0, 5.0, 10.0]))
    perfect = compute_analysis_metrics(
        None,
        None,
        None,
        reference.sections,
        None,
        reference,
    )
    missing = compute_analysis_metrics(None, None, None, [], None, reference)
    assert perfect.section_f1 == pytest.approx(1.0)
    assert perfect.section_f1_3s == pytest.approx(1.0)
    assert perfect.section_f1_trimmed == pytest.approx(1.0)
    assert perfect.section_f1_trimmed_3s == pytest.approx(1.0)
    assert missing.section_f1 == pytest.approx(0.0)
    assert missing.section_f1_3s == pytest.approx(0.0)
    assert missing.section_f1_trimmed == pytest.approx(0.0)
    assert missing.section_f1_trimmed_3s == pytest.approx(0.0)
