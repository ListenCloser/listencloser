from types import SimpleNamespace
from uuid import UUID, uuid4

import domain.capabilities as capabilities
from domain.models import Capability, Job


class _EntityQuery:
    def __init__(self, rows_by_version: dict[str, list[dict]]):
        self._rows_by_version = rows_by_version
        self._version_id: str | None = None

    def select(self, *_args):
        return self

    def eq(self, column: str, value: str):
        if column == "version_id":
            self._version_id = value
        return self

    def execute(self):
        return SimpleNamespace(data=list(self._rows_by_version.get(self._version_id or "", [])))


class _Client:
    def __init__(self, rows_by_version: dict[str, list[dict]]):
        self.rows_by_version = rows_by_version

    def table(self, name: str):
        assert name == "entities"
        return _EntityQuery(self.rows_by_version)


def _note(pitch: int, start: float, end: float) -> dict:
    return {
        "note_pitch": pitch,
        "note_start_seconds": start,
        "note_end_seconds": end,
        "note_velocity": 64,
    }


def test_compare_persists_literal_diff_without_fabricated_confidence(monkeypatch):
    version_a = uuid4()
    version_b = uuid4()
    captured: dict[str, object] = {}

    class _AlignmentRepo:
        def __init__(self, _client):
            pass

        def create(self, alignment, owner_id: str):
            assert owner_id == "owner-1"
            captured["alignment"] = alignment
            return alignment

    class _InsightRepo:
        def __init__(self, _client):
            pass

        def create(self, insight, owner_id: str):
            assert owner_id == "owner-1"
            captured["insight"] = insight
            return insight

    monkeypatch.setattr(capabilities, "AlignmentRepo", _AlignmentRepo)
    monkeypatch.setattr(capabilities, "InsightRepo", _InsightRepo)
    monkeypatch.setattr(capabilities, "_resolve_owner_id", lambda _client, _workflow_id: "owner-1")
    monkeypatch.setattr(capabilities, "_update_progress", lambda *_args, **_kwargs: None)

    job = Job(
        workflow_id=uuid4(),
        capability=Capability(name="compare", version="1.0"),
        input_version_ids=[version_a, version_b],
    )
    client = _Client(
        {
            str(version_a): [_note(60, 0.0, 1.0), _note(64, 2.0, 3.0)],
            str(version_b): [_note(60, 0.0, 1.0), _note(67, 2.0, 3.0)],
        }
    )

    output_ids = capabilities.handle_compare(job, client)

    alignment = captured["alignment"]
    insight = captured["insight"]
    assert alignment.confidence is None
    assert insight.confidence is None
    assert alignment.mapping_data == {
        "added_count": 1,
        "removed_count": 1,
        "modified_count": 0,
        "unchanged_count": 1,
        "version_a_note_count": 2,
        "version_b_note_count": 2,
    }
    assert insight.evidence["added_count"] == 1
    assert insight.evidence["removed_count"] == 1
    assert len(output_ids) == 2
    assert all(UUID(value) for value in output_ids)
