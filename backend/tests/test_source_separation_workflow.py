from uuid import UUID, uuid4

import pytest

import domain.api.workflows_jobs as workflows_jobs
from auth_utils import verify_token
from domain.models import Artifact, ArtifactKind, Version, WorkflowKind
from main import app


@pytest.fixture
def separation_route_fakes(monkeypatch):
    source_version_id = uuid4()
    source_artifact_id = uuid4()
    work_id = uuid4()
    project_id = uuid4()
    owner = "layers-owner"
    source = Version(
        id=source_version_id,
        artifact_id=source_artifact_id,
        storage_key="owner/project/source.wav",
        storage_bucket="artifacts",
        label="source.wav",
    )
    source_artifact = Artifact(
        id=source_artifact_id,
        work_id=work_id,
        kind=ArtifactKind.audio_original,
        mime_type="audio/wav",
    )
    captured = {"workflows": [], "jobs": []}

    class FakeWorkflowRepo:
        def __init__(self, _client):
            pass

        def get(self, _workflow_id, _owner):
            return None

        def create(self, workflow, create_owner):
            assert create_owner == owner
            captured["workflows"].append(workflow)
            return workflow

    class FakeJobRepo:
        def __init__(self, _client):
            pass

        def get(self, _job_id, _owner):
            return None

        def create(self, job, create_owner):
            assert create_owner == owner
            captured["jobs"].append(job)
            return job

    class FakeArtifactRepo:
        def __init__(self, _client):
            pass

        def get(self, artifact_id, get_owner):
            assert get_owner == owner
            assert artifact_id == source_artifact_id
            return source_artifact

    monkeypatch.setattr(workflows_jobs, "supabase_client", lambda: object())
    monkeypatch.setattr(workflows_jobs, "owner_id", lambda _auth: owner)
    monkeypatch.setattr(
        workflows_jobs,
        "_require_version_in_project",
        lambda _client, version_id, requested_project_id, requested_owner: source
        if (
            version_id == source_version_id
            and requested_project_id == project_id
            and requested_owner == owner
        )
        else None,
    )
    monkeypatch.setattr(workflows_jobs, "WorkflowRepo", FakeWorkflowRepo)
    monkeypatch.setattr(workflows_jobs, "JobRepo", FakeJobRepo)
    monkeypatch.setattr(workflows_jobs, "ArtifactRepo", FakeArtifactRepo)
    app.dependency_overrides[verify_token] = lambda: {"sub": owner}

    yield {
        "source_version_id": source_version_id,
        "project_id": project_id,
        "captured": captured,
        "source_artifact": source_artifact,
    }

    app.dependency_overrides.pop(verify_token, None)


def test_separate_workflow_is_detached_from_normal_work_processing(
    client,
    separation_route_fakes,
):
    source_version_id: UUID = separation_route_fakes["source_version_id"]
    project_id: UUID = separation_route_fakes["project_id"]
    captured = separation_route_fakes["captured"]

    response = client.post(
        "/api/v1/workflows/create",
        json={
            "version_id": str(source_version_id),
            "project_id": str(project_id),
            "action": "separate",
            "parameters": {},
        },
    )

    assert response.status_code == 200, response.text
    assert len(captured["workflows"]) == 1
    assert len(captured["jobs"]) == 1

    workflow = captured["workflows"][0]
    job = captured["jobs"][0]
    assert workflow.kind == WorkflowKind.create
    # WorkBundleRepository discovers normal Work processing through workflows
    # whose target_version_id is a Version of the Work. Optional separation is
    # deliberately detached from that relation, so failure cannot replace the
    # Work's ordinary processing state.
    assert workflow.target_version_id is None
    assert workflow.parameters["action"] == "separate"
    assert job.capability.name == "separate"
    assert job.input_version_ids == [source_version_id]
    assert job.parameters["model_signature"] == "955717e8"
    assert job.parameters["shifts"] == 0


def test_separate_workflow_rejects_non_original_sources(
    client,
    separation_route_fakes,
    monkeypatch,
):
    source_version_id: UUID = separation_route_fakes["source_version_id"]
    project_id: UUID = separation_route_fakes["project_id"]
    source_artifact = separation_route_fakes["source_artifact"].model_copy(
        update={"kind": ArtifactKind.audio_rendered}
    )

    class NonOriginalArtifactRepo:
        def __init__(self, _client):
            pass

        def get(self, _artifact_id, _owner):
            return source_artifact

    monkeypatch.setattr(workflows_jobs, "ArtifactRepo", NonOriginalArtifactRepo)

    response = client.post(
        "/api/v1/workflows/create",
        json={
            "version_id": str(source_version_id),
            "project_id": str(project_id),
            "action": "separate",
            "parameters": {},
        },
    )

    assert response.status_code == 400
    assert "Original audio" in response.text
