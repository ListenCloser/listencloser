from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from domain.api import projects_works


def _install_repository_fakes(monkeypatch, events: list[str]):
    work_id = uuid4()
    project_id = uuid4()
    artifact_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    work = SimpleNamespace(project_id=project_id)
    version = SimpleNamespace(
        id=version_id,
        storage_bucket="artifacts",
        storage_key="owner/work/score.musicxml",
    )
    snapshot = SimpleNamespace(
        work=work,
        jobs=[SimpleNamespace(id=job_id)],
        artifacts=[SimpleNamespace(id=artifact_id)],
        versions_by_artifact={artifact_id: [version]},
    )

    class FakeWorkRepo:
        def __init__(self, _client):
            pass

        def get(self, candidate_work_id, owner):
            assert candidate_work_id == work_id
            assert owner == "owner"
            events.append("work-get")
            return work

        def delete(self, candidate_work_id, owner):
            assert candidate_work_id == work_id
            assert owner == "owner"
            events.append("work-delete")

    class FakeWorkBundleRepository:
        def __init__(self, _client):
            pass

        def load(self, candidate_work_id, owner):
            assert candidate_work_id == work_id
            assert owner == "owner"
            events.append("snapshot")
            return snapshot

    monkeypatch.setattr(projects_works, "WorkRepo", FakeWorkRepo)
    monkeypatch.setattr(projects_works, "WorkBundleRepository", FakeWorkBundleRepository)
    monkeypatch.setattr(
        projects_works,
        "classify_version_storage_locator",
        lambda *_args, **_kwargs: SimpleNamespace(trusted=True, reason=None),
    )
    return work_id


class FakeStorage:
    def __init__(self, events: list[str], *, fail_remove: bool = False):
        self.events = events
        self.fail_remove = fail_remove

    def from_(self, bucket: str):
        assert bucket == "artifacts"
        storage = self

        class Bucket:
            def remove(self, keys: list[str]):
                assert keys == ["owner/work/score.musicxml"]
                storage.events.append("storage-remove")
                if storage.fail_remove:
                    raise RuntimeError("storage unavailable")

        return Bucket()


class FakeClient:
    def __init__(self, events: list[str], *, fail_remove: bool = False):
        self.storage = FakeStorage(events, fail_remove=fail_remove)


def test_work_row_is_deleted_before_storage_cleanup(monkeypatch):
    events: list[str] = []
    work_id = _install_repository_fakes(monkeypatch, events)

    result = projects_works._delete_work_and_cleanup(FakeClient(events), work_id, "owner")

    assert result == {"deleted": str(work_id)}
    assert events == ["work-get", "snapshot", "work-delete", "storage-remove"]


def test_storage_cleanup_failure_does_not_reverse_authoritative_delete(monkeypatch):
    events: list[str] = []
    work_id = _install_repository_fakes(monkeypatch, events)

    result = projects_works._delete_work_and_cleanup(
        FakeClient(events, fail_remove=True), work_id, "owner"
    )

    assert result == {"deleted": str(work_id)}
    assert events == ["work-get", "snapshot", "work-delete", "storage-remove"]
