from types import SimpleNamespace
from uuid import uuid4

from auth_utils import verify_token
from domain.api import projects_works
from domain.models import Artifact, ArtifactKind, Version, Work
from domain.work_bundle_repository import WorkBundleSnapshot
from main import app


class FakeBucket:
    def __init__(self, events: list[tuple[str, object]]):
        self.events = events

    def remove(self, paths):
        self.events.append(("storage.remove", paths))


class FakeStorage:
    def __init__(self, events: list[tuple[str, object]]):
        self.events = events

    def from_(self, _bucket):
        return FakeBucket(self.events)


class FakeClient:
    def __init__(self, events: list[tuple[str, object]]):
        self.storage = FakeStorage(events)


def test_delete_work_is_durable_before_storage_cleanup(client, monkeypatch):
    events: list[tuple[str, object]] = []
    project_id = uuid4()
    work = Work(project_id=project_id, title="Delete me")
    artifact = Artifact(work_id=work.id, kind=ArtifactKind.audio_original, mime_type="audio/wav")
    version = Version(
        artifact_id=artifact.id,
        storage_bucket="artifacts",
        storage_key="owner/project/artifact/source.wav",
    )
    snapshot = WorkBundleSnapshot(
        work=work,
        artifacts=[artifact],
        versions_by_artifact={artifact.id: [version]},
        jobs=[],
    )

    class FakeWorkRepo:
        def get(self, work_id, owner_id):
            assert work_id == work.id
            assert owner_id == "alice"
            return work

        def delete(self, work_id, owner_id):
            assert work_id == work.id
            assert owner_id == "alice"
            events.append(("work.delete", str(work_id)))

    class FakeBundleRepository:
        def load(self, work_id, owner_id):
            assert work_id == work.id
            assert owner_id == "alice"
            return snapshot

    class LegacyArtifactRepo:
        def list_by_work(self, _work_id, _owner_id):
            return [artifact]

        def delete(self, artifact_id, _owner_id):
            events.append(("artifact.delete", str(artifact_id)))

    class LegacyVersionRepo:
        def list_by_artifact(self, _artifact_id, _owner_id):
            return [version]

    fake_client = FakeClient(events)
    auth = SimpleNamespace(user=SimpleNamespace(id="alice"))

    monkeypatch.setitem(app.dependency_overrides, verify_token, lambda: auth)
    monkeypatch.setattr(projects_works, "supabase_client", lambda: fake_client)
    monkeypatch.setattr(projects_works, "WorkRepo", lambda _client: FakeWorkRepo())
    monkeypatch.setattr(
        projects_works,
        "WorkBundleRepository",
        lambda _client: FakeBundleRepository(),
    )
    # These two fakes make the regression fail by ordering on the pre-fix route,
    # while remaining intentionally unused after child-row deletion is delegated
    # to the database's existing ON DELETE CASCADE constraints.
    monkeypatch.setattr(
        projects_works,
        "ArtifactRepo",
        lambda _client: LegacyArtifactRepo(),
        raising=False,
    )
    monkeypatch.setattr(
        projects_works,
        "VersionRepo",
        lambda _client: LegacyVersionRepo(),
        raising=False,
    )
    monkeypatch.setattr(
        projects_works,
        "classify_version_storage_locator",
        lambda *_args, **_kwargs: SimpleNamespace(trusted=True, reason=None),
    )

    response = client.delete(f"/api/v1/works/{work.id}")

    assert response.status_code == 200
    assert response.json() == {"deleted": str(work.id)}
    assert events == [
        ("work.delete", str(work.id)),
        ("storage.remove", [version.storage_key]),
    ]
