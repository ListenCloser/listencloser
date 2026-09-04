from uuid import uuid4

import numpy as np

from domain.measured_changes import discover_measured_changes
from domain.perceptual_report import (
    PerceptualEvidenceReport,
    PerceptualProvenance,
    PerceptualSeriesEvidence,
)
from perceptual_evidence import CANONICAL_SAMPLE_RATE, build_perceptual_evidence_report

_BAND_ORDER = ["low", "low_mid", "mid", "high"]
_CONTROL_FRAME_STEP_SECONDS = 0.5
_CONTROL_FRAME_TIMES = [
    index * _CONTROL_FRAME_STEP_SECONDS for index in range(29)
]
_CONTROL_HOP_LENGTH = int(CANONICAL_SAMPLE_RATE * _CONTROL_FRAME_STEP_SECONDS)


def _tone(frequency: float, seconds: float, amplitude: float = 0.35) -> np.ndarray:
    count = int(seconds * CANONICAL_SAMPLE_RATE)
    time = np.arange(count, dtype=np.float32) / CANONICAL_SAMPLE_RATE
    return (amplitude * np.sin(2.0 * np.pi * frequency * time)).astype(np.float32)


def _report(audio: np.ndarray):
    return build_perceptual_evidence_report(audio, source_version_id=uuid4())


def _controlled_series(
    *,
    source_version_id,
    feature: str,
    values,
    unit: str,
    normalization: str,
    band_order: list[str] | None = None,
) -> PerceptualSeriesEvidence:
    parameters = {"hop_length": _CONTROL_HOP_LENGTH}
    if band_order is not None:
        parameters["band_order"] = band_order
    return PerceptualSeriesEvidence(
        feature=feature,
        frame_times_seconds=_CONTROL_FRAME_TIMES,
        values=values,
        unit=unit,
        normalization=normalization,
        parameters=parameters,
        source_version_id=source_version_id,
        provenance=PerceptualProvenance(
            engine_version="controlled-test",
            parameters={"hop_length": _CONTROL_HOP_LENGTH},
        ),
    )


def _controlled_report(
    *,
    onset_step: bool = False,
    band_step: bool = False,
) -> PerceptualEvidenceReport:
    source_version_id = uuid4()
    midpoint = 7.0
    onset_values = [
        0.0 if not onset_step or time < midpoint else 10.0
        for time in _CONTROL_FRAME_TIMES
    ]
    centroid_values = [500.0 for _ in _CONTROL_FRAME_TIMES]
    low_bands = [0.70, 0.20, 0.08, 0.02]
    high_bands = [0.10, 0.10, 0.10, 0.70]
    band_values = [
        list(high_bands if band_step and time >= midpoint else low_bands)
        for time in _CONTROL_FRAME_TIMES
    ]
    return PerceptualEvidenceReport(
        source_version_id=source_version_id,
        duration_seconds=_CONTROL_FRAME_TIMES[-1],
        series={
            "onset_strength": _controlled_series(
                source_version_id=source_version_id,
                feature="onset_strength",
                values=onset_values,
                unit="librosa_onset_strength",
                normalization="librosa_default_log_power_mel_flux",
            ),
            "spectral_centroid": _controlled_series(
                source_version_id=source_version_id,
                feature="spectral_centroid",
                values=centroid_values,
                unit="hz",
                normalization="none",
            ),
            "relative_band_energy": _controlled_series(
                source_version_id=source_version_id,
                feature="relative_band_energy",
                values=band_values,
                unit="fraction_of_frame_power",
                normalization="per_frame_total_stft_power",
                band_order=_BAND_ORDER,
            ),
        },
    )


def test_discovers_bounded_multi_feature_change_with_literal_evidence():
    # One unambiguous measured change: low steady tone -> high steady tone.
    # This moves spectral centroid and the relative-band distribution without
    # requiring any semantic interpretation of what the change "means".
    transition_seconds = 7.0
    window_seconds = 3.0
    report = _report(
        np.concatenate(
            [_tone(180.0, transition_seconds), _tone(4_500.0, transition_seconds)]
        )
    )
    report_version_id = uuid4()

    result = discover_measured_changes(
        report,
        evidence_report_version_id=report_version_id,
        window_seconds=window_seconds,
        min_separation_seconds=4.0,
        feature_change_floor=0.35,
    )

    assert result.status == "supported"
    assert 1 <= len(result.candidates) <= 5
    candidate = min(
        result.candidates,
        key=lambda item: abs(item.boundary_seconds - transition_seconds),
    )

    # boundary_seconds is the anchor separating adjacent before/after median
    # windows, not an estimator of the physical transition instant. For an
    # ideal step, both medians can remain maximally different while the anchor
    # is within half a comparison window of the step. Allow one evidence hop
    # for the discretized frame grid, and no more.
    onset_times = report.series["onset_strength"].frame_times_seconds
    evidence_hop_seconds = float(np.median(np.diff(onset_times)))
    localization_tolerance_seconds = window_seconds / 2.0 + evidence_hop_seconds
    assert (
        abs(candidate.boundary_seconds - transition_seconds)
        <= localization_tolerance_seconds
    )
    assert candidate.before_span_seconds[1] == candidate.boundary_seconds
    assert candidate.after_span_seconds[0] == candidate.boundary_seconds

    assert candidate.changed_feature_count >= 2
    assert set(candidate.normalized_feature_changes) == {
        "onset_strength",
        "spectral_centroid",
        "relative_band_energy",
    }
    assert (
        candidate.finding.subject_locator.source_artifact_version_id
        == report.source_version_id
    )
    assert (
        candidate.finding.comparison_locator.source_artifact_version_id
        == report.source_version_id
    )
    assert candidate.finding.support_refs
    assert all(
        ref.evidence_report_version_id == report_version_id
        for ref in candidate.finding.support_refs
    )
    assert {measurement.feature for measurement in candidate.finding.measurements} == {
        "onset_strength",
        "spectral_centroid",
        "relative_band_energy",
    }


def test_single_declared_feature_cannot_qualify_as_multiple_features():
    # Build the evidence grid directly so only onset strength changes. The two
    # other declared feature groups are mathematically constant rather than
    # merely derived from a nominally steady waveform.
    report = _controlled_report(onset_step=True)

    result = discover_measured_changes(
        report,
        evidence_report_version_id=uuid4(),
        window_seconds=3.0,
        min_separation_seconds=4.0,
        feature_change_floor=0.35,
    )

    assert result.status == "supported"
    assert result.candidates == []


def test_multicomponent_band_change_still_counts_as_one_feature_group():
    # All four relative-band components redistribute strongly, but onset
    # strength and spectral centroid remain exactly constant. Four component
    # deltas must therefore still count as one declared feature group.
    report = _controlled_report(band_step=True)

    result = discover_measured_changes(
        report,
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
