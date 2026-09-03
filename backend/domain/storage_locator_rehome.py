"""Dry-run-first re-home tool for selected legacy Version Storage locators.

This is the mutating #593 recovery gate after ``storage_locator_audit`` and
``storage_locator_probe``. Operators must explicitly select Version IDs. The
command is dry-run by default and writes only with ``--apply``:

    uv run python -m domain.storage_locator_rehome --version <uuid>
    uv run python -m domain.storage_locator_rehome --version <uuid> --apply

Source Versions and legacy objects are never modified or deleted. Output never
contains raw Storage keys, filenames, owner IDs, or provider exception text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError
from supabase import Client

from domain.models import Version
from domain.repositories import get_supabase
from domain.storage_locator_audit import AuditRows, audit_storage_locator_rows, load_audit_rows
from domain.storage_locator_policy import StorageLocatorKind, classify_version_storage_locator
from domain.storage_locator_probe import _download_selected_object

_REHOME_METHOD = "storage_locator_rehome_v1"
_STORAGE_BUCKET = "artifacts"
_SAFE_SUFFIX = re.compile(r"\.[A-Za-z0-9]{1,10}$")


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in rows if row.get("id") is not None}


def _replacement_id(source_id: UUID) -> UUID:
    return uuid5(NAMESPACE_URL, f"listencloser:{_REHOME_METHOD}:{source_id}")


def _safe_suffix(storage_key: str) -> str:
    match = _SAFE_SUFFIX.search(storage_key)
    return match.group(0).lower() if match else ".bin"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _lineage(source: Version) -> list[UUID]:
    lineage = list(source.lineage)
    if source.id not in lineage:
        lineage.append(source.id)
    return lineage


def _migration_metadata(source: Version, detail: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(source.metadata)
    metadata["storage_locator_rehome"] = {
        "method": _REHOME_METHOD,
        "source_version_id": str(source.id),
        "source_storage_key_sha256": detail["storage_key_sha256"],
        "source_reason": detail["reason"],
        "source_legacy_path_class": detail["legacy_path_class"],
    }
    return metadata


def _authority(rows: AuditRows, detail: dict[str, Any]) -> tuple[str, UUID, UUID]:
    artifacts = _by_id(rows.artifacts)
    works = _by_id(rows.works)
    projects = _by_id(rows.projects)

    artifact = artifacts.get(str(detail.get("artifact_id")))
    if artifact is None:
        raise ValueError("selected Version has no authoritative Artifact")
    work = works.get(str(artifact.get("work_id")))
    if work is None:
        raise ValueError("selected Version has no authoritative Work")
    project = projects.get(str(work.get("project_id")))
    if project is None:
        raise ValueError("selected Version has no authoritative Project")
    if not project.get("owner_id"):
        raise ValueError("selected Version has no authoritative owner")

    try:
        return (
            str(project["owner_id"]),
            UUID(str(project["id"])),
            UUID(str(artifact["id"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("selected Version has an invalid authority graph") from exc


def _destination_key(
    owner_id: str,
    project_id: UUID,
    artifact_id: UUID,
    replacement_id: UUID,
    source_key: str,
) -> str:
    return (
        f"{owner_id}/{project_id}/{artifact_id}/"
        f"{replacement_id.hex}{_safe_suffix(source_key)}"
    )


def _verify_trusted(
    version: Version,
    *,
    owner_id: str,
    project_id: UUID,
    artifact_id: UUID,
) -> None:
    decision = classify_version_storage_locator(
        version,
        owner_id=owner_id,
        project_id=project_id,
        artifact_id=artifact_id,
        allowed_job_ids=set(),
    )
    if not decision.trusted or decision.kind != StorageLocatorKind.owner_upload:
        raise RuntimeError("replacement Version failed the trusted owner-upload policy")


def _bytes_match(content: bytes, byte_size: int | None, sha256: str | None) -> bool:
    if byte_size is not None and len(content) != byte_size:
        return False
    return sha256 is None or hashlib.sha256(content).hexdigest() == sha256


def _upload(client: Client, key: str, content: bytes, mime_type: str) -> None:
    try:
        client.storage.from_(_STORAGE_BUCKET).upload(
            key,
            content,
            {"content-type": mime_type},
        )
    except Exception:
        raise RuntimeError("Storage re-home upload failed") from None


def _remove_new_destination(client: Client, key: str) -> None:
    try:
        client.storage.from_(_STORAGE_BUCKET).remove([key])
    except Exception:
        # The destination is deterministic and safe to leave for a later retry/GC.
        pass


def _insert(client: Client, version: Version) -> Version:
    try:
        result = (
            client.table("artifact_versions")
            .insert(version.model_dump(mode="json"))
            .execute()
        )
    except Exception:
        # Do not delete the copied bytes here. A network error can arrive after
        # Postgres committed the insert; removing bytes would then corrupt a
        # successfully published Version. The deterministic key/id make either
        # outcome safe to reconcile on the next invocation.
        raise RuntimeError("replacement Version publication outcome is unknown") from None
    if not result.data:
        raise RuntimeError("replacement Version publication returned no row")
    try:
        return Version.model_validate(result.data[0])
    except ValidationError:
        raise RuntimeError("replacement Version publication returned an invalid row") from None


def _replacement_matches(
    existing: Version,
    source: Version,
    *,
    owner_id: str,
    destination_key: str,
    detail: dict[str, Any],
) -> bool:
    provenance = existing.metadata.get("storage_locator_rehome")
    return (
        existing.artifact_id == source.artifact_id
        and existing.parent_version_id == source.id
        and existing.lineage == _lineage(source)
        and existing.storage_bucket == _STORAGE_BUCKET
        and existing.storage_key == destination_key
        and existing.byte_size is not None
        and existing.sha256 is not None
        and existing.created_by == owner_id
        and existing.produced_by_job_id is None
        and existing.label == source.label
        and isinstance(provenance, dict)
        and provenance.get("method") == _REHOME_METHOD
        and provenance.get("source_version_id") == str(source.id)
        and provenance.get("source_storage_key_sha256") == detail["storage_key_sha256"]
    )


def _base_result(
    source: Version,
    detail: dict[str, Any],
    replacement_id: UUID,
    destination_key: str,
) -> dict[str, Any]:
    return {
        "source_version_id": str(source.id),
        "source_reason": detail["reason"],
        "source_legacy_path_class": detail["legacy_path_class"],
        "source_storage_key_sha256": detail["storage_key_sha256"],
        "replacement_version_id": str(replacement_id),
        "replacement_storage_key_sha256": _digest(destination_key),
    }


def _existing_replacement_result(
    client: Client,
    existing: Version,
    source: Version,
    *,
    owner_id: str,
    project_id: UUID,
    artifact_id: UUID,
    destination_key: str,
    detail: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any]:
    if not _replacement_matches(
        existing,
        source,
        owner_id=owner_id,
        destination_key=destination_key,
        detail=detail,
    ):
        raise RuntimeError("deterministic replacement Version conflicts with existing state")
    _verify_trusted(
        existing,
        owner_id=owner_id,
        project_id=project_id,
        artifact_id=artifact_id,
    )
    content = _download_selected_object(client, existing.storage_bucket, existing.storage_key)
    if content is None or not _bytes_match(content, existing.byte_size, existing.sha256):
        raise RuntimeError("existing replacement bytes failed integrity verification")
    return {
        **base,
        "state": "already_applied",
        "applied": True,
        "actual_byte_size": len(content),
        "actual_sha256": hashlib.sha256(content).hexdigest(),
        "source_byte_size_matches": None,
        "source_sha256_matches": None,
        "destination_reused": True,
    }


def rehome_selected_storage(
    client: Client,
    rows: AuditRows,
    version_ids: list[str],
    *,
    apply: bool = False,
) -> list[dict[str, Any]]:
    """Plan or apply safe re-home for explicitly selected legacy Versions."""
    if not version_ids:
        raise ValueError("at least one Version must be selected")

    report = audit_storage_locator_rows(rows)
    selected = report.selected(version_ids)
    versions = _by_id(rows.versions)
    results: list[dict[str, Any]] = []

    for detail in selected:
        source_id = str(detail["version_id"])
        if detail["trusted"]:
            raise ValueError(f"selected Version is already trusted: {source_id}")
        source_row = versions.get(source_id)
        if source_row is None:
            raise ValueError(f"selected Version row not found: {source_id}")
        try:
            source = Version.model_validate(source_row)
        except ValidationError as exc:
            raise ValueError(f"selected Version row is invalid: {source_id}") from exc

        owner_id, project_id, artifact_id = _authority(rows, detail)
        if source.artifact_id != artifact_id:
            raise ValueError("selected Version does not match its authoritative Artifact")

        replacement_id = _replacement_id(source.id)
        destination_key = _destination_key(
            owner_id,
            project_id,
            artifact_id,
            replacement_id,
            source.storage_key,
        )
        base = _base_result(source, detail, replacement_id, destination_key)

        existing_row = versions.get(str(replacement_id))
        if existing_row is not None:
            try:
                existing = Version.model_validate(existing_row)
            except ValidationError:
                raise RuntimeError("existing replacement Version row is invalid") from None
            results.append(
                _existing_replacement_result(
                    client,
                    existing,
                    source,
                    owner_id=owner_id,
                    project_id=project_id,
                    artifact_id=artifact_id,
                    destination_key=destination_key,
                    detail=detail,
                    base=base,
                )
            )
            continue

        if not detail["is_latest"]:
            raise ValueError(
                f"selected Version is not latest and would resurrect historical state: {source_id}"
            )

        source_content = _download_selected_object(
            client,
            source.storage_bucket,
            source.storage_key,
        )
        if source_content is None:
            results.append(
                {
                    **base,
                    "state": "source_object_missing",
                    "applied": False,
                    "actual_byte_size": None,
                    "actual_sha256": None,
                    "source_byte_size_matches": None,
                    "source_sha256_matches": None,
                    "destination_reused": False,
                }
            )
            continue

        actual_size = len(source_content)
        actual_sha256 = hashlib.sha256(source_content).hexdigest()
        size_matches = None if source.byte_size is None else source.byte_size == actual_size
        sha_matches = None if source.sha256 is None else source.sha256 == actual_sha256
        if size_matches is False or sha_matches is False:
            results.append(
                {
                    **base,
                    "state": "source_metadata_mismatch",
                    "applied": False,
                    "actual_byte_size": actual_size,
                    "actual_sha256": actual_sha256,
                    "source_byte_size_matches": size_matches,
                    "source_sha256_matches": sha_matches,
                    "destination_reused": False,
                }
            )
            continue

        replacement = Version(
            id=replacement_id,
            artifact_id=source.artifact_id,
            parent_version_id=source.id,
            lineage=_lineage(source),
            storage_key=destination_key,
            storage_bucket=_STORAGE_BUCKET,
            byte_size=actual_size,
            sha256=actual_sha256,
            created_by=owner_id,
            produced_by_job_id=None,
            label=source.label,
            metadata=_migration_metadata(source, detail),
        )
        _verify_trusted(
            replacement,
            owner_id=owner_id,
            project_id=project_id,
            artifact_id=artifact_id,
        )

        if not apply:
            results.append(
                {
                    **base,
                    "state": "ready",
                    "applied": False,
                    "actual_byte_size": actual_size,
                    "actual_sha256": actual_sha256,
                    "source_byte_size_matches": size_matches,
                    "source_sha256_matches": sha_matches,
                    "destination_reused": False,
                }
            )
            continue

        destination = _download_selected_object(client, _STORAGE_BUCKET, destination_key)
        uploaded = False
        if destination is None:
            mime_type = mimetypes.guess_type(source.storage_key)[0] or "application/octet-stream"
            _upload(client, destination_key, source_content, mime_type)
            uploaded = True
            destination = _download_selected_object(client, _STORAGE_BUCKET, destination_key)

        if destination is None or not _bytes_match(destination, actual_size, actual_sha256):
            if uploaded:
                _remove_new_destination(client, destination_key)
            raise RuntimeError("replacement Storage bytes failed post-copy verification")

        created = _insert(client, replacement)
        _verify_trusted(
            created,
            owner_id=owner_id,
            project_id=project_id,
            artifact_id=artifact_id,
        )
        results.append(
            {
                **base,
                "state": "applied",
                "applied": True,
                "actual_byte_size": actual_size,
                "actual_sha256": actual_sha256,
                "source_byte_size_matches": size_matches,
                "source_sha256_matches": sha_matches,
                "destination_reused": not uploaded,
            }
        )

    return results


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply re-home for selected legacy Version Storage objects."
    )
    parser.add_argument(
        "--version",
        dest="version_ids",
        action="append",
        required=True,
        metavar="UUID",
        help="Select this legacy Version for re-home evaluation. Repeatable.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy verified bytes and publish replacement Versions. Default is dry-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    client = get_supabase()
    if client is None:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    rows = load_audit_rows(client)
    try:
        results = rehome_selected_storage(client, rows, args.version_ids, apply=args.apply)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None

    print(json.dumps({"apply": args.apply, "rehome_results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
