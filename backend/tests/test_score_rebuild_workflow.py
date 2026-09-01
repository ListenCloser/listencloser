"""Focused API coverage for score-only reinterpretation from performance MIDI."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from domain.models import ArtifactKind


class TestScoreRebuildWorkflow:
    PROJECT_ID = UUID("00000000-0000-0000-0000-000000000020")
    VERSION_ID = "00000000-0000-0000-0000-000000000010"
    ARTIFACT_ID = "00000000-0000-0000-0000-000000000011"
    WORK_ID = "00000000-0000-0000-0000-000000000012"

    def _client(self, monkeypatch, *, artifact_kind=ArtifactKind.midi_performance):
        import domain.api as api
        from auth_utils import verify_token
        from main import app

        owner = "owner-1"
        version = SimpleNamespace(
            id=self.VERSION_ID,
            label="performance.mid",
            artifact_id=self.ARTIFACT_ID,
        )
        artifact = SimpleNamespace(
            id=self.ARTIFACT_ID,
            work_id=self.WORK_ID,
            kind=artifact_kind,
        )
        work = SimpleNamespace(id=self.WORK_ID, project_id=self.PROJECT_ID)

        class FakeVersionRepo:
            def __init__(self, sb):
                pass

            def get(self, version_id, owner_id):
                return version if str(version_id) == version.id else None

        class FakeArtifactRepo:
            def __init__(self, sb):
                pass

            def get(self, artifact_id, owner_id):
                return artifact if str(artifact_id) == artifact.id else None

        class FakeWorkRepo:
            def __init__(self, sb):
                pass

            def get(self, work_id, owner_id):
                return work if str(work_id) == work.id else None

        class FakeJobRepo:
            def __init__(self):
                self.created = []
                self.jobs = {}

            def get(self, job_id, owner_id):
                return self.jobs.get(str(job_id))

            def create(self, job, owner_id):
                self.jobs[str(job.id)] = job
                self.created.append(job)
                return job

        class FakeWorkflowRepo:
            def __init__(self):
                self.created = []
                self.workflows = {}

            def create(self, workflow, owner_id):
                self.workflows[str(workflow.id)] = workflow
                self.created.append(workflow)
                return workflow

            def get(self, workflow_id, owner_id):
                return self.workflows.get(str(workflow_id))

        job_repo = FakeJobRepo()
        workflow_repo = FakeWorkflowRepo()

        monkeypatch.setattr(api, "VersionRepo", FakeVersionRepo)
        monkeypatch.setattr(api, "ArtifactRepo", FakeArtifactRepo)
        monkeypatch.setattr(api, "WorkRepo", FakeWorkRepo)
        monkeypatch.setattr(api, "JobRepo", lambda sb: job_repo)
        monkeypatch.setattr(api, "WorkflowRepo", lambda sb: workflow_repo)
        monkeypatch.setattr(api, "get_supabase", lambda: SimpleNamespace())
        app.dependency_overrides[verify_token] = lambda: SimpleNamespace(
            user=SimpleNamespace(id=owner)
        )

        from fastapi.testclient import TestClient

        return TestClient(app), job_repo, workflow_repo

    def _body(self, **overrides):
        return {
            "performance_midi_version_id": self.VERSION_ID,
            "project_id": str(self.PROJECT_ID),
            **overrides,
        }

    def _cleanup_auth(self):
        from auth_utils import verify_token
        from main import app

        app.dependency_overrides.pop(verify_token, None)

    def test_creates_only_score_job_from_performance_midi(self, monkeypatch):
        client, job_repo, workflow_repo = self._client(monkeypatch)
        try:
            response = client.post(
                "/api/v1/workflows/score",
                json=self._body(score_engine="pm2s"),
            )

            assert response.status_code == 200
            assert len(job_repo.created) == 1
            job = job_repo.created[0]
            assert job.capability.name == "score"
            assert [str(value) for value in job.input_version_ids] == [self.VERSION_ID]
            assert job.parameters == {
                "score_engine": "pm2s",
                "input_representation": "performance_midi",
            }
            assert job.cache_key.endswith(f":{self.VERSION_ID}:pm2s")
            assert all(created.capability.name != "transcribe" for created in job_repo.created)
            assert workflow_repo.created[0].parameters["workflow_scope"] == "score_rebuild"
        finally:
            self._cleanup_auth()

    def test_score_engine_is_part_of_idempotency_identity(self, monkeypatch):
        client, job_repo, _ = self._client(monkeypatch)
        try:
            baseline = client.post(
                "/api/v1/workflows/score",
                json=self._body(score_engine="musescore"),
            )
            challenger = client.post(
                "/api/v1/workflows/score",
                json=self._body(score_engine="pm2s"),
            )

            assert baseline.status_code == 200
            assert challenger.status_code == 200
            assert len(job_repo.created) == 2
            assert job_repo.created[0].id != job_repo.created[1].id
            assert job_repo.created[0].cache_key != job_repo.created[1].cache_key
        finally:
            self._cleanup_auth()

    def test_omitted_engine_matches_explicit_musescore(self, monkeypatch):
        client, job_repo, _ = self._client(monkeypatch)
        try:
            omitted = client.post("/api/v1/workflows/score", json=self._body())
            explicit = client.post(
                "/api/v1/workflows/score",
                json=self._body(score_engine="musescore"),
            )

            assert omitted.status_code == 200
            assert explicit.status_code == 200
            assert omitted.json()["job"]["id"] == explicit.json()["job"]["id"]
            assert len(job_repo.created) == 1
        finally:
            self._cleanup_auth()

    def test_rejects_non_performance_midi_artifact(self, monkeypatch):
        client, job_repo, _ = self._client(
            monkeypatch,
            artifact_kind=ArtifactKind.midi_corrected,
        )
        try:
            response = client.post("/api/v1/workflows/score", json=self._body())

            assert response.status_code == 400
            assert response.json()["detail"] == "Score rebuild requires a performance MIDI version"
            assert job_repo.created == []
        finally:
            self._cleanup_auth()

    def test_rejects_version_from_another_project(self, monkeypatch):
        client, job_repo, _ = self._client(monkeypatch)
        try:
            response = client.post(
                "/api/v1/workflows/score",
                json=self._body(project_id="00000000-0000-0000-0000-000000000099"),
            )

            assert response.status_code == 400
            assert response.json()["detail"] == "Version does not belong to this project"
            assert job_repo.created == []
        finally:
            self._cleanup_auth()
