from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from uuid import UUID

import pytest

from domain.artifact_gc import (
    classify_object,
    collect_artifact_garbage,
    RetentionReason,
    StorageObject,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OWNER = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
JOB = UUID("33333333-3333-4333-8333-333333333333")
EXECUTION = "44444444-4444-4444-8444-444444444444"

PENDING_KEY = f"{OWNER}/{PROJECT}/pending/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.wav"
JOB_KEY = f"jobs/{JOB}/execution-{EXECUTION}/result.mid"


def _obj(key: str, *, age_hours: float = 48, size: int = 7) -> StorageObject:
    return StorageObject(key=key, created_at=NOW - timedelta(hours=age_hours), size_bytes=size)


def test_classifier_keeps_referenced_object() -> None:
    reason = classify_object(
        _obj(PENDING_KEY),
        referenced={("artifacts", PENDING_KEY)},
        active_job_ids=set(),
        bucket="artifacts",
        cutoff=NOW - timedelta(hours=24),
    )
    assert reason is RetentionReason.REFERENCED


def test_classifier_keeps_recent_pending_upload() -> None:
    reason = classify_object(
        _obj(PENDING_KEY, age_hours=1),
        referenced=set(),
        active_job_ids=set(),
        bucket="artifacts",
        cutoff=NOW - timedelta(hours=24),
    )
    assert reason is RetentionReason.TOO_RECENT


def test_classifier_keeps_active_job_output_even_when_old() -> None:
    reason = classify_object(
        _obj(JOB_KEY, age_hours=72),
        referenced=set(),
        active_job_ids={JOB},
        bucket="artifacts",
        cutoff=NOW - timedelta(hours=24),
    )
    assert reason is RetentionReason.ACTIVE_JOB


@pytest.mark.parametrize(
    "key",
    [
        f"jobs/{JOB}/attempt-2/result.mid",
        JOB_KEY,
        PENDING_KEY,
    ],
)
def test_classifier_marks_old_known_orphan_eligible(key: str) -> None:
    reason = classify_object(
        _obj(key),
        referenced=set(),
        active_job_ids=set(),
        bucket="artifacts",
        cutoff=NOW - timedelta(hours=24),
    )
    assert reason is RetentionReason.ELIGIBLE


def test_classifier_fails_closed_for_unknown_key_layout() -> None:
    reason = classify_object(
        _obj("legacy/or/unexpected/path.bin"),
        referenced=set(),
        active_job_ids=set(),
        bucket="artifacts",
        cutoff=NOW - timedelta(hours=24),
    )
    assert reason is RetentionReason.UNKNOWN_KEY_CLASS


def test_classifier_fails_closed_without_timestamp() -> None:
    reason = classify_object(
        StorageObject(key=PENDING_KEY, created_at=None, size_bytes=1),
        referenced=set(),
        active_job_ids=set(),
        bucket="artifacts",
        cutoff=NOW - timedelta(hours=24),
    )
    assert reason is RetentionReason.MISSING_TIMESTAMP


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.allowed_stages = None

    def select(self, _columns):
        return self

    def in_(self, _column, stages):
        self.allowed_stages = set(stages)
        return self

    def range(self, start, end):
        rows = self.rows
        if self.allowed_stages is not None:
            rows = [row for row in rows if row.get("stage") in self.allowed_stages]
        self.page = rows[start : end + 1]
        return self

    def execute(self):
        return SimpleNamespace(data=list(self.page))


class _Bucket:
    def __init__(self, rows):
        self.rows = dict(rows)
        self.remove_calls = 0

    def list(self, *, path, options):
        prefix = f"{path}/" if path else ""
        children = {}
        for key, row in self.rows.items():
            if not key.startswith(prefix):
                continue
            remainder = key[len(prefix) :]
            first, slash, _rest = remainder.partition("/")
            if slash:
                children[first] = {"name": first, "id": None, "metadata": None}
            else:
                children[first] = {"name": first, **row}
        ordered = [children[name] for name in sorted(children)]
        offset = options["offset"]
        limit = options["limit"]
        return ordered[offset : offset + limit]

    def remove(self, keys):
        self.remove_calls += 1
        for key in keys:
            self.rows.pop(key, None)


class _Storage:
    def __init__(self, bucket):
        self.bucket = bucket
        self.requested_buckets = []

    def from_(self, name):
        self.requested_buckets.append(name)
        assert name == "artifacts"
        return self.bucket


class _Client:
    def __init__(self, *, versions, jobs, objects):
        self.tables = {
            "artifact_versions": versions,
            "jobs": jobs,
        }
        self.bucket = _Bucket(objects)
        self.storage = _Storage(self.bucket)

    def table(self, name):
        return _Query(self.tables[name])


def _storage_row(*, age_hours: float, size: int = 10):
    created = NOW - timedelta(hours=age_hours)
    return {
        "id": "object-id",
        "created_at": created.isoformat(),
        "metadata": {"size": size},
    }


def test_dry_run_reports_aggregates_without_deleting_or_exposing_keys() -> None:
    client = _Client(
        versions=[{"storage_bucket": "artifacts", "storage_key": PENDING_KEY}],
        jobs=[{"id": str(JOB), "stage": "failed"}],
        objects={
            PENDING_KEY: _storage_row(age_hours=72),
            JOB_KEY: _storage_row(age_hours=72, size=20),
        },
    )

    summary = collect_artifact_garbage(client, now=NOW)

    assert summary.dry_run is True
    assert summary.scanned_count == 2
    assert summary.eligible_count == 1
    assert summary.eligible_bytes == 20
    assert summary.deleted_count == 0
    assert client.bucket.remove_calls == 0
    report = summary.to_json()
    assert PENDING_KEY not in report
    assert JOB_KEY not in report


def test_delete_mode_collects_old_orphan_and_is_idempotent() -> None:
    client = _Client(
        versions=[],
        jobs=[{"id": str(JOB), "stage": "failed"}],
        objects={JOB_KEY: _storage_row(age_hours=72, size=20)},
    )

    first = collect_artifact_garbage(client, now=NOW, dry_run=False)
    second = collect_artifact_garbage(client, now=NOW, dry_run=False)

    assert first.eligible_count == 1
    assert first.deleted_count == 1
    assert first.deleted_bytes == 20
    assert second.eligible_count == 0
    assert second.deleted_count == 0


def test_delete_mode_never_touches_recent_pending_or_active_job() -> None:
    client = _Client(
        versions=[],
        jobs=[{"id": str(JOB), "stage": "running"}],
        objects={
            PENDING_KEY: _storage_row(age_hours=1),
            JOB_KEY: _storage_row(age_hours=72),
        },
    )

    summary = collect_artifact_garbage(client, now=NOW, dry_run=False)

    assert summary.eligible_count == 0
    assert summary.deleted_count == 0
    assert client.bucket.remove_calls == 0
    assert summary.retained_by_reason["active_job"] == 1
    assert summary.retained_by_reason["too_recent"] == 1


def test_delete_mode_requires_conservative_grace() -> None:
    client = _Client(versions=[], jobs=[], objects={})
    with pytest.raises(ValueError, match="at least 24 hours"):
        collect_artifact_garbage(client, now=NOW, dry_run=False, grace_hours=6)


def test_collector_refuses_non_private_legacy_bucket() -> None:
    client = _Client(versions=[], jobs=[], objects={})
    with pytest.raises(ValueError, match="only owns"):
        collect_artifact_garbage(client, bucket="recordings", now=NOW)
