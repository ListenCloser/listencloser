from types import SimpleNamespace

import pytest

from domain.models import Project, Work
from domain.repositories import WorkRepo


class FakeQuery:
    def __init__(self, client, table: str):
        self.client = client
        self.table = table
        self.operation = "select"
        self.payload: dict | None = None
        self.filters: list[tuple[str, object]] = []

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def update(self, payload: dict):
        self.operation = "update"
        self.payload = dict(payload)
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
        self.client.executed.append((self.operation, self.table))
        if self.operation == "update":
            assert self.payload is not None
            for row in matching:
                row.update(self.payload)
        return SimpleNamespace(data=[dict(row) for row in matching])


class FakeClient:
    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows
        self.executed: list[tuple[str, str]] = []

    def table(self, table: str):
        return FakeQuery(self, table)


def _authorization_graph():
    alice_project = Project(owner_id="alice", name="Alice library")
    bob_project = Project(owner_id="bob", name="Bob library")
    alice_work = Work(project_id=alice_project.id, title="Alice piece")
    bob_work = Work(project_id=bob_project.id, title="Bob piece")
    client = FakeClient(
        {
            "projects": [
                alice_project.model_dump(mode="json"),
                bob_project.model_dump(mode="json"),
            ],
            "works": [
                alice_work.model_dump(mode="json"),
                bob_work.model_dump(mode="json"),
            ],
        }
    )
    return client, alice_project, bob_project, alice_work, bob_work


def test_work_update_rejects_foreign_existing_work_before_update():
    client, alice_project, _bob_project, _alice_work, bob_work = _authorization_graph()
    attempted_takeover = Work(
        id=bob_work.id,
        project_id=alice_project.id,
        title="Taken over",
    )

    with pytest.raises(PermissionError):
        WorkRepo(client).update(attempted_takeover, "alice")

    assert ("update", "works") not in client.executed
    stored_bob_work = next(row for row in client.rows["works"] if row["id"] == str(bob_work.id))
    assert stored_bob_work["project_id"] == str(bob_work.project_id)
    assert stored_bob_work["title"] == bob_work.title


def test_work_update_allows_owned_work():
    client, alice_project, _bob_project, alice_work, _bob_work = _authorization_graph()
    renamed = Work(
        id=alice_work.id,
        project_id=alice_project.id,
        title="Renamed by Alice",
    )

    updated = WorkRepo(client).update(renamed, "alice")

    assert updated == renamed
    assert ("update", "works") in client.executed


def test_work_update_rejects_reparenting_into_foreign_project_before_update():
    client, _alice_project, bob_project, alice_work, _bob_work = _authorization_graph()
    attempted_reparent = Work(
        id=alice_work.id,
        project_id=bob_project.id,
        title=alice_work.title,
    )

    with pytest.raises(PermissionError):
        WorkRepo(client).update(attempted_reparent, "alice")

    assert ("update", "works") not in client.executed
