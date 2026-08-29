from types import SimpleNamespace

import pytest

from domain.models import (
    Artifact,
    ArtifactKind,
    Capability,
    Job,
    Project,
    Version,
    Work,
    Workflow,
    WorkflowKind,
)
from domain.repositories import JobRepo
from domain.work_bundle_repository import WorkBundleRepository


class FakeQuery:
    def __init__(self, client, table: str):
        self.client = client
        self.table = table
        self.filters: list[tuple[str, str, object]] = []
        self.ordering: tuple[str, bool] | None = None
        self.window: tuple[int, int] | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column: str, values):
        self.filters.append(("in", column, values))
        return self

    def order(self, column: str, *, desc: bool = False):
        self.ordering = (column, desc)
        return self

    def range(self, start: int, end: int):
        self.window = (start, end)
        return self

    def execute(self):
        rows = [dict(row) for row in self.client.rows.get(self.table, [])]
        for op, column, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if str(row.get(column)) == str(value)]
            else:
                accepted = {str(item) for item in value}
                rows = [row for row in rows if str(row.get(column)) in accepted]
        if self.ordering:
            column, desc = self.ordering
            rows.sort(key=lambda row: str(row.get(column) or ""), reverse=desc)
        if self.window:
            start, end = self.window
            rows = rows[start : end + 1]
        self.client.executed.append(self.table)
        return SimpleNamespace(data=rows)


class FakeClient:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.executed: list[str] = []

    def table(self, table: str):
        return FakeQuery(self, table)


def _fixture_graph():
    project = Project(owner_id="user-1", name="Library")
    work = Work(project_id=project.id, title="Saved piece")
    audio = Artifact(work_id=work.id, kind=ArtifactKind.audio_original)
    midi = Artifact(work_id=work.id, kind=ArtifactKind.midi_performance)
    audio_v1 = Version(
        artifact_id=audio.id,
        storage_key="audio.wav",
        storage_bucket="artifacts",
    )
    midi_v1 = Version(
        artifact_id=midi.id,
        storage_key="midi-v1.mid",
        storage_bucket="artifacts",
    )
    midi_v2 = Version(
        artifact_id=midi.id,
        parent_version_id=midi_v1.id,
        lineage=[midi_v1.id],
        storage_key="midi-v2.mid",
        storage_bucket="artifacts",
    )
    workflow = Workflow(
        project_id=project.id,
        kind=WorkflowKind.understand,
        target_version_id=midi_v2.id,
    )
    job = Job(
        workflow_id=workflow.id,
        capability=Capability(name="understand", version="1.0"),
        input_version_ids=[midi_v2.id],
    )

    client = FakeClient()
    client.rows = {
        "projects": [project.model_dump(mode="json")],
        "works": [work.model_dump(mode="json")],
        "artifacts": [audio.model_dump(mode="json"), midi.model_dump(mode="json")],
        "artifact_versions": [
            audio_v1.model_dump(mode="json"),
            midi_v1.model_dump(mode="json"),
            midi_v2.model_dump(mode="json"),
        ],
        "workflows": [workflow.model_dump(mode="json")],
        "jobs": [JobRepo(client)._job_to_row(job)],
    }
    return client, project, work, audio, midi, workflow, job


def test_loads_complete_work_graph_in_six_queries():
    client, _project, work, audio, midi, workflow, job = _fixture_graph()

    snapshot = WorkBundleRepository(client).load(work.id, "user-1")

    assert snapshot is not None
    assert snapshot.work == work
    assert {artifact.id for artifact in snapshot.artifacts} == {audio.id, midi.id}
    assert len(snapshot.versions_by_artifact[audio.id]) == 1
    assert len(snapshot.versions_by_artifact[midi.id]) == 2
    assert [loaded.id for loaded in snapshot.jobs] == [job.id]
    assert snapshot.jobs[0].workflow_id == workflow.id
    assert client.executed == [
        "works",
        "projects",
        "artifacts",
        "artifact_versions",
        "workflows",
        "jobs",
    ]


def test_bulk_descendant_reads_page_instead_of_truncating(monkeypatch):
    client, _project, work, audio, midi, _workflow, _job = _fixture_graph()
    monkeypatch.setattr("domain.work_bundle_repository._PAGE_SIZE", 3)

    snapshot = WorkBundleRepository(client).load(work.id, "user-1")

    assert snapshot is not None
    assert len(snapshot.versions_by_artifact[audio.id]) == 1
    assert len(snapshot.versions_by_artifact[midi.id]) == 2
    assert client.executed.count("artifact_versions") == 2


def test_unauthorized_work_stops_before_descendant_reads():
    client, _project, work, *_rest = _fixture_graph()

    with pytest.raises(PermissionError):
        WorkBundleRepository(client).load(work.id, "other-user")

    assert client.executed == ["works", "projects"]


def test_empty_work_stops_after_artifact_read():
    project = Project(owner_id="user-1", name="Library")
    work = Work(project_id=project.id, title="Empty")
    client = FakeClient(
        {
            "projects": [project.model_dump(mode="json")],
            "works": [work.model_dump(mode="json")],
            "artifacts": [],
        }
    )

    snapshot = WorkBundleRepository(client).load(work.id, "user-1")

    assert snapshot is not None
    assert snapshot.artifacts == []
    assert snapshot.jobs == []
    assert client.executed == ["works", "projects", "artifacts"]
