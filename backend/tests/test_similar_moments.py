from uuid import UUID, uuid4

import pytest

from domain.perceptual_report import (
    CANONICAL_SAMPLE_RATE,
    PerceptualEvidenceReport,
    PerceptualProvenance,
    PerceptualSeriesEvidence,
)
from domain.similar_moments import RECURRENCE_DIMENSIONS, find_similar_moments

_HOP_LENGTH = CANONICAL_SAMPLE_RATE // 2
_FRAME_TIMES = [index * 0.5 for index in range(16)]


def _series(
    *,
    source_version_id: UUID,
    feature: str,
    values,
    band_order: list[str] | None = None,
) -> PerceptualSeriesEvidence:
    parameters = {"hop_length": _HOP_LENGTH}
    if band_order is not None:
        parameters["band_order"] = band_order
    return PerceptualSeriesEvidence(
        feature=feature,
        frame_times_seconds=_FRAME_TIMES,
        values=values,
        unit=None,
        normalization="test",
        parameters=parameters,
        source_version_id=source_version_id,
        provenance=PerceptualProvenance(
            engine_version="test",
            parameters={"hop_length": _HOP_LENGTH},
        ),
    )


def _report(source_version_id: UUID) -> PerceptualEvidenceReport:
    onset = [
        0.1,
        0.7,
        0.2,
        0.9,
        0.4,
        0.5,
        0.3,
        0.6,
        0.1,
        0.7,
        0.2,
        0.9,
        0.8,
        0.3,
        0.6,
        0.2,
    ]
    centroid = [
        200.0,
        500.0,
        300.0,
        700.0,
        420.0,
        460.0,
        410.0,
        480.0,
        200.0,
        500.0,
        300.0,
        700.0,
        650.0,
        320.0,
        510.0,
        280.0,
    ]
    query_bands = [
        [0.55, 0.25, 0.15, 0.05],
        [0.30, 0.30, 0.25, 0.15],
        [0.45, 0.20, 0.25, 0.10],
        [0.20, 0.25, 0.30, 0.25],
    ]
    middle_bands = [
        [0.25, 0.25, 0.25, 0.25],
        [0.28, 0.27, 0.24, 0.21],
        [0.26, 0.24, 0.28, 0.22],
        [0.29, 0.21, 0.26, 0.24],
    ]
    tail_bands = [
        [0.15, 0.20, 0.30, 0.35],
        [0.35, 0.25, 0.20, 0.20],
        [0.20, 0.35, 0.30, 0.15],
        [0.30, 0.20, 0.15, 0.35],
    ]
    bands = [*query_bands, *middle_bands, *query_bands, *tail_bands]

    return PerceptualEvidenceReport(
        source_version_id=source_version_id,
        duration_seconds=8.0,
        series={
            "spectral_centroid": _series(
                source_version_id=source_version_id,
                feature="spectral_centroid",
                values=centroid,
            ),
            "relative_band_energy": _series(
                source_version_id=source_version_id,
                feature="relative_band_energy",
                values=bands,
                band_order=["low", "low_mid", "mid", "high"],
            ),
            "onset_strength": _series(
                source_version_id=source_version_id,
                feature="onset_strength",
                values=onset,
            ),
        },
    )


def test_repeated_descriptor_shape_is_ranked_first_with_exact_lineage():
    source_version_id = uuid4()
    evidence_report_version_id = uuid4()

    result = find_similar_moments(
        _report(source_version_id),
        evidence_report_version_id=evidence_report_version_id,
        query_start_seconds=0.0,
        query_end_seconds=2.0,
        max_matches=3,
    )

    assert result.source_version_id == source_version_id
    assert result.evidence_report_version_id == evidence_report_version_id
    assert result.query_start_seconds == 0.0
    assert result.query_end_seconds == 2.0
    assert result.method.dimensions == list(RECURRENCE_DIMENSIONS)
    assert (
        result.method.score_semantics
        == "lower_is_closer_under_this_method_not_confidence"
    )
    assert result.matches
    assert result.matches[0].start_seconds == 4.0
    assert result.matches[0].end_seconds == 6.0
    assert result.matches[0].distance == pytest.approx(0.0, abs=1e-12)
    assert set(result.matches[0].component_distances) == set(RECURRENCE_DIMENSIONS)


def test_query_and_returned_candidates_are_explicitly_non_overlapping():
    result = find_similar_moments(
        _report(uuid4()),
        evidence_report_version_id=uuid4(),
        query_start_seconds=0.0,
        query_end_seconds=2.0,
        max_matches=3,
    )

    for match in result.matches:
        assert match.start_seconds >= 2.0 or match.end_seconds <= 0.0

    for index, left in enumerate(result.matches):
        for right in result.matches[index + 1 :]:
            assert (
                left.end_seconds <= right.start_seconds
                or right.end_seconds <= left.start_seconds
            )


def test_distance_is_not_exposed_as_confidence():
    result = find_similar_moments(
        _report(uuid4()),
        evidence_report_version_id=uuid4(),
        query_start_seconds=0.0,
        query_end_seconds=2.0,
    )
    payload = result.model_dump(mode="json")

    assert "confidence" not in payload
    assert "confidence" not in payload["method"]
    assert all("confidence" not in match for match in payload["matches"])
    assert payload["method"]["semantic_claims"] == "none"


def test_no_valid_non_overlapping_window_returns_empty_proposals_without_fake_threshold():
    source_version_id = uuid4()
    report = _report(source_version_id).model_copy(
        update={
            "duration_seconds": 4.0,
            "series": {
                feature: series.model_copy(
                    update={
                        "frame_times_seconds": series.frame_times_seconds[:8],
                        "values": series.values[:8],
                    }
                )
                for feature, series in _report(source_version_id).series.items()
            },
        }
    )

    result = find_similar_moments(
        report,
        evidence_report_version_id=uuid4(),
        query_start_seconds=0.0,
        query_end_seconds=3.5,
    )

    assert result.matches == []
    assert result.no_match_reason == "no_valid_non_overlapping_candidate_windows"
    assert "max_distance" not in result.method.parameters
