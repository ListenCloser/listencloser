from datetime import UTC, datetime
from uuid import UUID, uuid4

from domain.models import Artifact, ArtifactKind, Version, Work
from domain.perceptual_report import (
    CANONICAL_SAMPLE_RATE,
    PerceptualEvidenceReport,
    PerceptualProvenance,
    PerceptualSeriesEvidence,
)
from domain.similar_moments_query import SimilarMomentsQuery, find_persisted_similar_moments
from domain.work_bundle_repository import WorkBundleSnapshot

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
    pattern = [0.1, 0.8, 0.2, 0.7]
    onset = [*pattern, 0.4, 0.5, 0.45, 0.55, *pattern, 0.9, 0.3, 0.6, 0.2]
    centroid_pattern = [200.0, 700.0, 300.0, 600.0]
    centroid = [
        *centroid_pattern,
        420.0,
        460.0,
        430.0,
        470.0,
        *centroid_pattern,
        760.0,
        340.0,
        540.0,
        280.0,
    ]
    band_pattern = [
        [0.55, 0.25, 0.15, 0.05],
        [0.25, 0.30, 0.25, 0.20],
        [0.45, 0.20, 0.25, 0.10],
        [0.20, 0.25, 0.30, 0.25],
    ]
    neutral = [
        [0.30, 0.25, 0.25, 0.20],
        [0.28, 0.27, 0.24, 0.21],
        [0.31, 0.24, 0.26, 0.19],
        [0.29, 0.26, 0.23, 0.22],
    ]
    tail = [
        [0.20, 0.20, 0.25, 0.35],
        [0.35, 0.25, 0.20, 0.20],
        [0.20, 0.35, 0.30, 0.15],
        [0.30, 0.20, 0.15, 0.35],
    ]

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
                values=[*band_pattern, *neutral, *band_pattern, *tail],
                band_order=["low", "low_mid", "mid", "high"],
            ),
            "onset_strength": _series(
                source_version_id=source_version_id,
                feature="onset_strength",
                values=onset,
            ),
        },
    )


def _snapshot(*, include_report: bool = True):
    work = Work(project_id=uuid4(), title="Similar moments query")
    source_artifact = Artifact(
        work_id=work.id,
        kind=ArtifactKind.audio_original,
        mime_type="audio/wav",
    )
    source_version = Version(
        artifact_id=source_artifact.id,
        storage_key="source.wav",
        storage_bucket="artifacts",
        created_by="owner",
        label="source.wav",
    )
    report = _report(source_version.id)
    artifacts = [source_artifact]
    versions_by_artifact = {source_artifact.id: [source_version]}
    report_version = None

    if include_report:
        report_artifact = Artifact(
            work_id=work.id,
            kind=ArtifactKind.analysis_report,
            mime_type="application/json",
        )
        report_version = Version(
            artifact_id=report_artifact.id,
            parent_version_id=source_version.id,
            lineage=[source_version.id],
            storage_key="perceptual-series.json",
            storage_bucket="artifacts",
            created_by="owner",
            label="Perceptual series evidence",
            created_at=datetime(2026, 9, 4, 12, tzinfo=UTC),
            metadata={
                "report_type": "perceptual_series",
                "schema_version": report.schema_version,
                "source_version_id": str(source_version.id),
                "source_artifact_id": str(source_artifact.id),
                "preprocessing_version": report.preprocessing_version,
                "sample_rate": report.sample_rate,
                "channel_mode": report.channel_mode,
                "features": sorted(report.series),
            },
        )
        artifacts.append(report_artifact)
        versions_by_artifact[report_artifact.id] = [report_version]

    return (
        WorkBundleSnapshot(
            work=work,
            artifacts=artifacts,
            versions_by_artifact=versions_by_artifact,
            jobs=[],
        ),
        source_version,
        report,
        report_version,
    )


def test_persisted_query_preserves_source_report_and_method_provenance():
    snapshot, source_version, report, report_version = _snapshot()
    assert report_version is not None

    result = find_persisted_similar_moments(
        snapshot,
        source_version=source_version,
        query=SimilarMomentsQuery(
            query_start_seconds=0.0,
            query_end_seconds=2.0,
            max_matches=3,
        ),
        load_report=lambda version: report.model_dump_json().encode("utf-8"),
    )

    assert result.status == "supported"
    assert result.evidence_report_version_id == report_version.id
    assert result.reasons == []
    assert result.observation is not None
    assert result.observation.source_version_id == source_version.id
    assert result.observation.evidence_report_version_id == report_version.id
    assert result.observation.method.id == "perceptual_descriptor_shape"
    assert result.observation.method.semantic_claims == "none"
    assert result.observation.matches[0].start_seconds == 4.0


def test_missing_persisted_report_is_unavailable_without_loading_bytes():
    snapshot, source_version, _, _ = _snapshot(include_report=False)
    calls = []

    result = find_persisted_similar_moments(
        snapshot,
        source_version=source_version,
        query=SimilarMomentsQuery(query_start_seconds=0.0, query_end_seconds=2.0),
        load_report=lambda version: calls.append(version) or b"{}",
    )

    assert result.status == "unavailable"
    assert result.observation is None
    assert result.evidence_report_version_id is None
    assert calls == []


def test_invalid_selected_span_is_withheld_after_exact_report_validation():
    snapshot, source_version, report, report_version = _snapshot()
    assert report_version is not None

    result = find_persisted_similar_moments(
        snapshot,
        source_version=source_version,
        query=SimilarMomentsQuery(query_start_seconds=3.0, query_end_seconds=2.0),
        load_report=lambda version: report.model_dump_json().encode("utf-8"),
    )

    assert result.status == "withheld"
    assert result.observation is None
    assert result.evidence_report_version_id == report_version.id
    assert any("positive duration" in reason for reason in result.reasons)
