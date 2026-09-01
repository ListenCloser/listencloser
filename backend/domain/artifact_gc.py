"""Conservative garbage collection for unreferenced private artifacts.

The collector is intentionally fail-closed:

* ``artifact_versions`` is the authoritative durable reference set.
* queued/claimed/running jobs protect all recognized job-attempt keys.
* pending direct uploads and job outputs need an age grace period.
* unknown key layouts or missing timestamps are retained.
* dry-run is the default; delete mode requires at least 24 hours of grace.
* reports contain aggregate counts/bytes only, never object keys or filenames.

Run from the backend project:

    uv run python -m domain.artifact_gc
    uv run python -m domain.artifact_gc --delete --grace-hours 24
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

_ARTIFACT_BUCKET = "artifacts"
_DEFAULT_GRACE_HOURS = 24.0
_MIN_DELETE_GRACE_HOURS = 24.0
_PAGE_SIZE = 1000
_DELETE_BATCH_SIZE = 100
_ACTIVE_JOB_STAGES = ("queued", "claimed", "running")

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
_PENDING_UPLOAD_RE = re.compile(
    rf"^(?P<owner>{_UUID})/(?P<project>{_UUID})/pending/[0-9a-fA-F]{{32}}\.[a-zA-Z0-9]+$"
)
_JOB_ATTEMPT_RE = re.compile(rf"^jobs/(?P<job>{_UUID})/attempt-\d+/.+$")
_JOB_EXECUTION_RE = re.compile(rf"^jobs/(?P<job>{_UUID})/execution-{_UUID}/.+$")

logger = logging.getLogger("artifact_gc")


class RetentionReason(StrEnum):
    REFERENCED = "referenced"
    ACTIVE_JOB = "active_job"
    TOO_RECENT = "too_recent"
    MISSING_TIMESTAMP = "missing_timestamp"
    UNKNOWN_KEY_CLASS = "unknown_key_class"
    ELIGIBLE = "eligible"


@dataclass(frozen=True)
class StorageObject:
    key: str
    created_at: datetime | None
    size_bytes: int = 0


@dataclass(frozen=True)
class GcSummary:
    dry_run: bool
    bucket: str
    grace_hours: float
    scanned_count: int
    scanned_bytes: int
    eligible_count: int
    eligible_bytes: int
    deleted_count: int
    deleted_bytes: int
    delete_error_count: int
    retained_by_reason: dict[str, int]

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _object_size(row: dict[str, Any]) -> int:
    metadata = row.get("metadata")
    value = metadata.get("size") if isinstance(metadata, dict) else None
    if value is None:
        value = row.get("size")
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _job_id_from_key(key: str) -> UUID | None:
    for pattern in (_JOB_ATTEMPT_RE, _JOB_EXECUTION_RE):
        match = pattern.fullmatch(key)
        if match:
            return UUID(match.group("job"))
    return None


def _is_recognized_key(key: str) -> bool:
    return bool(
        _PENDING_UPLOAD_RE.fullmatch(key)
        or _JOB_ATTEMPT_RE.fullmatch(key)
        or _JOB_EXECUTION_RE.fullmatch(key)
    )


def classify_object(
    obj: StorageObject,
    *,
    referenced: set[tuple[str, str]],
    active_job_ids: set[UUID],
    bucket: str,
    cutoff: datetime,
) -> RetentionReason:
    """Classify one object without mutating Storage."""

    if (bucket, obj.key) in referenced:
        return RetentionReason.REFERENCED

    job_id = _job_id_from_key(obj.key)
    if job_id is not None and job_id in active_job_ids:
        return RetentionReason.ACTIVE_JOB

    if not _is_recognized_key(obj.key):
        return RetentionReason.UNKNOWN_KEY_CLASS

    if obj.created_at is None:
        return RetentionReason.MISSING_TIMESTAMP

    created_at = obj.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if created_at > cutoff:
        return RetentionReason.TOO_RECENT

    return RetentionReason.ELIGIBLE


def _select_all(
    client: Any,
    table: str,
    columns: str,
    *,
    active_stages: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = client.table(table).select(columns)
        if active_stages is not None:
            query = query.in_("stage", list(active_stages))
        result = query.range(offset, offset + _PAGE_SIZE - 1).execute()
        page = list(result.data or [])
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            return rows
        offset += len(page)


def load_referenced_versions(client: Any, *, bucket: str) -> set[tuple[str, str]]:
    """Load the complete authoritative Version reference set before deletion."""

    rows = _select_all(client, "artifact_versions", "storage_bucket,storage_key")
    refs: set[tuple[str, str]] = set()
    for row in rows:
        storage_bucket = row.get("storage_bucket")
        storage_key = row.get("storage_key")
        if storage_bucket and storage_key:
            refs.add((str(storage_bucket), str(storage_key)))
    return refs


def load_active_job_ids(client: Any) -> set[UUID]:
    rows = _select_all(
        client,
        "jobs",
        "id,stage",
        active_stages=_ACTIVE_JOB_STAGES,
    )
    active: set[UUID] = set()
    for row in rows:
        if row.get("stage") not in _ACTIVE_JOB_STAGES:
            continue
        try:
            active.add(UUID(str(row["id"])))
        except (KeyError, TypeError, ValueError):
            # A malformed active-job row means the inventory cannot safely
            # identify its objects. Abort rather than weakening protection.
            raise RuntimeError("active jobs query returned an invalid id") from None
    return active


def _is_storage_folder(row: dict[str, Any]) -> bool:
    # Supabase Storage returns folders as rows with no id/metadata. Do not
    # mistake an object whose metadata is missing for a folder if it has an id.
    return row.get("id") is None and row.get("metadata") is None


def list_storage_objects(client: Any, *, bucket: str) -> list[StorageObject]:
    """Recursively inventory a Storage bucket before any deletion is attempted."""

    storage = client.storage.from_(bucket)
    pending = deque([""])
    objects: list[StorageObject] = []

    while pending:
        prefix = pending.popleft()
        offset = 0
        while True:
            page = storage.list(
                path=prefix,
                options={
                    "limit": _PAGE_SIZE,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
            rows = list(page or [])
            for raw in rows:
                row = dict(raw)
                name = str(row.get("name") or "")
                if not name:
                    raise RuntimeError("storage inventory returned an unnamed entry")
                key = f"{prefix}/{name}" if prefix else name
                if _is_storage_folder(row):
                    pending.append(key)
                    continue
                created_at = _parse_datetime(row.get("created_at") or row.get("updated_at"))
                objects.append(
                    StorageObject(
                        key=key,
                        created_at=created_at,
                        size_bytes=_object_size(row),
                    )
                )
            if len(rows) < _PAGE_SIZE:
                break
            offset += len(rows)

    return objects


def _remove_batches(storage: Any, candidates: list[StorageObject]) -> tuple[int, int, int]:
    deleted_count = 0
    deleted_bytes = 0
    delete_error_count = 0
    for start in range(0, len(candidates), _DELETE_BATCH_SIZE):
        batch = candidates[start : start + _DELETE_BATCH_SIZE]
        try:
            storage.remove([obj.key for obj in batch])
        except Exception:
            # Do not log exception text here: provider errors may embed object
            # paths. The next run remains idempotent and will rediscover objects
            # whose deletion did not complete.
            delete_error_count += len(batch)
            logger.warning("artifact_gc.delete_batch_failed", extra={"count": len(batch)})
            continue
        deleted_count += len(batch)
        deleted_bytes += sum(obj.size_bytes for obj in batch)
    return deleted_count, deleted_bytes, delete_error_count


def collect_artifact_garbage(
    client: Any,
    *,
    bucket: str = _ARTIFACT_BUCKET,
    grace_hours: float = _DEFAULT_GRACE_HOURS,
    dry_run: bool = True,
    now: datetime | None = None,
) -> GcSummary:
    """Inventory, classify, and optionally delete unreferenced private artifacts."""

    if bucket != _ARTIFACT_BUCKET:
        raise ValueError("artifact GC only owns the private 'artifacts' bucket")
    if grace_hours <= 0:
        raise ValueError("grace_hours must be positive")
    if not dry_run and grace_hours < _MIN_DELETE_GRACE_HOURS:
        raise ValueError(
            f"delete mode requires at least {_MIN_DELETE_GRACE_HOURS:g} hours of grace"
        )

    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    cutoff = current_time.astimezone(UTC) - timedelta(hours=grace_hours)

    # Complete all reads before the first delete. If any inventory/reference
    # query fails, the function raises and Storage remains untouched.
    referenced = load_referenced_versions(client, bucket=bucket)
    active_jobs = load_active_job_ids(client)
    objects = list_storage_objects(client, bucket=bucket)

    reasons: Counter[RetentionReason] = Counter()
    candidates: list[StorageObject] = []
    for obj in objects:
        reason = classify_object(
            obj,
            referenced=referenced,
            active_job_ids=active_jobs,
            bucket=bucket,
            cutoff=cutoff,
        )
        reasons[reason] += 1
        if reason is RetentionReason.ELIGIBLE:
            candidates.append(obj)

    deleted_count = 0
    deleted_bytes = 0
    delete_error_count = 0
    if not dry_run and candidates:
        # Refresh durable protections immediately before mutating Storage. This
        # narrows the race where an old pending upload is finalized or a Job is
        # re-queued while the bucket inventory is being walked.
        latest_referenced = load_referenced_versions(client, bucket=bucket)
        latest_active_jobs = load_active_job_ids(client)
        candidates = [
            obj
            for obj in candidates
            if classify_object(
                obj,
                referenced=latest_referenced,
                active_job_ids=latest_active_jobs,
                bucket=bucket,
                cutoff=cutoff,
            )
            is RetentionReason.ELIGIBLE
        ]
        deleted_count, deleted_bytes, delete_error_count = _remove_batches(
            client.storage.from_(bucket),
            candidates,
        )

    retained = {
        reason.value: count
        for reason, count in sorted(reasons.items(), key=lambda item: item[0].value)
        if reason is not RetentionReason.ELIGIBLE
    }
    summary = GcSummary(
        dry_run=dry_run,
        bucket=bucket,
        grace_hours=grace_hours,
        scanned_count=len(objects),
        scanned_bytes=sum(obj.size_bytes for obj in objects),
        eligible_count=len(candidates),
        eligible_bytes=sum(obj.size_bytes for obj in candidates),
        deleted_count=deleted_count,
        deleted_bytes=deleted_bytes,
        delete_error_count=delete_error_count,
        retained_by_reason=retained,
    )
    logger.info("artifact_gc.summary", extra=asdict(summary))
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=_DEFAULT_GRACE_HOURS,
        help="minimum object age before eligibility (default: 24)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="delete eligible objects; default is aggregate-only dry-run",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    from .repositories import get_supabase

    client = get_supabase()
    if client is None:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    summary = collect_artifact_garbage(
        client,
        grace_hours=args.grace_hours,
        dry_run=not args.delete,
    )
    print(summary.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
