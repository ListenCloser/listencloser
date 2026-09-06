"""Focused persisted-contract tests for bounded AnalysisGNN score analysis."""

from uuid import uuid4

import pytest

from domain.analysisgnn_score_report import build_analysisgnn_score_report
from engines.base import EngineProvenance
from engines.symbolic.analysisgnn import AnalysisGNNScoreEvidence, AnalysisGNNScoreObservation


def _provenance() -> EngineProvenance:
    return EngineProvenance(
        engine="analysisgnn",
        library_version="1.0.0",
        model="local-pinned-checkpoint",
        parameters={
            "checkpoint_sha256": "a" * 64,
            "model_license": "UNVERIFIED",
            "runtime_classification": "INTERNAL_ONLY",
            "commercial_default_eligible": False,
        },
    )


def test_analysisgnn_score_report_preserves_exact_score_lineage_and_labels() -> None:
    work_id = uuid4()
    artifact_id = uuid4()
    version_id = uuid4()
    evidence = AnalysisGNNScoreEvidence(
        observations=(
            AnalysisGNNScoreObservation(
                onset_beat=12.5,
                measure_number=7,
                labels=(
                    ("cadence", "PAC"),
                    ("localkey", "C"),
                    ("romanNumeral", "V7"),
                ),
            ),
        ),
        tasks=("cadence", "localkey", "romanNumeral"),
        provenance=_provenance(),
    )

    report = build_analysisgnn_score_report(
        evidence,
        work_id=work_id,
        source_score_artifact_id=artifact_id,
        source_score_version_id=version_id,
    )

    assert report.work_id == work_id
    assert report.source_score_artifact_id == artifact_id
    assert report.source_score_version_id == version_id
    assert report.experimental is True
    assert report.tasks == ["cadence", "localkey", "romanNumeral"]
    assert report.observations[0].onset_beat == 12.5
    assert report.observations[0].measure_number == 7
    assert [(label.task, label.value) for label in report.observations[0].labels] == [
        ("cadence", "PAC"),
        ("localkey", "C"),
        ("romanNumeral", "V7"),
    ]
    assert report.method.parameters["checkpoint_sha256"] == "a" * 64
    assert report.method.parameters["runtime_classification"] == "INTERNAL_ONLY"
    assert "not current ListenCloser theory truth" in report.interpretation


def test_analysisgnn_score_report_rejects_unadmitted_upstream_task() -> None:
    evidence = AnalysisGNNScoreEvidence(
        observations=(
            AnalysisGNNScoreObservation(
                onset_beat=0.0,
                measure_number=1,
                labels=(("quality", "major"),),
            ),
        ),
        tasks=("quality",),
        provenance=_provenance(),
    )

    with pytest.raises(ValueError, match="non-product tasks"):
        build_analysisgnn_score_report(
            evidence,
            work_id=uuid4(),
            source_score_artifact_id=uuid4(),
            source_score_version_id=uuid4(),
        )
