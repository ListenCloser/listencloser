from datetime import UTC, datetime
from uuid import UUID, uuid4

from domain.models import Artifact, ArtifactKind, Version, Work
from domain.relation_query import (
    PerceptualSpanComparisonQuery,
    compare_persisted_perceptual_spans,
)
from domain.work_bundle_repository import WorkBundleSnapshot
from perceptual_evidence import (
    CANONICAL_SAMPLE_RATE,
    PerceptualEvidenceReport,
    PerceptualProvenance,
    PerceptualSeriesEvidence,
)

_HOP_LENGTH = CANONICAL_SAMPLE_RATE // 2
_FRAME_TIMES = [index * 0.5 for index in range(9)]


def _series(
    *,
    source_version_id: UUID,
    feature: str,
    values,
    unit: str,
    normalization: str,
    band_order: list[str] | None = None,
) -> PerceptualSeriesEvidence:
    parameters = {"hop_length": _HOP_LENGTH}
    if band_order is not None:
        parameters["band_order"] = band_order
    return PerceptualSeriesEvidence(
        feature=feature,
        frame_times_seconds=_FRAME_TIMES,
        values=values,
        unit=unit,
        normalization=normalization,
        parameters=parameters,
        source_version_id=source_version_id,
        provenance=PerceptualProvenance(
            engine_version="test",
            parameters={"hop_length": _HOP_LENGTH},
        ),
    )


def _report(source_version_id: UUID) -> PerceptualEvidenceReport:
    low_scalar = [0.1, 0.1, 0.1, 0.1, 0.15, 0.8, 0.8, 0.8, 0.8]
    centroid = [200.0, 200.0, 200.0, 200.0, 300.0, 900.0, 900.0, 900.0, 900.0]
    onset = [0.2, 0.2, 0.2, 0.2, 0.3, 0.9, 0.9, 0.9, 0.9]
    low_bands = [0.70, 0.20, 0.08, 0.02]
    high_bands = [0.20, 0.20, 0.20, 0.40]
    bands = [low_bands, low_bands, low_bands, low_bands, low_bands]
    bands.extend([high_bands, high_bands, high_bands, high_bands])
    band_order = ["low", "low_mid", "mid", "high"]

    return PerceptualEvidenceReport(
        source_version_id=source_version_id,
        duration_seconds=4.0,
        series={
            "rms": _series(
                source_version_id=source_version_id,
                feature="rms",
                values=low_scalar,
                unit="linear_amplitude",
                normalization="none",
            ),
            "spectral_centroid": _series(
                source_version_id=source_version_id,
                feature="spectral_centroid",
                values=centroid,
                unit="hz",
                normalization="none",
            ),
            "relative_band_energy": _series(
                source_version_id=source_version_id,
                feature="relative_band_energy",
                values=bands,
                unit="fraction_of_frame_power",
                normalization="per_frame_total_stft_power",
                band_order=band_order,
            ),
            "onset_strength": _series(
                source_version_id=source_version_id,
                feature="onset_strength",
                values=onset,
                unit="librosa_onset_strength",
                normalization="librosa_default_log_power_mel_flux",
            ),
        },
    )


def _query() -> PerceptualSpanComparisonQuery:
    return PerceptualSpanComparisonQuery(
        subject_start_seconds=2.5,
        subject_end_seconds=3.5,
        comparison_start_seconds=0.5,
        comparison_end_seconds=1.5,
    )


def _snapshot(
    *,
    report: PerceptualEvidenceReport | None = None,
    report_source_version_id: UUID | None = None,
    report_parent_version_id: UUID | None = None,
    report_lineage: list[UUID] | None = None,
    report_created_at: datetime | None = None,
):
    project_id = uuid4()
    work = Work(project_id=project_id, title="Comparison test")
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

    artifacts = [source_artifact]
    versions_by_artifact = {source_artifact.id: [source_version]}
    report_version = None
    if report is not None:
        report_artifact = Artifact(
            work_id=work.id,
            kind=ArtifactKind.analysis_report,
            mime_type="application/json",
        )
        metadata_source_version_id = report_source_version_id or source_version.id
        report_version = Version(
            artifact_id=report_artifact.id,
            parent_version_id=(
                source_version.id if report_parent_version_id is None else report_parent_version_id
            ),
            lineage=([source_version.id] if report_lineage is None else list(report_lineage)),
            storage_key="perceptual-series.json",
            storage_bucket="artifacts",
            created_by="owner",
            label="Perceptual series evidence",
            created_at=report_created_at or datetime(2026, 8, 29, 12, tzinfo=UTC),
            metadata={
                "report_type": "perceptual_series",
                "schema_version": report.schema_version,
                "source_version_id": str(metadata_source_version_id),
                "source_artifact_id": str(source_artifact.id),
                "preprocessing_version": report.preprocessing_version,
                "sample_rate": report.sample_rate,
                "channel_mode": report.channel_mode,
                "features": sorted(report.series),
            },
        )
        artifacts.append(report_artifact)
        versions_by_artifact[report_artifact.id] = [report_version]

    snapshot = WorkBundleSnapshot(
        work=work,
        artifacts=artifacts,
        versions_by_artifact=versions_by_artifact,
        jobs=[],
    )
    return snapshot, source_version, report_version


def test_supported_query_preserves_report_version_spans_and_support_refs():
    provisional_source = uuid4()
    provisional_report = _report(provisional_source)
    snapshot, source_version, report_version = _snapshot(report=provisional_report)
    assert report_version is not None
    report = _report(source_version.id)

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=_query(),
        load_report=lambda version: report.model_dump_json().encode("utf-8"),
    )

    assert result.status == "supported"
    assert result.evidence_report_version_id == report_version.id
    assert result.reasons == []
    assert result.finding is not None
    assert result.finding.subject_locator.start_seconds == 2.5
    assert result.finding.comparison_locator.start_seconds == 0.5
    assert result.finding.available_actions == ["focus", "compare", "evidence"]
    assert {ref.id for ref in result.finding.support_refs} == {
        f"{report_version.id}:rms",
        f"{report_version.id}:spectral_centroid",
        f"{report_version.id}:relative_band_energy",
        f"{report_version.id}:onset_strength",
    }


def test_missing_perceptual_report_is_unavailable_without_calling_loader():
    snapshot, source_version, _ = _snapshot()
    calls = []

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=_query(),
        load_report=lambda version: calls.append(version) or b"{}",
    )

    assert result.status == "unavailable"
    assert result.finding is None
    assert result.evidence_report_version_id is None
    assert calls == []


def test_report_for_a_different_source_version_is_not_reused():
    report = _report(uuid4())
    snapshot, source_version, _ = _snapshot(
        report=report,
        report_source_version_id=uuid4(),
    )

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=_query(),
        load_report=lambda version: report.model_dump_json().encode("utf-8"),
    )

    assert result.status == "unavailable"
    assert result.finding is None


def test_latest_matching_report_with_broken_lineage_fails_closed():
    provisional_report = _report(uuid4())
    snapshot, source_version, valid_report_version = _snapshot(report=provisional_report)
    assert valid_report_version is not None

    report_artifact = next(
        artifact for artifact in snapshot.artifacts if artifact.kind == ArtifactKind.analysis_report
    )
    broken = valid_report_version.model_copy(
        update={
            "id": uuid4(),
            "parent_version_id": uuid4(),
            "lineage": [uuid4()],
            "created_at": datetime(2026, 8, 29, 13, tzinfo=UTC),
        }
    )
    snapshot.versions_by_artifact[report_artifact.id].insert(0, broken)
    calls = []

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=_query(),
        load_report=lambda version: calls.append(version) or b"{}",
    )

    assert result.status == "failed"
    assert result.evidence_report_version_id == broken.id
    assert any("lineage" in reason or "parent" in reason for reason in result.reasons)
    assert calls == []


def test_corrupt_report_payload_is_failed_not_unavailable():
    provisional_report = _report(uuid4())
    snapshot, source_version, report_version = _snapshot(report=provisional_report)
    assert report_version is not None

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=_query(),
        load_report=lambda version: b"not-json",
    )

    assert result.status == "failed"
    assert result.evidence_report_version_id == report_version.id
    assert result.reasons == ["perceptual evidence report could not be validated"]


def test_metadata_payload_mismatch_fails_closed_before_comparison():
    provisional_report = _report(uuid4())
    snapshot, source_version, report_version = _snapshot(report=provisional_report)
    assert report_version is not None
    report = _report(source_version.id)
    report_artifact = next(
        artifact for artifact in snapshot.artifacts if artifact.kind == ArtifactKind.analysis_report
    )
    mismatched = report_version.model_copy(
        update={
            "metadata": {
                **report_version.metadata,
                "preprocessing_version": "different-preprocessing",
            }
        }
    )
    snapshot.versions_by_artifact[report_artifact.id] = [mismatched]

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=_query(),
        load_report=lambda version: report.model_dump_json().encode("utf-8"),
    )

    assert result.status == "failed"
    assert any("preprocessing" in reason for reason in result.reasons)


def test_invalid_user_span_is_withheld_with_relation_reasons():
    provisional_report = _report(uuid4())
    snapshot, source_version, report_version = _snapshot(report=provisional_report)
    assert report_version is not None
    report = _report(source_version.id)
    invalid_query = PerceptualSpanComparisonQuery(
        subject_start_seconds=2.0,
        subject_end_seconds=1.0,
        comparison_start_seconds=0.5,
        comparison_end_seconds=1.5,
    )

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=source_version,
        query=invalid_query,
        load_report=lambda version: report.model_dump_json().encode("utf-8"),
    )

    assert result.status == "withheld"
    assert result.finding is None
    assert result.evidence_report_version_id == report_version.id
    assert any("positive duration" in reason for reason in result.reasons)


def test_source_version_must_belong_to_the_authorized_snapshot():
    snapshot, source_version, _ = _snapshot()
    foreign_source = source_version.model_copy(update={"id": uuid4()})

    result = compare_persisted_perceptual_spans(
        snapshot,
        source_version=foreign_source,
        query=_query(),
        load_report=lambda version: b"{}",
    )

    assert result.status == "failed"
    assert result.finding is None
    assert any("authorized Work snapshot" in reason for reason in result.reasons)
