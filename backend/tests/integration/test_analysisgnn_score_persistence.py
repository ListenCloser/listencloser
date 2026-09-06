from __future__ import annotations

import json
import uuid
from uuid import UUID

import pytest

from domain.analysisgnn_score_capability import handle_analysisgnn_score
from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Job,
    JobLifecycle,
    JobStage,
    Project,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)
from domain.repositories import (
    ArtifactRepo,
    JobRepo,
    ProjectRepo,
    VersionRepo,
    WorkflowRepo,
    WorkRepo,
)
from engines.base import EngineProvenance
from engines.symbolic.analysisgnn import AnalysisGNNResult

OWNER_ID = "00000000-0000-4000-8000-000000001248"
pytestmark = pytest.mark.real_stack


def test_analysisgnn_score_persists_exact_score_lineage_and_internal_provenance(sb, monkeypatch):
    project = ProjectRepo(sb).create(
        Project(owner_id=OWNER_ID, name=f"it-analysisgnn-{uuid.uuid4().hex[:8]}")
    )
    work = WorkRepo(sb).create(Work(project_id=project.id, title="AnalysisGNN piano smoke"), OWNER_ID)
    artifact = ArtifactRepo(sb).create(
        Artifact(
            work_id=work.id,
            kind=ArtifactKind.musicxml_score,
            mime_type="application/vnd.recordare.musicxml+xml",
        ),
        OWNER_ID,
    )
    storage_key = f"it/{uuid.uuid4().hex}.musicxml"
    score_bytes = b"<score-partwise version='4.0'></score-partwise>"
    sb.storage.from_("artifacts").upload(
        storage_key,
        score_bytes,
        {"content-type": "application/vnd.recordare.musicxml+xml"},
    )
    source_version = VersionRepo(sb).create(
        Version(
            artifact_id=artifact.id,
            storage_key=storage_key,
            storage_bucket="artifacts",
            label="fixture.musicxml",
            created_by=OWNER_ID,
        ),
        OWNER_ID,
    )
    workflow = WorkflowRepo(sb).create(
        Workflow(
            project_id=project.id,
            kind=WorkflowKind.understand,
            target_version_id=source_version.id,
        ),
        OWNER_ID,
    )
    job = Job(
        workflow_id=workflow.id,
        capability=Capability(name="analysisgnn_score", version="1.0"),
        lifecycle=JobLifecycle(current=JobStage.running),
        input_version_ids=[source_version.id],
        created_by=OWNER_ID,
    )
    job = JobRepo(sb).create(job, OWNER_ID)

    def _fake_analyze(_self, musicxml_bytes, *, tasks):
        assert musicxml_bytes == score_bytes
        assert tasks == ("cadence", "localkey", "romanNumeral")
        return AnalysisGNNResult(
            predictions=[
                {
                    "cadence": "PAC",
                    "localkey": "C",
                    "romanNumeral": "V7",
                    "onset": "12.0",
                    "s_measure": "5",
                }
            ],
            tasks=tasks,
            provenance=EngineProvenance(
                engine="analysisgnn",
                library_version="1.0.0",
                model="local-pinned-checkpoint",
                parameters={
                    "checkpoint_sha256": "b" * 64,
                    "model_license": "UNVERIFIED",
                    "runtime_classification": "INTERNAL_ONLY",
                    "commercial_default_eligible": False,
                },
            ),
        )

    monkeypatch.setattr(
        "domain.analysisgnn_score_capability.AnalysisGNNEngine.analyze_musicxml",
        _fake_analyze,
    )

    output_ids = handle_analysisgnn_score(job, sb)
    assert len(output_ids) == 1

    output_version = VersionRepo(sb).get(UUID(output_ids[0]), OWNER_ID)
    assert output_version is not None
    assert output_version.parent_version_id == source_version.id
    assert output_version.lineage == [source_version.id]
    assert output_version.produced_by_job_id == job.id
    assert output_version.metadata["report_type"] == "analysisgnn_score_analysis"
    assert output_version.metadata["source_score_version_id"] == str(source_version.id)
    assert output_version.metadata["source_score_artifact_id"] == str(artifact.id)
    assert output_version.metadata["runtime_classification"] == "INTERNAL_ONLY"
    assert output_version.metadata["model_license"] == "UNVERIFIED"
    assert output_version.metadata["checkpoint_sha256"] == "b" * 64
    assert output_version.metadata["tasks"] == ["cadence", "localkey", "romanNumeral"]
    assert output_version.metadata["observation_count"] == 1

    payload = sb.storage.from_("artifacts").download(output_version.storage_key)
    report = json.loads(payload)
    assert report["source_score_version_id"] == str(source_version.id)
    assert report["source_score_artifact_id"] == str(artifact.id)
    assert report["method"]["parameters"]["runtime_classification"] == "INTERNAL_ONLY"
    assert report["observations"] == [
        {
            "onset_beat": 12.0,
            "measure_number": 5,
            "labels": [
                {"task": "cadence", "value": "PAC"},
                {"task": "localkey", "value": "C"},
                {"task": "romanNumeral", "value": "V7"},
            ],
        }
    ]
