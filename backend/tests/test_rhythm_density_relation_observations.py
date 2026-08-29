from uuid import uuid4

from domain.relation_observations import RelationObservation, SecondsSpanLocator
from domain.rhythm_density_relations import (
    RhythmDensityEvidence,
    compare_rhythm_density_spans,
)


def _window(
    start: float,
    end: float,
    density: float,
    *,
    mode: str = "beat_relative",
    unit: str = "events_per_beat",
    coordinate_unit: str = "beats",
    window_size: float = 2.0,
    step_size: float = 1.0,
) -> dict:
    return {
        "start": start,
        "end": end,
        "density": density,
        "mode": mode,
        "unit": unit,
        "coordinate_unit": coordinate_unit,
        "window_size": window_size,
        "step_size": step_size,
    }


def _evidence(windows: list[dict]):
    source_version_id = uuid4()
    evidence = RhythmDensityEvidence(
        evidence_id=uuid4(),
        source_version_id=source_version_id,
        windows=windows,
        pulse_provenance={"engine": "beat_this", "engine_version": "1.1.0"},
    )
    return evidence, source_version_id


def _locator(source_version_id, start: float, end: float):
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


def _measurement(result):
    assert isinstance(result, RelationObservation)
    assert len(result.measurements) == 1
    measurement = result.measurements[0]
    assert measurement.feature == "rhythm_density"
    return measurement


def test_identical_density_spans_are_unchanged():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, 1.0),
            _window(1.0, 3.0, 1.0),
            _window(3.0, 5.0, 1.0),
            _window(4.0, 6.0, 1.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 3.0),
        comparison_locator=_locator(source_version_id, 3.0, 6.0),
    )

    measurement = _measurement(result)
    assert result.kind == "rhythm_density_span_comparison"
    assert result.sufficiency.status == "supported"
    assert measurement.subject_value == 1.0
    assert measurement.comparison_value == 1.0
    assert measurement.delta == 0.0
    assert measurement.direction == "unchanged"


def test_higher_and_lower_density_are_literal_numeric_directions():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, 0.5),
            _window(1.0, 3.0, 1.0),
            _window(3.0, 5.0, 2.0),
            _window(4.0, 6.0, 3.0),
        ]
    )

    higher = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 3.0, 6.0),
        comparison_locator=_locator(source_version_id, 0.0, 3.0),
    )
    lower = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 3.0),
        comparison_locator=_locator(source_version_id, 3.0, 6.0),
    )

    higher_measurement = _measurement(higher)
    lower_measurement = _measurement(lower)
    assert higher_measurement.subject_value == 2.5
    assert higher_measurement.comparison_value == 0.75
    assert higher_measurement.delta == 1.75
    assert higher_measurement.direction == "higher"
    assert lower_measurement.delta == -1.75
    assert lower_measurement.direction == "lower"


def test_mixed_window_contract_withholds_instead_of_resampling():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, 1.0, window_size=2.0),
            _window(2.0, 3.0, 1.0, window_size=1.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 2.0),
        comparison_locator=_locator(source_version_id, 2.0, 3.0),
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("window_size" in reason for reason in result.sufficiency.reasons)


def test_seconds_fallback_is_not_eligible_product_evidence():
    evidence, source_version_id = _evidence(
        [
            _window(
                0.0,
                2.0,
                1.0,
                mode="seconds",
                unit="events_per_second",
                coordinate_unit="seconds",
            )
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 2.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    assert result.sufficiency.status == "withhold"
    reasons = " ".join(result.sufficiency.reasons)
    assert "beat_relative" in reasons
    assert "events_per_beat" in reasons


def test_source_version_mismatch_withholds():
    evidence, source_version_id = _evidence([_window(0.0, 2.0, 1.0)])

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(uuid4(), 0.0, 2.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    assert result.sufficiency.status == "withhold"
    assert any("source version" in reason for reason in result.sufficiency.reasons)


def test_non_finite_or_malformed_windows_withhold():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, float("nan")),
            _window(2.0, 2.0, 1.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 2.0),
        comparison_locator=_locator(source_version_id, 2.0, 3.0),
    )

    assert result.sufficiency.status == "withhold"
    reasons = " ".join(result.sufficiency.reasons)
    assert "non-finite" in reasons
    assert "non-positive duration" in reasons


def test_partial_overlap_only_withholds():
    evidence, source_version_id = _evidence([_window(0.0, 2.0, 1.0)])

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.5, 1.5),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    assert result.sufficiency.status == "withhold"
    assert any("no complete" in reason for reason in result.sufficiency.reasons)


def test_boundary_aligned_complete_windows_are_supported():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, 1.0),
            _window(1.0, 3.0, 3.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 3.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    measurement = _measurement(result)
    assert result.sufficiency.status == "supported"
    assert measurement.subject_window_count == 2
    assert measurement.comparison_window_count == 1
    assert measurement.subject_value == 2.0
    assert measurement.comparison_value == 1.0
    assert measurement.window_size == 2.0
    assert measurement.step_size == 1.0
    assert measurement.coordinate_unit == "beats"


def test_zero_comparison_density_omits_relative_delta():
    evidence, source_version_id = _evidence(
        [
            _window(0.0, 2.0, 0.0),
            _window(2.0, 4.0, 2.0),
        ]
    )

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 2.0, 4.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    measurement = _measurement(result)
    assert result.sufficiency.status == "supported"
    assert measurement.delta == 2.0
    assert measurement.relative_delta is None
    assert measurement.direction == "higher"


def test_support_ref_and_provenance_preserve_evidence_contract():
    evidence, source_version_id = _evidence([_window(0.0, 2.0, 1.0)])

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 2.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    assert result.sufficiency.status == "supported"
    assert len(result.support_refs) == 1
    assert result.support_refs[0].namespace == "rhythm_density_insight"
    assert result.support_refs[0].id == f"{evidence.evidence_id}:rhythm_density"
    contract = result.provenance["evidence_contract"]
    assert contract == {
        "mode": "beat_relative",
        "unit": "events_per_beat",
        "coordinate_unit": "beats",
        "window_size": 2.0,
        "step_size": 1.0,
    }
    assert result.provenance["pulse_provenance"]["engine"] == "beat_this"


def test_rhythm_relation_serialization_round_trip():
    evidence, source_version_id = _evidence([_window(0.0, 2.0, 1.0)])
    subject = _locator(source_version_id, 0.0, 2.0)
    comparison = _locator(source_version_id, 0.0, 2.0)

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=subject,
        comparison_locator=comparison,
    )
    round_trip = type(result).model_validate_json(result.model_dump_json())

    assert round_trip == result


def test_rhythm_relation_emits_no_semantic_claim_or_statement():
    evidence, source_version_id = _evidence([_window(0.0, 2.0, 1.0)])

    result = compare_rhythm_density_spans(
        evidence,
        subject_locator=_locator(source_version_id, 0.0, 2.0),
        comparison_locator=_locator(source_version_id, 0.0, 2.0),
    )

    payload = result.model_dump(mode="json")
    assert "statement" not in payload
    assert "claim" not in payload
    assert result.provenance["semantic_interpretation_emitted"] is False
