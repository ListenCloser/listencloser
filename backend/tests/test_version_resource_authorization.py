from types import SimpleNamespace
from uuid import uuid4

from auth_utils import verify_token
from domain.api import artifacts_versions, evidence
from main import app


class FakeQuery:
    def __init__(self, client, table: str):
        self.client = client
        self.table = table
        self.filters: list[tuple[str, object]] = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        matching = [
            row
            for row in self.client.rows.get(self.table, [])
            if all(str(row.get(column)) == str(value) for column, value in self.filters)
        ]
        return SimpleNamespace(data=[dict(row) for row in matching])


class FakeClient:
    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows

    def table(self, table: str):
        return FakeQuery(self, table)


def _foreign_version_client():
    project_id = uuid4()
    work_id = uuid4()
    artifact_id = uuid4()
    version_id = uuid4()
    return (
        FakeClient(
            {
                "projects": [{"id": str(project_id), "owner_id": "bob"}],
                "works": [{"id": str(work_id), "project_id": str(project_id)}],
                "artifacts": [{"id": str(artifact_id), "work_id": str(work_id)}],
                "artifact_versions": [{"id": str(version_id), "artifact_id": str(artifact_id)}],
            }
        ),
        version_id,
    )


def test_version_read_routes_hide_foreign_object_existence(client, monkeypatch):
    fake_client, foreign_version_id = _foreign_version_client()
    missing_version_id = uuid4()
    auth = SimpleNamespace(user=SimpleNamespace(id="alice"))

    monkeypatch.setitem(app.dependency_overrides, verify_token, lambda: auth)
    monkeypatch.setattr(artifacts_versions, "supabase_client", lambda: fake_client)
    monkeypatch.setattr(evidence, "supabase_client", lambda: fake_client)

    paths = (
        "/api/v1/versions/{version_id}",
        "/api/v1/versions/{version_id}/entities",
        "/api/v1/versions/{version_id}/insights",
    )
    for path in paths:
        foreign_response = client.get(path.format(version_id=foreign_version_id))
        missing_response = client.get(path.format(version_id=missing_version_id))

        assert foreign_response.status_code == 404
        assert missing_response.status_code == 404
        assert foreign_response.json() == {"detail": "Version not found"}
        assert missing_response.json() == {"detail": "Version not found"}
