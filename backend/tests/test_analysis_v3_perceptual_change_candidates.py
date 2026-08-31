from __future__ import annotations

from uuid import UUID

from backend.evaluation.analysis_v3.perceptual.change_candidates import (
    discover_measured_change_candidates,
)
from domain.perceptual_report import (
    PerceptualEvidenceReport,
    PerceptualProvenance,
    PerceptualSeriesEvidence,
)

SOURCE_VERSION_ID = UUID("11111111-1111-1111-1111-111111111111")
REPORT_VERSION_ID = UUID("22222222-2222-2222-2222-222222222222")
SAMPLE_RATE = 22_050
HOP_LENGTH = SAMPLE_RATE


def _series(
    feature: str,
    times: list[float],
    values: list[float] | list[list[float]],
    *,
    unit: str,
    normalization: str,
    band_order: list[str] | None = None,
) -> PerceptualSeriesEvidence:
    parameters: dict[str, object] = {"hop_length": HOP_LENGTH}
    if band_order is not None:
        parameters["band_order"] = band_order
    return PerceptualSeriesEvidence(
        feature=feature,
        frame_times_seconds=times,
        values=values,
        unit=unit,
        normalization=normalization,
        parameters=parameters,
        source_version_id=SOURCE_VERSION_ID,
        provenance=PerceptualProvenance(
            engine_version="test",
            parameters={"hop_length": HOP_LENGTH, **parameters},
        ),
    )


def _report(
    *,
    times: list[float],
    onset: list[float],
    centroid: list[float],
    bands: list[list[float]],
    rms: list[float] | None = None,
) -> PerceptualEvidenceReport:
    series: dict[str, PerceptualSeriesEvidence] = {
        "onset_strength": _series(
            "onset_strength",
            times,
            onset,
            unit="librosa_onset_strength",
            normalization="librosa_default_log_power_mel_flux",
        ),
        "spectral_centroid": _series(
            "spectral_centroid",
            times,
            centroid,
            unit="hz",
            normalization="none",
        ),
        "relative_band_energy": _series(
            "relative_band_energy",
            times,
            bands,
            unit="fraction_of_frame_power",
            normalization="per_frame_total_stft_power",
            band_order=["low", "low_mid", "mid", "high"],
        ),
    }
    if rms is not None:
        series["rms"] = _series(
            "rms",
            times,
            rms,
            unit="linear_amplitude",
            normalization="none",
        )
    return PerceptualEvidenceReport(
        source_version_id=SOURCE_VERSION_ID,
        duration_seconds=times[-1] + 1.0,
        series=series,
    )


def test_change_control_localizes_known_multivariate_step() -> None:
    times = [float(value) for value in range(41)]
    before_band = [0.8, 0.1, 0.05, 0.05]
    after_band = [0.1, 0.2, 0.3, 0.4]
    report = _report(
        times=times,
        onset=[0.2] * 20 + [2.0] * 21,
        centroid=[300.0] * 20 + [2_000.0] * 21,
        bands=[before_band] * 20 + [after_band] * 21,
        rms=[0.1] * 20 + [0.9] * 21,
    )

    result = discover_measured_change_candidates(
        report,
        evidence_report_version_id=REPORT_VERSION_ID,
        window_seconds=4.0,
        min_separation_seconds=4.0,
        threshold_mad=1.0,
    )

    assert result.status == "supported"
    assert result.candidates
    best = result.candidates[0]
    assert best.boundary_seconds == 20.0
    assert set(best.component_scores) == {
        "onset_strength",
        "spectral_centroid",
        "low",
        "low_mid",
        "mid",
        "high",
    }
    assert {measurement.feature for measurement in best.observation.measurements} == {
        "onset_strength",
        "spectral_centroid",
        "relative_band_energy",
    }
    assert all(ref.id.split(":")[-1] != "rms" for ref in best.observation.support_refs)


def test_change_control_returns_no_candidate_for_stationary_evidence() -> None:
    times = [float(value) for value in range(31)]
    report = _report(
        times=times,
        onset=[0.5] * len(times),
        centroid=[500.0] * len(times),
        bands=[[0.25, 0.25, 0.25, 0.25]] * len(times),
        rms=[0.3] * len(times),
    )

    result = discover_measured_change_candidates(
        report,
        evidence_report_version_id=REPORT_VERSION_ID,
        window_seconds=4.0,
        threshold_mad=1.0,
    )

    assert result.status == "supported"
    assert result.candidates == []


def test_change_control_excludes_rms_from_candidate_score() -> None:
    times = [float(value) for value in range(41)]
    report = _report(
        times=times,
        onset=[0.5] * len(times),
        centroid=[500.0] * len(times),
        bands=[[0.25, 0.25, 0.25, 0.25]] * len(times),
        rms=[0.1] * 20 + [0.9] * 21,
    )

    result = discover_measured_change_candidates(
        report,
        evidence_report_version_id=REPORT_VERSION_ID,
        window_seconds=4.0,
        threshold_mad=1.0,
    )

    assert result.status == "supported"
    assert result.candidates == []


def test_change_control_withholds_on_misaligned_promoted_series() -> None:
    times = [float(value) for value in range(21)]
    report = _report(
        times=times,
        onset=[0.5] * len(times),
        centroid=[500.0] * len(times),
        bands=[[0.25, 0.25, 0.25, 0.25]] * len(times),
    )
    centroid = report.series["spectral_centroid"].model_copy(
        update={"frame_times_seconds": [*times[:-1], times[-1] + 0.25]}
    )
    malformed = report.model_copy(update={"series": {**report.series, "spectral_centroid": centroid}})

    result = discover_measured_change_candidates(
        malformed,
        evidence_report_version_id=REPORT_VERSION_ID,
        window_seconds=4.0,
    )

    assert result.status == "withheld"
    assert any("exact promoted frame grid" in reason for reason in result.reasons)
