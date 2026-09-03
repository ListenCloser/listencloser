from types import SimpleNamespace
from uuid import uuid4

from auth_utils import verify_token
from domain.api import projects_works
from domain.models import Project, Work
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


def _foreign_work_client() -> tuple[FakeClient, Work]:
    project = Project(owner_id="bob", name="Bob library")
    work = Work(project_id=project.id, title="Private piece")
    return (
        FakeClient(
            {
                "projects": [project.model_dump(mode="json")],
                "works": [work.model_dump(mode="json")],
            }
        ),
        work,
    )


def test_private_work_routes_hide_foreign_object_existence(client, monkeypatch):
    fake_client, foreign_work = _foreign_work_client()
    missing_work_id = uuid4()
    auth = SimpleNamespace(user=SimpleNamespace(id="alice"))

    monkeypatch.setitem(app.dependency_overrides, verify_token, lambda: auth)
    monkeypatch.setattr(projects_works, "supabase_client", lambda: fake_client)

    for method in (client.get, client.delete):
        foreign_response = method(f"/api/v1/works/{foreign_work.id}")
        missing_response = method(f"/api/v1/works/{missing_work_id}")

        assert foreign_response.status_code == 404
        assert missing_response.status_code == 404
        assert foreign_response.json() == {"detail": "Work not found"}
        assert missing_response.json() == {"detail": "Work not found"}
