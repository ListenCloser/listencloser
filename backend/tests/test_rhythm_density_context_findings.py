from uuid import uuid4

from domain.relation_observations import SecondsSpanLocator
from domain.rhythm_density_context import contextualize_rhythm_density_within_work
from domain.rhythm_density_context_findings import (
    GroundedContextFinding,
    compose_grounded_rhythm_density_context_finding,
)
from domain.rhythm_density_relations import RhythmDensityEvidence


def _window(start: float, end: float, density: float) -> dict:
    return {
        "start": start,
        "end": end,
        "density": density,
        "mode": "beat_relative",
        "unit": "events_per_beat",
        "coordinate_unit": "beats",
        "window_size": 2.0,
        "step_size": 1.0,
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


def _evidence(*, include_coverage: bool = True):
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
    source_version_id = uuid4()
    evidence = RhythmDensityEvidence(
        evidence_id=uuid4(),
        source_version_id=source_version_id,
        windows=windows,
        coverage=_coverage(windows) if include_coverage else None,
        pulse_provenance={"engine": "beat_this", "engine_version": "1.1.0"},
    )
    return evidence, source_version_id


def _locator(source_version_id, start: float = 4.0, end: float = 6.0):
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


def _supported_observation():
    evidence, source_version_id = _evidence()
    observation = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id),
    )
    assert observation.sufficiency.status == "supported"
    return observation


def test_supported_context_composes_literal_focusable_finding():
    observation = _supported_observation()

    finding = compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin="user_selected",
    )

    assert finding is not None
    assert finding.source_relation_id == observation.id
    assert finding.subject_locator == observation.subject_locator
    assert finding.reference_population == observation.reference_population
    assert finding.support_refs == observation.support_refs
    assert finding.sufficiency == observation.sufficiency
    assert finding.subject_origin == "user_selected"
    assert finding.selection_conditioned_on_rhythm_density is False
    assert finding.available_actions == ["focus", "evidence"]
    assert "compare" not in finding.available_actions

    measurement = finding.measurements[0]
    assert measurement.support_ref == observation.support_refs[0]
    assert measurement.subject_value == 5.0
    assert measurement.reference_median == 1.5
    assert measurement.reference_q1 == 1.0
    assert measurement.reference_q3 == 2.0
    assert measurement.reference_iqr == 1.0
    assert measurement.delta_from_reference_median == 3.5
    assert measurement.empirical_midrank_percentile == 100.0
    assert finding.headline == (
        "Median event density here is higher than the median elsewhere in this Work "
        "(5 vs 1.5 events/beat)."
    )
    assert finding.evidence_summary == (
        "Reference middle 50%: 1–2 events/beat. Empirical mid-rank percentile: 100.0."
    )


def test_extrema_subject_origin_preserves_selection_conditioning_without_salience_claim():
    observation = _supported_observation()

    peak = compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin="legacy_density_peak",
    )
    valley = compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin="legacy_density_valley",
    )
    other = compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin="other_grounded_candidate",
    )

    assert peak is not None
    assert valley is not None
    assert other is not None
    assert peak.selection_conditioned_on_rhythm_density is True
    assert valley.selection_conditioned_on_rhythm_density is True
    assert other.selection_conditioned_on_rhythm_density is None
    assert peak.provenance["subject_origin"] == "legacy_density_peak"
    assert peak.provenance["selection_conditioned_on_rhythm_density"] is True
    assert peak.provenance["salience_independence_claimed"] is False


def test_withheld_context_does_not_compose_product_finding():
    evidence, source_version_id = _evidence(include_coverage=False)
    observation = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=_locator(source_version_id),
    )
    assert observation.sufficiency.status == "withhold"

    finding = compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin="user_selected",
    )

    assert finding is None


def test_composer_rejects_fabricated_continuous_comparison_locator():
    observation = _supported_observation()
    fabricated = observation.model_copy(
        update={"comparison_locator": observation.subject_locator},
    )

    finding = compose_grounded_rhythm_density_context_finding(
        fabricated,
        subject_origin="user_selected",
    )

    assert finding is None


def test_composer_rejects_inconsistent_measurement_math():
    observation = _supported_observation()
    measurement = observation.measurements[0]
    inconsistent_measurement = measurement.model_copy(
        update={
            "reference_iqr": measurement.reference_iqr + 1.0,
            "delta_from_reference_median": measurement.delta_from_reference_median + 1.0,
        }
    )
    inconsistent = observation.model_copy(update={"measurements": [inconsistent_measurement]})

    finding = compose_grounded_rhythm_density_context_finding(
        inconsistent,
        subject_origin="user_selected",
    )

    assert finding is None


def test_composer_rejects_non_finite_measurement_and_reference_count_drift():
    observation = _supported_observation()
    measurement = observation.measurements[0]
    non_finite = observation.model_copy(
        update={"measurements": [measurement.model_copy(update={"subject_value": float("nan")})]}
    )
    assert (
        compose_grounded_rhythm_density_context_finding(
            non_finite,
            subject_origin="user_selected",
        )
        is None
    )

    assert observation.reference_population is not None
    drifted_population = observation.reference_population.model_copy(
        update={
            "eligible_window_count": observation.reference_population.eligible_window_count + 1,
        }
    )
    count_drift = observation.model_copy(update={"reference_population": drifted_population})
    assert (
        compose_grounded_rhythm_density_context_finding(
            count_drift,
            subject_origin="user_selected",
        )
        is None
    )


def test_composer_requires_explicit_non_inferential_relation_provenance():
    observation = _supported_observation()
    provenance = dict(observation.provenance)
    provenance["inferential_statistics_emitted"] = True
    inferential = observation.model_copy(update={"provenance": provenance})

    finding = compose_grounded_rhythm_density_context_finding(
        inferential,
        subject_origin="user_selected",
    )

    assert finding is None


def test_grounded_context_finding_serializes_without_semantic_or_inferential_claims():
    observation = _supported_observation()
    finding = compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin="legacy_density_peak",
    )
    assert finding is not None

    payload = finding.model_dump(mode="json")
    rendered = finding.model_dump_json().lower()
    for forbidden in (
        "significant",
        "exciting",
        "dramatic",
        "groovy",
        "important",
        "chorus-like",
    ):
        assert forbidden not in rendered

    restored = GroundedContextFinding.model_validate(payload)
    assert restored == finding
