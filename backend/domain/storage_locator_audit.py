"""Read-only audit for historical Version Storage locators.

Run from ``backend/`` with service-role Supabase credentials:

    uv run python -m domain.storage_locator_audit
    uv run python -m domain.storage_locator_audit --version <version-uuid>

The default report contains aggregate counts only. ``--version`` is an explicit
operator drill-down for selected Versions and still never emits raw Storage
keys, filenames, or owner IDs. This command does not mutate database rows or
Storage objects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from supabase import Client

from domain.models import Version
from domain.repositories import get_supabase
from domain.storage_locator_policy import StorageLocatorKind, classify_version_storage_locator

_PAGE_SIZE = 1000


@dataclass(frozen=True)
class AuditRows:
    projects: list[dict[str, Any]]
    works: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    versions: list[dict[str, Any]]
    workflows: list[dict[str, Any]]
    jobs: list[dict[str, Any]]


@dataclass(frozen=True)
class LocatorAuditEntry:
    version_id: str
    artifact_id: str | None
    work_id: str | None
    project_id: str | None
    artifact_kind: str | None
    trusted: bool
    locator_kind: str
    reason: str
    legacy_path_class: str
    storage_bucket: str
    storage_key_sha256: str
    byte_size: int | None
    stored_sha256: str | None
    created_at: str | None
    is_latest: bool

    def selected_detail(self) -> dict[str, Any]:
        """Return privacy-safe detail for an explicitly selected Version."""

        return {
            "version_id": self.version_id,
            "artifact_id": self.artifact_id,
            "work_id": self.work_id,
            "project_id": self.project_id,
            "artifact_kind": self.artifact_kind,
            "trusted": self.trusted,
            "locator_kind": self.locator_kind,
            "reason": self.reason,
            "legacy_path_class": self.legacy_path_class,
            "storage_bucket": self.storage_bucket,
            "storage_key_sha256": self.storage_key_sha256,
            "byte_size": self.byte_size,
            "stored_sha256": self.stored_sha256,
            "created_at": self.created_at,
            "is_latest": self.is_latest,
        }


@dataclass(frozen=True)
class LocatorAuditReport:
    entries: tuple[LocatorAuditEntry, ...]

    def summary(self) -> dict[str, Any]:
        candidates = [entry for entry in self.entries if not entry.trusted]
        trusted = [entry for entry in self.entries if entry.trusted]
        return {
            "read_only": True,
            "total_versions": len(self.entries),
            "trusted_versions": len(trusted),
            "candidate_versions": len(candidates),
            "latest_candidate_versions": sum(entry.is_latest for entry in candidates),
            "affected_works": len({entry.work_id for entry in candidates if entry.work_id}),
            "affected_projects": len(
                {entry.project_id for entry in candidates if entry.project_id}
            ),
            "trusted_locator_kinds": _counts(entry.locator_kind for entry in trusted),
            "candidate_reasons": _counts(entry.reason for entry in candidates),
            "candidate_artifact_kinds": _counts(
                entry.artifact_kind or "unknown" for entry in candidates
            ),
            "candidate_path_classes": _counts(entry.legacy_path_class for entry in candidates),
        }

    def selected(self, version_ids: list[str]) -> list[dict[str, Any]]:
        by_id = {entry.version_id: entry for entry in self.entries}
        missing = [version_id for version_id in version_ids if version_id not in by_id]
        if missing:
            raise ValueError(f"selected Version not found: {', '.join(missing)}")
        return [by_id[version_id].selected_detail() for version_id in version_ids]


def _counts(values) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _read_all_pages(client: Client, table: str, columns: str = "*") -> list[dict[str, Any]]:
    """Read an entire table without accepting the default PostgREST row cap."""

    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        result = (
            client.table(table)
            .select(columns)
            .order("id")
            .range(start, start + _PAGE_SIZE - 1)
            .execute()
        )
        page = list(result.data or [])
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            return rows
        start += _PAGE_SIZE


def load_audit_rows(client: Client) -> AuditRows:
    """Load only the persisted graph needed to evaluate locator authority."""

    return AuditRows(
        projects=_read_all_pages(client, "projects", "id,owner_id"),
        works=_read_all_pages(client, "works", "id,project_id"),
        artifacts=_read_all_pages(client, "artifacts", "id,work_id,kind"),
        versions=_read_all_pages(client, "artifact_versions"),
        workflows=_read_all_pages(client, "workflows", "id,project_id,target_version_id"),
        jobs=_read_all_pages(client, "jobs", "id,workflow_id"),
    )


def _as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _legacy_path_class(storage_key: str) -> str:
    parts = storage_key.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return "unsafe"
    if parts[0] == "jobs":
        return "worker_job"
    if parts[0] == "transcriptions":
        return "transcriptions"
    if parts[0] == "it":
        return "integration"
    if _as_uuid(parts[0]) is not None:
        return "uuid_prefix"
    return "other"


def _locator_key_digest(storage_key: str) -> str:
    return hashlib.sha256(storage_key.encode("utf-8")).hexdigest()


def _row_version_id(row: dict[str, Any]) -> str:
    value = row.get("id")
    return str(value) if value is not None else "<missing>"


def _latest_version_ids(versions: list[Version]) -> set[UUID]:
    latest: dict[UUID, Version] = {}
    for version in versions:
        current = latest.get(version.artifact_id)
        if current is None or (version.created_at, str(version.id)) > (
            current.created_at,
            str(current.id),
        ):
            latest[version.artifact_id] = version
    return {version.id for version in latest.values()}


def audit_storage_locator_rows(rows: AuditRows) -> LocatorAuditReport:
    """Classify every Version against the exact production locator policy."""

    projects = {str(row["id"]): row for row in rows.projects if row.get("id") is not None}
    works = {str(row["id"]): row for row in rows.works if row.get("id") is not None}
    artifacts = {str(row["id"]): row for row in rows.artifacts if row.get("id") is not None}

    valid_versions: dict[str, Version] = {}
    invalid_version_ids: set[str] = set()
    for row in rows.versions:
        version_id = _row_version_id(row)
        try:
            valid_versions[version_id] = Version.model_validate(row)
        except ValidationError:
            invalid_version_ids.add(version_id)

    version_work: dict[str, str] = {}
    for version_id, version in valid_versions.items():
        artifact = artifacts.get(str(version.artifact_id))
        if not artifact:
            continue
        work_id = artifact.get("work_id")
        if work_id is not None and str(work_id) in works:
            version_work[version_id] = str(work_id)

    workflow_work: dict[str, str] = {}
    for workflow in rows.workflows:
        workflow_id = workflow.get("id")
        target_version_id = workflow.get("target_version_id")
        if workflow_id is None or target_version_id is None:
            continue
        work_id = version_work.get(str(target_version_id))
        if not work_id:
            continue
        work = works[work_id]
        if str(workflow.get("project_id")) != str(work.get("project_id")):
            continue
        workflow_work[str(workflow_id)] = work_id

    allowed_jobs_by_work: dict[str, set[UUID]] = defaultdict(set)
    for job in rows.jobs:
        job_id = _as_uuid(job.get("id"))
        work_id = workflow_work.get(str(job.get("workflow_id")))
        if job_id is not None and work_id is not None:
            allowed_jobs_by_work[work_id].add(job_id)

    latest_ids = _latest_version_ids(list(valid_versions.values()))
    entries: list[LocatorAuditEntry] = []

    for row in rows.versions:
        version_id = _row_version_id(row)
        storage_key = str(row.get("storage_key") or "")
        base = {
            "version_id": version_id,
            "artifact_id": str(row.get("artifact_id")) if row.get("artifact_id") else None,
            "work_id": None,
            "project_id": None,
            "artifact_kind": None,
            "trusted": False,
            "locator_kind": StorageLocatorKind.untrusted.value,
            "legacy_path_class": _legacy_path_class(storage_key),
            "storage_bucket": str(row.get("storage_bucket") or ""),
            "storage_key_sha256": _locator_key_digest(storage_key),
            "byte_size": row.get("byte_size"),
            "stored_sha256": row.get("sha256"),
            "created_at": str(row.get("created_at")) if row.get("created_at") else None,
            "is_latest": False,
        }

        if version_id in invalid_version_ids:
            entries.append(LocatorAuditEntry(reason="invalid_version_row", **base))
            continue

        version = valid_versions[version_id]
        base["is_latest"] = version.id in latest_ids
        artifact = artifacts.get(str(version.artifact_id))
        if artifact is None:
            entries.append(LocatorAuditEntry(reason="missing_artifact", **base))
            continue

        base["artifact_kind"] = str(artifact.get("kind")) if artifact.get("kind") else None
        work_id = artifact.get("work_id")
        base["work_id"] = str(work_id) if work_id is not None else None
        work = works.get(str(work_id))
        if work is None:
            entries.append(LocatorAuditEntry(reason="missing_work", **base))
            continue

        project_id = work.get("project_id")
        base["project_id"] = str(project_id) if project_id is not None else None
        project = projects.get(str(project_id))
        if project is None:
            entries.append(LocatorAuditEntry(reason="missing_project", **base))
            continue

        owner_id = project.get("owner_id")
        project_uuid = _as_uuid(project_id)
        artifact_uuid = _as_uuid(artifact.get("id"))
        if not owner_id or project_uuid is None or artifact_uuid is None:
            entries.append(LocatorAuditEntry(reason="invalid_authority_graph", **base))
            continue

        decision = classify_version_storage_locator(
            version,
            owner_id=str(owner_id),
            project_id=project_uuid,
            artifact_id=artifact_uuid,
            allowed_job_ids=allowed_jobs_by_work.get(str(work_id), set()),
        )
        entries.append(
            LocatorAuditEntry(
                trusted=decision.trusted,
                locator_kind=decision.kind.value,
                reason=decision.reason,
                **{
                    key: value
                    for key, value in base.items()
                    if key not in {"trusted", "locator_kind"}
                },
            )
        )

    return LocatorAuditReport(entries=tuple(entries))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only audit of persisted Version Storage locator authority.",
    )
    parser.add_argument(
        "--version",
        dest="version_ids",
        action="append",
        default=[],
        metavar="UUID",
        help="Include privacy-safe detail for this explicitly selected Version. Repeatable.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    client = get_supabase()
    if client is None:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    report = audit_storage_locator_rows(load_audit_rows(client))
    payload: dict[str, Any] = {"summary": report.summary()}
    if args.version_ids:
        try:
            payload["selected"] = report.selected(args.version_ids)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
