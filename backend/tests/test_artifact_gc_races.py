from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from domain.artifact_gc import collect_artifact_garbage


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OWNER = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
PENDING_KEY = f"{OWNER}/{PROJECT}/pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav"


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _columns):
        return self

    def in_(self, _column, _stages):
        return self

    def range(self, start, end):
        self.page = self.rows[start : end + 1]
        return self

    def execute(self):
        return SimpleNamespace(data=list(self.page))


class _Bucket:
    def __init__(self):
        self.remove_calls = 0

    def list(self, *, path, options):
        if path:
            return []
        return [
            {
                "name": OWNER,
                "id": None,
                "metadata": None,
            }
        ]

    def remove(self, _keys):
        self.remove_calls += 1


class _NestedBucket(_Bucket):
    def list(self, *, path, options):
        if path == "":
            return [{"name": OWNER, "id": None, "metadata": None}]
        if path == OWNER:
            return [{"name": PROJECT, "id": None, "metadata": None}]
        if path == f"{OWNER}/{PROJECT}":
            return [{"name": "pending", "id": None, "metadata": None}]
        if path == f"{OWNER}/{PROJECT}/pending":
            return [
                {
                    "name": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav",
                    "id": "object-id",
                    "created_at": (NOW - timedelta(hours=72)).isoformat(),
                    "metadata": {"size": 10},
                }
            ]
        return []


class _Storage:
    def __init__(self, bucket):
        self.bucket = bucket

    def from_(self, name):
        assert name == "artifacts"
        return self.bucket


class _RaceClient:
    def __init__(self):
        self.bucket = _NestedBucket()
        self.storage = _Storage(self.bucket)
        self.version_reads = 0

    def table(self, name):
        if name == "artifact_versions":
            self.version_reads += 1
            rows = (
                []
                if self.version_reads == 1
                else [{"storage_bucket": "artifacts", "storage_key": PENDING_KEY}]
            )
            return _Query(rows)
        if name == "jobs":
            return _Query([])
        raise AssertionError(name)


def test_delete_mode_rechecks_references_before_storage_mutation() -> None:
    client = _RaceClient()

    summary = collect_artifact_garbage(client, now=NOW, dry_run=False)

    assert summary.eligible_count == 0
    assert summary.deleted_count == 0
    assert summary.retained_by_reason["referenced"] == 1
    assert client.bucket.remove_calls == 0
