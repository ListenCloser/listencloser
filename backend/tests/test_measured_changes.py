from uuid import uuid4

import numpy as np

from domain.measured_changes import discover_measured_changes
from perceptual_evidence import CANONICAL_SAMPLE_RATE, build_perceptual_evidence_report


def _tone(frequency: float, seconds: float, amplitude: float = 0.35) -> np.ndarray:
    count = int(seconds * CANONICAL_SAMPLE_RATE)
    time = np.arange(count, dtype=np.float32) / CANONICAL_SAMPLE_RATE
    return (amplitude * np.sin(2.0 * np.pi * frequency * time)).astype(np.float32)


def _report(audio: np.ndarray):
    return build_perceptual_evidence_report(audio, source_version_id=uuid4())


def test_discovers_bounded_multi_feature_change_with_literal_evidence():
    # One unambiguous measured change: low steady tone -> high steady tone.
    # This moves spectral centroid and the relative-band distribution without
    # requiring any semantic interpretation of what the change "means".
    report = _report(np.concatenate([_tone(180.0, 7.0), _tone(4_500.0, 7.0)]))
    report_version_id = uuid4()

    result = discover_measured_changes(
        report,
        evidence_report_version_id=report_version_id,
        window_seconds=3.0,
        min_separation_seconds=4.0,
        feature_change_floor=0.35,
    )

    assert result.status == "supported"
    assert 1 <= len(result.candidates) <= 5
    candidate = min(result.candidates, key=lambda item: abs(item.boundary_seconds - 7.0))
    assert abs(candidate.boundary_seconds - 7.0) < 0.5
    assert candidate.changed_feature_count >= 2
    assert set(candidate.normalized_feature_changes) == {
        "onset_strength",
        "spectral_centroid",
        "relative_band_energy",
    }
    assert candidate.finding.source_artifact_version_id == report.source_version_id
    assert candidate.finding.evidence_refs
    assert all(
        ref.evidence_report_version_id == report_version_id
        for ref in candidate.finding.evidence_refs
    )
    assert {measurement.feature for measurement in candidate.finding.measurements} == {
        "onset_strength",
        "spectral_centroid",
        "relative_band_energy",
    }


def test_single_declared_feature_cannot_qualify_as_multiple_features():
    # Preserve the exact promoted grid but edit only the onset-strength series.
    # Multiple scalar excursions inside one feature are still one feature.
    report = _report(_tone(440.0, 14.0))
    onset = report.series["onset_strength"]
    midpoint = len(onset.values) // 2
    changed_onset = onset.model_copy(
        update={"values": [0.0] * midpoint + [10.0] * (len(onset.values) - midpoint)}
    )
    single_feature_report = report.model_copy(
        update={"series": {**report.series, "onset_strength": changed_onset}}
    )

    result = discover_measured_changes(
        single_feature_report,
        evidence_report_version_id=uuid4(),
        window_seconds=3.0,
        min_separation_seconds=4.0,
        feature_change_floor=0.35,
    )

    assert result.status == "supported"
    assert result.candidates == []


def test_misaligned_promoted_evidence_fails_closed():
    report = _report(_tone(440.0, 12.0))
    centroid = report.series["spectral_centroid"]
    shifted = centroid.model_copy(
        update={
            "frame_times_seconds": [
                value + 0.01 for value in centroid.frame_times_seconds
            ]
        }
    )
    incompatible = report.model_copy(
        update={"series": {**report.series, "spectral_centroid": shifted}}
    )

    result = discover_measured_changes(
        incompatible,
        evidence_report_version_id=uuid4(),
    )

    assert result.status == "withheld"
    assert result.candidates == []
    assert any("exact promoted frame grid" in reason for reason in result.reasons)


def test_candidate_top_set_is_hard_bounded():
    parts = []
    for index in range(12):
        parts.append(_tone(180.0 if index % 2 == 0 else 4_500.0, 4.0))
    report = _report(np.concatenate(parts))

    result = discover_measured_changes(
        report,
        evidence_report_version_id=uuid4(),
        window_seconds=2.0,
        min_separation_seconds=3.0,
        feature_change_floor=0.25,
        max_candidates=3,
    )

    assert result.status == "supported"
    assert len(result.candidates) <= 3
    assert [candidate.rank for candidate in result.candidates] == list(
        range(1, len(result.candidates) + 1)
    )
