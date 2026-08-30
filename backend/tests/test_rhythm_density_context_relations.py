from uuid import UUID, uuid4

import pytest

from domain.relation_observations import SecondsSpanLocator
from domain.rhythm_density_context_relations import compare_rhythm_density_to_context
from domain.rhythm_density_relations import RhythmDensityEvidence


def _window(
    start: float,
    density: float,
    *,
    end: float | None = None,
    window_size: float = 1.0,
    step_size: float = 1.0,
) -> dict:
    return {
        "start": start,
        "end": start + 1.0 if end is None else end,
        "density": density,
        "mode": "beat_relative",
        "unit": "events_per_beat",
        "coordinate_unit": "beats",
        "window_size": window_size,
        "step_size": step_size,
    }


def _evidence(
    windows: list[dict],
    *,
    include_coverage: bool = True,
    coverage_overrides: dict | None = None,
) -> tuple[RhythmDensityEvidence, UUID]:
    source_version_id = uuid4()
    coverage = None
    if include_coverage:
        coverage = {
            "policy_version": "complete_series_v1",
            "total_generated_window_count": len(windows),
            "stored_window_count": len(windows),
            "start_seconds": windows[0]["start"],
            "end_seconds": max(window["end"] for window in windows),
            "truncated": False,
        }
        if coverage_overrides:
            coverage.update(coverage_overrides)

    return (
        RhythmDensityEvidence(
            evidence_id=uuid4(),
            source_version_id=source_version_id,
            windows=windows,
            coverage=coverage,
            pulse_provenance={"engine": "beat_this", "engine_version": "1.1.0"},
        ),
        source_version_id,
    )


def _locator(source_version_id: UUID, start: float, end: float) -> SecondsSpanLocator:
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


def _measurement(result):
    assert result.sufficiency.status == "supported"
    assert len(result.measurements) == 1
    return result.measurements[0]


def test_work_reference_reports_descriptive_median_iqr_and_midrank():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 1.0),
            _window(1.0, 2.0),
            _window(2.0, 4.0),
            _window(3.0, 3.0),
            _window(4.0, 4.0),
            _window(5.0, 5.0),
            _window(6.0, 100.0),
        ]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 2.0, 3.0),
    )

    measurement = _measurement(result)
    assert result.kind == "rhythm_density_context_comparison"
    assert result.reference_population is not None
    assert result.reference_population.kind == "work_excluding_subject"
    assert result.reference_population.eligible_window_count == 6
    assert measurement.subject_value == 4.0
    assert measurement.comparison_value == 3.5
    assert measurement.delta == 0.5
    assert measurement.direction == "higher"
    assert measurement.reference_q1 == pytest.approx(2.25)
    assert measurement.reference_q3 == pytest.approx(4.75)
    assert measurement.reference_iqr == pytest.approx(2.5)
    assert measurement.subject_midrank_percentile == pytest.approx(58.3333333333)


def test_reference_population_excludes_every_window_intersecting_subject():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1), end=float(start + 2)) for start in range(9)]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 2.0, 4.0),
    )

    measurement = _measurement(result)
    assert result.reference_population is not None
    assert result.reference_population.eligible_window_count == 6
    assert result.reference_population.before_subject_window_count == 1
    assert result.reference_population.after_subject_window_count == 5
    assert measurement.subject_window_count == 1
    assert measurement.reference_window_count == 6


def test_local_context_uses_only_bounded_before_and_after_windows():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1)) for start in range(12)]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 5.0, 6.0),
        reference_kind="local_context",
        context_radius_seconds=3.0,
    )

    measurement = _measurement(result)
    assert result.comparison_locator is not None
    assert result.comparison_locator.start_seconds == 2.0
    assert result.comparison_locator.end_seconds == 9.0
    assert result.reference_population is not None
    assert result.reference_population.eligible_window_count == 6
    assert result.reference_population.before_subject_window_count == 3
    assert result.reference_population.after_subject_window_count == 3
    assert result.reference_population.covered_seconds == 6.0
    assert measurement.reference_window_count == 6
    assert measurement.reference_covered_seconds == 6.0


def test_local_context_requires_evidence_on_both_sides():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1)) for start in range(8)]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 1.0),
        reference_kind="local_context",
        context_radius_seconds=6.0,
    )

    assert result.sufficiency.status == "withhold"
    assert result.reference_population is not None
    assert result.reference_population.before_subject_window_count == 0
    assert result.reference_population.after_subject_window_count == 6
    assert any("before and after" in reason for reason in result.sufficiency.reasons)


def test_insufficient_reference_population_withholds_with_count():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1)) for start in range(5)]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 2.0, 3.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.reference_population is not None
    assert result.reference_population.eligible_window_count == 4
    assert any("at least 5" in reason for reason in result.sufficiency.reasons)


def test_contextual_comparison_requires_explicit_complete_series_coverage():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1)) for start in range(7)],
        include_coverage=False,
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 3.0, 4.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("coverage metadata" in reason for reason in result.sufficiency.reasons)


def test_truncated_coverage_withholds():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1)) for start in range(7)],
        coverage_overrides={
            "total_generated_window_count": 8,
            "truncated": True,
        },
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 3.0, 4.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    reasons = " ".join(result.sufficiency.reasons)
    assert "truncated" in reasons
    assert "window count" in reasons


def test_outlier_does_not_move_reference_median_and_rank_remains_descriptive():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 1.0),
            _window(1.0, 1.0),
            _window(2.0, 2.0),
            _window(3.0, 1.0),
            _window(4.0, 1.0),
            _window(5.0, 1.0),
            _window(6.0, 1.0),
            _window(7.0, 100.0),
        ]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 2.0, 3.0),
    )

    measurement = _measurement(result)
    assert measurement.comparison_value == 1.0
    assert measurement.reference_iqr == 0.0
    assert measurement.subject_midrank_percentile == pytest.approx(85.7142857143)


def test_zero_reference_median_omits_relative_delta():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 0.0),
            _window(1.0, 0.0),
            _window(2.0, 2.0),
            _window(3.0, 0.0),
            _window(4.0, 0.0),
            _window(5.0, 0.0),
        ]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 2.0, 3.0),
    )

    measurement = _measurement(result)
    assert measurement.comparison_value == 0.0
    assert measurement.delta == 2.0
    assert measurement.relative_delta is None
    assert measurement.direction == "higher"


def test_mixed_evidence_contract_withholds_through_shared_ab_validator():
    windows = [_window(float(start), float(start + 1)) for start in range(7)]
    windows[-1] = _window(6.0, 7.0, window_size=2.0)
    evidence, source_version_id = _evidence(windows)

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 3.0, 4.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("window_size" in reason for reason in result.sufficiency.reasons)


def test_work_reference_rejects_context_radius():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1)) for start in range(7)]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 3.0, 4.0),
        context_radius_seconds=5.0,
    )

    assert result.sufficiency.status == "withhold"
    assert any("only valid for local_context" in reason for reason in result.sufficiency.reasons)


def test_local_context_rejects_invalid_radius():
    evidence, source_version_id = _evidence(
        [_window(float(start), float(start + 1)) for start in range(7)]
    )

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 3.0, 4.0),
        reference_kind="local_context",
        context_radius_seconds=0.0,
    )

    assert result.sufficiency.status == "withhold"
    assert any("positive finite" in reason for reason in result.sufficiency.reasons)


def test_context_relation_serialization_and_provenance_are_explicit():
    coverage_windows = [_window(float(start), float(start + 1)) for start in range(7)]
    evidence, source_version_id = _evidence(coverage_windows)

    result = compare_rhythm_density_to_context(
        evidence,
        subject_locator=_locator(source_version_id, 3.0, 4.0),
    )
    round_trip = type(result).model_validate_json(result.model_dump_json())

    assert round_trip == result
    assert result.provenance["reference_summary"] == "median_iqr_empirical_midrank"
    assert result.provenance["rank_target"] == "subject_median_vs_reference_window_values"
    assert result.provenance["independent_observations_assumed"] is False
    assert result.provenance["inferential_statistics_emitted"] is False
    assert result.provenance["semantic_interpretation_emitted"] is False
    assert result.provenance["persistence_coverage"]["policy_version"] == "complete_series_v1"

    payload = result.model_dump(mode="json")
    assert "statement" not in payload
    assert "claim" not in payload
    assert "significant" not in result.model_dump_json().lower()
