from uuid import uuid4

from domain.relation_observations import RelationObservation, SecondsSpanLocator
from domain.rhythm_density_context import (
    RhythmDensityContextObservation,
    contextualize_rhythm_density_within_work,
)
from domain.rhythm_density_relations import RhythmDensityEvidence


def _window(
    start: float,
    end: float,
    density: float,
    *,
    window_size: float = 2.0,
    step_size: float = 1.0,
) -> dict:
    return {
        "start": start,
        "end": end,
        "density": density,
        "mode": "beat_relative",
        "unit": "events_per_beat",
        "coordinate_unit": "beats",
        "window_size": window_size,
        "step_size": step_size,
    }


def _coverage(windows: list[dict]) -> dict:
    return {
        "policy_version": "complete_series_v1",
        "total_generated_window_count": len(windows),
        "stored_window_count": len(windows),
        "start_seconds": windows[0]["start"],
        "end_seconds": windows[-1]["end"],
        "truncated": False,
    }


def _evidence(windows: list[dict], *, coverage: dict | None = None):
    source_version_id = uuid4()
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


def _locator(source_version_id, start: float, end: float) -> SecondsSpanLocator:
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


def test_work_context_excludes_every_window_intersecting_subject():
    windows = [
        _window(0.0, 2.0, 1.0),
        _window(1.0, 3.0, 1.0),
        _window(2.0, 4.0, 2.0),
        _window(3.0, 5.0, 4.0),
        _window(4.0, 6.0, 5.0),
        _window(5.0, 7.0, 4.0),
        _window(6.0, 8.0, 2.0),
        _window(7.0, 9.0, 3.0),
        _window(8.0, 10.0, 1.0),
    ]
    evidence, source_version_id = _evidence(windows, coverage=_coverage(windows))

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert isinstance(result, RelationObservation)
    assert result.comparison_locator is None
    assert result.sufficiency.status == "supported"
    assert result.reference_population is not None
    assert result.reference_population.eligible_window_count == 6
    assert result.reference_population.excluded_intersecting_window_count == 3
    assert result.reference_population.eligible_intervals_seconds == [
        (0.0, 4.0),
        (6.0, 10.0),
    ]
    assert result.reference_population.eligible_coverage_seconds == 8.0

    measurement = result.measurements[0]
    assert measurement.subject_value == 5.0
    assert measurement.reference_median == 1.5
    assert measurement.reference_q1 == 1.0
    assert measurement.reference_q3 == 2.0
    assert measurement.reference_iqr == 1.0
    assert measurement.delta_from_reference_median == 3.5
    assert measurement.direction == "higher"
    assert measurement.empirical_midrank_percentile == 100.0
    assert measurement.subject_window_count == 1
    assert measurement.reference_window_count == 6


def test_empirical_percentile_uses_deterministic_midrank_for_ties():
    windows = [
        _window(0.0, 2.0, 1.0, window_size=2.0, step_size=2.0),
        _window(2.0, 4.0, 2.0, window_size=2.0, step_size=2.0),
        _window(4.0, 6.0, 2.0, window_size=2.0, step_size=2.0),
        _window(6.0, 8.0, 2.0, window_size=2.0, step_size=2.0),
        _window(8.0, 10.0, 3.0, window_size=2.0, step_size=2.0),
    ]
    evidence, source_version_id = _evidence(windows, coverage=_coverage(windows))

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert result.sufficiency.status == "supported"
    measurement = result.measurements[0]
    assert measurement.reference_window_count == 4
    assert measurement.subject_value == 2.0
    assert measurement.reference_median == 2.0
    assert measurement.empirical_midrank_percentile == 50.0
    assert measurement.direction == "unchanged"
    assert measurement.quartile_method == "linear"
    assert measurement.percentile_convention == "empirical_midrank_reference_windows_v1"


def test_work_context_requires_declared_complete_persistence_coverage():
    windows = [
        _window(0.0, 2.0, 1.0, step_size=2.0),
        _window(2.0, 4.0, 1.0, step_size=2.0),
        _window(4.0, 6.0, 2.0, step_size=2.0),
        _window(6.0, 8.0, 3.0, step_size=2.0),
        _window(8.0, 10.0, 4.0, step_size=2.0),
    ]
    evidence, source_version_id = _evidence(windows)

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("complete_series_v1" in reason for reason in result.sufficiency.reasons)


def test_work_context_withholds_when_reference_population_is_too_small():
    windows = [
        _window(0.0, 2.0, 1.0, step_size=2.0),
        _window(2.0, 4.0, 2.0, step_size=2.0),
        _window(4.0, 6.0, 3.0, step_size=2.0),
        _window(6.0, 8.0, 4.0, step_size=2.0),
    ]
    evidence, source_version_id = _evidence(windows, coverage=_coverage(windows))

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.reference_population is not None
    assert result.reference_population.eligible_window_count == 3
    assert result.measurements == []
    assert any("at least 4" in reason for reason in result.sufficiency.reasons)


def test_malformed_complete_series_metadata_withholds_before_context_statistics():
    windows = [
        _window(0.0, 2.0, 1.0, step_size=2.0),
        _window(2.0, 4.0, 2.0, step_size=2.0),
        _window(4.0, 6.0, 3.0, step_size=2.0),
        _window(6.0, 8.0, 4.0, step_size=2.0),
        _window(8.0, 10.0, 5.0, step_size=2.0),
    ]
    malformed_coverage = _coverage(windows)
    malformed_coverage["stored_window_count"] = 4
    malformed_coverage["truncated"] = True
    evidence, source_version_id = _evidence(windows, coverage=malformed_coverage)

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    reasons = " ".join(result.sufficiency.reasons)
    assert "stored window count" in reasons
    assert "marked truncated" in reasons


def test_work_context_delegates_incompatible_contracts_to_public_density_validator():
    windows = [
        _window(0.0, 2.0, 1.0, step_size=2.0),
        _window(2.0, 4.0, 2.0, step_size=2.0),
        _window(4.0, 6.0, 3.0, step_size=2.0),
        _window(6.0, 8.0, 4.0, step_size=2.0),
        _window(8.0, 10.0, 5.0, step_size=1.0),
    ]
    evidence, source_version_id = _evidence(windows, coverage=_coverage(windows))

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("step_size" in reason for reason in result.sufficiency.reasons)


def test_reference_median_and_iqr_are_robust_to_one_extreme_window():
    windows = [
        _window(0.0, 2.0, 1.0, step_size=2.0),
        _window(2.0, 4.0, 1.0, step_size=2.0),
        _window(4.0, 6.0, 2.0, step_size=2.0),
        _window(6.0, 8.0, 1.0, step_size=2.0),
        _window(8.0, 10.0, 1.0, step_size=2.0),
        _window(10.0, 12.0, 100.0, step_size=2.0),
    ]
    evidence, source_version_id = _evidence(windows, coverage=_coverage(windows))

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert result.sufficiency.status == "supported"
    measurement = result.measurements[0]
    assert measurement.reference_window_count == 5
    assert measurement.reference_median == 1.0
    assert measurement.reference_iqr == 0.0
    assert measurement.empirical_midrank_percentile == 80.0


def test_context_observation_preserves_support_contract_and_non_inferential_provenance():
    windows = [
        _window(0.0, 2.0, 1.0, step_size=2.0),
        _window(2.0, 4.0, 2.0, step_size=2.0),
        _window(4.0, 6.0, 5.0, step_size=2.0),
        _window(6.0, 8.0, 3.0, step_size=2.0),
        _window(8.0, 10.0, 4.0, step_size=2.0),
    ]
    evidence, source_version_id = _evidence(windows, coverage=_coverage(windows))

    result = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id, 4.0, 6.0),
    )

    assert result.sufficiency.status == "supported"
    assert len(result.support_refs) == 1
    assert result.support_refs[0].namespace == "rhythm_density_insight"
    assert result.support_refs[0].id == f"{evidence.evidence_id}:rhythm_density"
    assert result.provenance["comparison_locator_semantics"] == (
        "none_discontinuous_reference_population"
    )
    assert result.provenance["reference_window_independence_assumed"] is False
    assert result.provenance["inferential_statistics_emitted"] is False
    assert result.provenance["semantic_interpretation_emitted"] is False
    assert result.provenance["quartile_method"] == "linear"
    assert result.provenance["percentile_convention"] == "empirical_midrank_reference_windows_v1"
    assert result.provenance["persistence_coverage"] == _coverage(windows)

    payload = result.model_dump(mode="json")
    assert "statement" not in payload
    assert "claim" not in payload
    assert "significant" not in result.model_dump_json().lower()

    restored = RhythmDensityContextObservation.model_validate(payload)
    assert restored == result
