from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1))


replace_once(
    "backend/domain/api.py",
    '''class UnderstandWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    transcription_profile: Literal["auto", "solo_piano"] | None = None
    score_engine: Literal["musescore", "pm2s"] | None = None


def _canonical_transcription_profile(profile: str | None) -> str:
''',
    '''class UnderstandWorkflowBody(BaseModel):
    version_id: str
    project_id: str
    transcription_profile: Literal["auto", "solo_piano"] | None = None
    score_engine: Literal["musescore", "pm2s"] | None = None


class ScoreWorkflowBody(BaseModel):
    performance_midi_version_id: str
    project_id: str
    score_engine: Literal["musescore", "pm2s"] | None = None


def _canonical_transcription_profile(profile: str | None) -> str:
''',
)

score_route = '''# ---------------------------------------------------------------------------
# POST /workflows/score
# ---------------------------------------------------------------------------


@router.post("/workflows/score", response_model=WorkflowJobResponse)
@limiter.limit("10/minute")
async def create_score_workflow(
    body: ScoreWorkflowBody,
    request: Request,
    auth=Depends(verify_token),
):
    """Rebuild Score from an existing canonical performance-MIDI version.

    This route intentionally queues only the score capability. It never
    retranscribes audio, so changing Score interpretation does not mutate or
    replace the canonical performance representation used by Piano Roll.
    """
    sb = _sb()
    owner_id = _owner_id(auth)
    version_id = UUID(body.performance_midi_version_id)
    project_id = UUID(body.project_id)

    try:
        version = _require_version_in_project(sb, version_id, project_id, owner_id)
        artifact = ArtifactRepo(sb).get(version.artifact_id, owner_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        if artifact.kind != ArtifactKind.midi_performance:
            raise HTTPException(
                status_code=400,
                detail="Score rebuild requires a performance MIDI version",
            )

        score_engine = _canonical_score_engine(body.score_engine)
        job_id = uuid5(
            NAMESPACE_URL,
            f"hello-ai:score:1.0:{owner_id}:{version_id}:{score_engine}",
        )
        job_repo = JobRepo(sb)
        existing_job = job_repo.get(job_id, owner_id)
        if existing_job:
            existing_workflow = WorkflowRepo(sb).get(existing_job.workflow_id, owner_id)
            if not existing_workflow:
                raise RuntimeError("idempotent score job references a missing workflow")
            return {"workflow": existing_workflow, "job": existing_job}

        wf_repo = WorkflowRepo(sb)
        workflow = Workflow(
            id=uuid5(
                NAMESPACE_URL,
                f"hello-ai:score-workflow:1.0:{owner_id}:{version_id}:{score_engine}",
            ),
            project_id=project_id,
            kind=WorkflowKind.understand,
            target_version_id=version_id,
            parameters={"score_engine": score_engine, "workflow_scope": "score_rebuild"},
        )
        try:
            workflow = wf_repo.create(workflow, owner_id)
        except Exception:
            concurrent_job = job_repo.get(job_id, owner_id)
            if concurrent_job:
                concurrent_workflow = wf_repo.get(concurrent_job.workflow_id, owner_id)
                if concurrent_workflow:
                    return {"workflow": concurrent_workflow, "job": concurrent_job}
            workflow = wf_repo.get(workflow.id, owner_id)
            if not workflow:
                raise

        job = Job(
            id=job_id,
            workflow_id=workflow.id,
            capability=Capability(name="score", version="1.0"),
            input_version_ids=[version_id],
            parameters={
                "score_engine": score_engine,
                "input_representation": "performance_midi",
            },
            cache_key=f"score:1.0:{owner_id}:{version_id}:{score_engine}",
            created_by=owner_id,
        )
        try:
            job = job_repo.create(job, owner_id)
        except Exception:
            job = job_repo.get(job_id, owner_id)
            if not job:
                raise

        return {"workflow": workflow, "job": job}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


'''
replace_once(
    "backend/domain/api.py",
    '''# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------
''',
    score_route
    + '''# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------
''',
)

Path("backend/tests/test_score_rebuild_workflow.py").write_text(
    '''"""Focused API coverage for score-only reinterpretation from performance MIDI."""

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
'''
)
