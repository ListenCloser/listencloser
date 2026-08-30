from uuid import uuid4

from domain.relation_observations import SecondsSpanLocator
from domain.rhythm_density_context import contextualize_rhythm_density_within_work
from domain.rhythm_density_context_findings import compose_grounded_rhythm_density_context_finding
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


def _supported_observation():
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
        coverage={
            "policy_version": "complete_series_v1",
            "total_generated_window_count": len(windows),
            "stored_window_count": len(windows),
            "start_seconds": 0.0,
            "end_seconds": 10.0,
            "truncated": False,
        },
        pulse_provenance={"engine": "beat_this", "engine_version": "1.1.0"},
    )
    observation = contextualize_rhythm_density_within_work(
        evidence,
        subject_locator=SecondsSpanLocator(
            start_seconds=4.0,
            end_seconds=6.0,
            source_artifact_version_id=source_version_id,
            authority="user_selected",
        ),
    )
    assert observation.sufficiency.status == "supported"
    return observation


def _compose(observation):
    return compose_grounded_rhythm_density_context_finding(
        observation,
        subject_origin="user_selected",
    )


def test_composer_rejects_subject_locator_source_version_drift():
    observation = _supported_observation()
    drifted_locator = observation.subject_locator.model_copy(
        update={"source_artifact_version_id": uuid4()}
    )

    assert _compose(observation.model_copy(update={"subject_locator": drifted_locator})) is None


def test_composer_rejects_support_ref_evidence_id_drift():
    observation = _supported_observation()
    drifted_ref = observation.support_refs[0].model_copy(
        update={"id": f"{uuid4()}:rhythm_density"}
    )

    assert _compose(observation.model_copy(update={"support_refs": [drifted_ref]})) is None


def test_composer_rejects_positive_reference_count_with_empty_coverage():
    observation = _supported_observation()
    assert observation.reference_population is not None
    empty_coverage = observation.reference_population.model_copy(
        update={
            "eligible_intervals_seconds": [],
            "eligible_coverage_seconds": 0.0,
        }
    )

    assert _compose(observation.model_copy(update={"reference_population": empty_coverage})) is None


def test_composer_rejects_reference_interval_outside_source_coverage_envelope():
    observation = _supported_observation()
    assert observation.reference_population is not None
    population = observation.reference_population
    intervals = list(population.eligible_intervals_seconds)
    intervals.append(
        (
            population.source_coverage_end_seconds + 1.0,
            population.source_coverage_end_seconds + 2.0,
        )
    )
    outside_envelope = population.model_copy(
        update={
            "eligible_intervals_seconds": intervals,
            "eligible_coverage_seconds": population.eligible_coverage_seconds + 1.0,
        }
    )

    assert (
        _compose(observation.model_copy(update={"reference_population": outside_envelope}))
        is None
    )
