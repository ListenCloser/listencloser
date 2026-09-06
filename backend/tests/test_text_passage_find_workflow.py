"""Focused API coverage for durable CLaMP3 text-to-passage Find jobs."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from domain.models import ArtifactKind


class TestTextPassageFindWorkflow:
    PROJECT_ID = UUID("00000000-0000-0000-0000-000000000120")
    WORK_ID = UUID("00000000-0000-0000-0000-000000000121")
    SOURCE_VERSION_ID = UUID("00000000-0000-0000-0000-000000000122")
    SOURCE_ARTIFACT_ID = UUID("00000000-0000-0000-0000-000000000123")
    PERFORMANCE_VERSION_ID = UUID("00000000-0000-0000-0000-000000000124")
    PERFORMANCE_ARTIFACT_ID = UUID("00000000-0000-0000-0000-000000000125")
    SECONDARY_WORK_ID = UUID("00000000-0000-0000-0000-000000000198")

    def _client(self, monkeypatch, *, parent_matches: bool = True, same_work: bool = True):
        from auth_utils import verify_token
        from domain.api import text_passage_find as api
        from main import app

        owner = "owner-find"
        source_version = SimpleNamespace(
            id=self.SOURCE_VERSION_ID,
            artifact_id=self.SOURCE_ARTIFACT_ID,
            parent_version_id=None,
        )
        performance_version = SimpleNamespace(
            id=self.PERFORMANCE_VERSION_ID,
            artifact_id=self.PERFORMANCE_ARTIFACT_ID,
            parent_version_id=(
                self.SOURCE_VERSION_ID
                if parent_matches
                else UUID("00000000-0000-0000-0000-000000000199")
            ),
        )
        source_artifact = SimpleNamespace(
            id=self.SOURCE_ARTIFACT_ID,
            work_id=self.WORK_ID,
            kind=ArtifactKind.audio_original,
        )
        performance_artifact = SimpleNamespace(
            id=self.PERFORMANCE_ARTIFACT_ID,
            work_id=self.WORK_ID if same_work else self.SECONDARY_WORK_ID,
            kind=ArtifactKind.midi_performance,
        )
        source_work = SimpleNamespace(id=self.WORK_ID, project_id=self.PROJECT_ID)
        secondary_work = SimpleNamespace(
            id=self.SECONDARY_WORK_ID,
            project_id=self.PROJECT_ID,
        )

        class FakeVersionRepo:
            def __init__(self, _sb):
                pass

            def get(self, version_id, _owner_id):
                return {
                    self_ref.SOURCE_VERSION_ID: source_version,
                    self_ref.PERFORMANCE_VERSION_ID: performance_version,
                }.get(version_id)

        class FakeArtifactRepo:
            def __init__(self, _sb):
                pass

            def get(self, artifact_id, _owner_id):
                return {
                    self_ref.SOURCE_ARTIFACT_ID: source_artifact,
                    self_ref.PERFORMANCE_ARTIFACT_ID: performance_artifact,
                }.get(artifact_id)

        class FakeWorkRepo:
            def __init__(self, _sb):
                pass

            def get(self, work_id, _owner_id):
                return {
                    self_ref.WORK_ID: source_work,
                    self_ref.SECONDARY_WORK_ID: secondary_work,
                }.get(work_id)

        class FakeJobRepo:
            def __init__(self):
                self.created = []
                self.jobs = {}

            def get(self, job_id, _owner_id):
                return self.jobs.get(job_id)

            def create(self, job, _owner_id):
                self.created.append(job)
                self.jobs[job.id] = job
                return job

        class FakeWorkflowRepo:
            def __init__(self):
                self.created = []
                self.workflows = {}

            def create(self, workflow, _owner_id):
                self.created.append(workflow)
                self.workflows[workflow.id] = workflow
                return workflow

            def get(self, workflow_id, _owner_id):
                return self.workflows.get(workflow_id)

        self_ref = self
        job_repo = FakeJobRepo()
        workflow_repo = FakeWorkflowRepo()
        monkeypatch.setattr(api, "VersionRepo", FakeVersionRepo)
        monkeypatch.setattr(api, "ArtifactRepo", FakeArtifactRepo)
        monkeypatch.setattr(api, "WorkRepo", FakeWorkRepo)
        monkeypatch.setattr(api, "JobRepo", lambda _sb: job_repo)
        monkeypatch.setattr(api, "WorkflowRepo", lambda _sb: workflow_repo)
        monkeypatch.setattr(api, "supabase_client", lambda: SimpleNamespace())
        app.dependency_overrides[verify_token] = lambda: SimpleNamespace(
            user=SimpleNamespace(id=owner)
        )

        from fastapi.testclient import TestClient

        return TestClient(app), job_repo, workflow_repo

    def _body(self, **overrides):
        return {
            "source_version_id": str(self.SOURCE_VERSION_ID),
            "performance_version_id": str(self.PERFORMANCE_VERSION_ID),
            "project_id": str(self.PROJECT_ID),
            "text": "  sparse piano  ",
            "max_matches": 3,
            **overrides,
        }

    @staticmethod
    def _cleanup_auth():
        from auth_utils import verify_token
        from main import app

        app.dependency_overrides.pop(verify_token, None)

    def test_queues_exact_two_version_find_job(self, monkeypatch):
        client, job_repo, workflow_repo = self._client(monkeypatch)
        try:
            response = client.post("/api/v1/workflows/text-passage-find", json=self._body())

            assert response.status_code == 200
            assert len(job_repo.created) == 1
            job = job_repo.created[0]
            assert job.capability.name == "text_passage_find"
            assert job.input_version_ids == [self.SOURCE_VERSION_ID, self.PERFORMANCE_VERSION_ID]
            assert job.parameters == {
                "text": "sparse piano",
                "max_matches": 3,
                "performance_version_id": str(self.PERFORMANCE_VERSION_ID),
            }
            assert workflow_repo.created[0].target_version_id == self.SOURCE_VERSION_ID
            assert workflow_repo.created[0].parameters["action"] == "text_passage_find"
        finally:
            self._cleanup_auth()

    def test_same_exact_query_is_idempotent(self, monkeypatch):
        client, job_repo, _ = self._client(monkeypatch)
        try:
            first = client.post("/api/v1/workflows/text-passage-find", json=self._body())
            second = client.post(
                "/api/v1/workflows/text-passage-find",
                json=self._body(text="sparse piano"),
            )

            assert first.status_code == 200
            assert second.status_code == 200
            assert first.json()["job"]["id"] == second.json()["job"]["id"]
            assert len(job_repo.created) == 1
        finally:
            self._cleanup_auth()

    def test_rejects_non_parented_performance_version(self, monkeypatch):
        client, job_repo, _ = self._client(monkeypatch, parent_matches=False)
        try:
            response = client.post("/api/v1/workflows/text-passage-find", json=self._body())

            assert response.status_code == 400
            assert "directly parented" in response.json()["detail"]
            assert job_repo.created == []
        finally:
            self._cleanup_auth()

    def test_rejects_versions_from_different_works(self, monkeypatch):
        client, job_repo, _ = self._client(monkeypatch, same_work=False)
        try:
            response = client.post("/api/v1/workflows/text-passage-find", json=self._body())

            assert response.status_code == 400
            assert "same Work" in response.json()["detail"]
            assert job_repo.created == []
        finally:
            self._cleanup_auth()
