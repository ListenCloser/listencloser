from uuid import uuid4

import numpy as np

from domain.relation_observations import SecondsSpanLocator, compare_perceptual_spans
from perceptual_evidence import (
    CANONICAL_SAMPLE_RATE,
    PerceptualEvidenceReport,
    build_perceptual_evidence_report,
)


def _sine(frequency: float, seconds: float, amplitude: float = 0.5) -> np.ndarray:
    sample_count = int(seconds * CANONICAL_SAMPLE_RATE)
    time = np.arange(sample_count, dtype=np.float32) / CANONICAL_SAMPLE_RATE
    return (amplitude * np.sin(2.0 * np.pi * frequency * time)).astype(np.float32)


def _report(audio: np.ndarray):
    source_version_id = uuid4()
    report = build_perceptual_evidence_report(
        audio,
        source_version_id=source_version_id,
    )
    return report, source_version_id, uuid4()


def _locator(source_version_id, start: float, end: float):
    return SecondsSpanLocator(
        start_seconds=start,
        end_seconds=end,
        source_artifact_version_id=source_version_id,
        authority="user_selected",
    )


def _measurement(observation, feature: str):
    return next(item for item in observation.measurements if item.feature == feature)


def test_identical_spans_produce_zero_unchanged_measurements():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))
    span = _locator(source_version_id, 0.5, 1.5)

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=span,
        comparison_locator=span,
    )

    assert result.sufficiency.status == "supported"
    assert len(result.measurements) == 4
    for measurement in result.measurements:
        assert measurement.direction == "unchanged"
        delta = np.asarray(measurement.delta, dtype=float)
        assert np.allclose(delta, 0.0)


def test_amplitude_step_produces_expected_rms_direction():
    audio = np.concatenate([_sine(220.0, 2.0, 0.1), _sine(220.0, 2.0, 0.8)])
    report, source_version_id, report_version_id = _report(audio)

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 2.4, 3.4),
        comparison_locator=_locator(source_version_id, 0.4, 1.4),
        features=["rms"],
    )

    measurement = _measurement(result, "rms")
    assert result.sufficiency.status == "supported"
    assert measurement.direction == "higher"
    assert float(measurement.subject_value) > float(measurement.comparison_value) * 7.0


def test_frequency_shift_produces_expected_centroid_direction():
    audio = np.concatenate([_sine(220.0, 2.0), _sine(4_000.0, 2.0)])
    report, source_version_id, report_version_id = _report(audio)

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 2.4, 3.4),
        comparison_locator=_locator(source_version_id, 0.4, 1.4),
        features=["spectral_centroid"],
    )

    measurement = _measurement(result, "spectral_centroid")
    assert result.sufficiency.status == "supported"
    assert measurement.direction == "higher"
    assert float(measurement.subject_value) > float(measurement.comparison_value) * 5.0


def test_dense_transients_produce_higher_onset_strength():
    sample_count = int(4.0 * CANONICAL_SAMPLE_RATE)
    audio = np.zeros(sample_count, dtype=np.float32)
    for second in (0.5, 1.0, 1.5):
        audio[int(second * CANONICAL_SAMPLE_RATE)] = 1.0
    for second in np.arange(2.2, 3.8, 0.1):
        audio[int(second * CANONICAL_SAMPLE_RATE)] = 1.0
    report, source_version_id, report_version_id = _report(audio)

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 2.2, 3.8),
        comparison_locator=_locator(source_version_id, 0.2, 1.8),
        features=["onset_strength"],
    )

    measurement = _measurement(result, "onset_strength")
    assert result.sufficiency.status == "supported"
    assert measurement.direction == "higher"


def test_band_shift_stays_a_mixed_numeric_vector_relation():
    audio = np.concatenate([_sine(100.0, 2.0), _sine(6_000.0, 2.0)])
    report, source_version_id, report_version_id = _report(audio)

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 2.4, 3.4),
        comparison_locator=_locator(source_version_id, 0.4, 1.4),
        features=["relative_band_energy"],
    )

    measurement = _measurement(result, "relative_band_energy")
    assert result.sufficiency.status == "supported"
    assert measurement.components == ["low", "low_mid", "mid", "high"]
    assert measurement.direction == "mixed"
    assert isinstance(measurement.delta, list)
    assert len(measurement.delta) == 4


def test_incompatible_preprocessing_metadata_withholds():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))
    incompatible = report.model_copy(update={"preprocessing_version": "different_contract"})

    result = compare_perceptual_spans(
        incompatible,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 0.4, 1.4),
        comparison_locator=_locator(source_version_id, 2.4, 3.4),
        features=["rms"],
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("preprocessing version" in reason for reason in result.sufficiency.reasons)


def test_mismatched_source_lineage_withholds_without_clamping_or_fallback():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(uuid4(), 0.4, 1.4),
        comparison_locator=_locator(source_version_id, 2.4, 3.4),
        features=["rms"],
    )

    assert result.sufficiency.status == "withhold"
    assert result.measurements == []
    assert any("source version" in reason for reason in result.sufficiency.reasons)


def test_invalid_or_out_of_range_locator_withholds():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 1.5, 1.0),
        comparison_locator=_locator(source_version_id, 3.5, 4.5),
        features=["rms"],
    )

    assert result.sufficiency.status == "withhold"
    assert any("positive duration" in reason for reason in result.sufficiency.reasons)
    assert any("source duration" in reason for reason in result.sufficiency.reasons)


def test_partial_evidence_coverage_withholds_explicitly():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))
    rms = report.series["rms"]
    keep = [time <= 1.0 for time in rms.frame_times_seconds]
    truncated = rms.model_copy(
        update={
            "frame_times_seconds": [
                time
                for time, selected in zip(rms.frame_times_seconds, keep, strict=True)
                if selected
            ],
            "values": [value for value, selected in zip(rms.values, keep, strict=True) if selected],
        }
    )
    series = dict(report.series)
    series["rms"] = truncated
    incomplete = report.model_copy(update={"series": series})

    result = compare_perceptual_spans(
        incomplete,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 2.0, 3.0),
        comparison_locator=_locator(source_version_id, 0.2, 0.8),
        features=["rms"],
    )

    assert result.sufficiency.status == "withhold"
    assert any("cover" in reason for reason in result.sufficiency.reasons)


def test_near_zero_denominator_omits_relative_delta_instead_of_exploding():
    audio = np.zeros(int(4.0 * CANONICAL_SAMPLE_RATE), dtype=np.float32)
    audio[int(2.5 * CANONICAL_SAMPLE_RATE)] = 1.0
    report, source_version_id, report_version_id = _report(audio)

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 2.2, 2.8),
        comparison_locator=_locator(source_version_id, 0.2, 0.8),
        features=["onset_strength"],
    )

    measurement = _measurement(result, "onset_strength")
    assert result.sufficiency.status == "supported"
    assert measurement.relative_delta is None
    assert np.isfinite(float(measurement.delta))


def test_support_refs_cover_every_series_used_by_the_relation():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))
    features = ["rms", "spectral_centroid", "onset_strength"]

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 0.4, 1.4),
        comparison_locator=_locator(source_version_id, 2.4, 3.4),
        features=features,
    )

    assert result.sufficiency.status == "supported"
    assert {ref.id for ref in result.support_refs} == {
        f"{report_version_id}:{feature}" for feature in features
    }


def test_relation_serialization_preserves_locators_measurements_and_provenance():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))
    subject = _locator(source_version_id, 0.4, 1.4)
    comparison = _locator(source_version_id, 2.4, 3.4)

    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=subject,
        comparison_locator=comparison,
        features=["rms"],
    )
    round_trip = type(result).model_validate_json(result.model_dump_json())

    assert round_trip.subject_locator == subject
    assert round_trip.comparison_locator == comparison
    assert round_trip.measurements == result.measurements
    assert round_trip.sufficiency == result.sufficiency
    assert round_trip.provenance == result.provenance


def test_relation_layer_emits_no_natural_language_semantic_interpretation():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))
    result = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 0.4, 1.4),
        comparison_locator=_locator(source_version_id, 2.4, 3.4),
        features=["rms", "spectral_centroid"],
    )

    payload = result.model_dump(mode="json")
    assert "statement" not in payload
    assert "claim" not in payload
    assert result.provenance["semantic_interpretation_emitted"] is False


def test_boundary_perturbation_changes_measurement_across_known_transition():
    audio = np.concatenate([_sine(100.0, 2.0), _sine(6_000.0, 2.0)])
    report, source_version_id, report_version_id = _report(audio)
    comparison = _locator(source_version_id, 0.4, 1.4)

    before = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 1.0, 1.8),
        comparison_locator=comparison,
        features=["relative_band_energy"],
    )
    crossing = compare_perceptual_spans(
        report,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 1.8, 2.6),
        comparison_locator=comparison,
        features=["relative_band_energy"],
    )

    before_delta = np.asarray(_measurement(before, "relative_band_energy").delta)
    crossing_delta = np.asarray(_measurement(crossing, "relative_band_energy").delta)
    assert before.sufficiency.status == "supported"
    assert crossing.sufficiency.status == "supported"
    assert not np.allclose(before_delta, crossing_delta)


def test_missing_promoted_series_withholds_instead_of_using_weaker_evidence():
    report, source_version_id, report_version_id = _report(_sine(440.0, 4.0))
    series = dict(report.series)
    series.pop("rms")
    incomplete = PerceptualEvidenceReport(
        source_version_id=report.source_version_id,
        duration_seconds=report.duration_seconds,
        series=series,
    )

    result = compare_perceptual_spans(
        incomplete,
        evidence_report_version_id=report_version_id,
        subject_locator=_locator(source_version_id, 0.4, 1.4),
        comparison_locator=_locator(source_version_id, 2.4, 3.4),
        features=["rms"],
    )

    assert result.sufficiency.status == "withhold"
    assert result.support_refs == []
    assert any("missing" in reason for reason in result.sufficiency.reasons)
