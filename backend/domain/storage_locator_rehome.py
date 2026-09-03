"""Dry-run-first re-home tool for selected legacy Version Storage locators.

This is the mutating #593 recovery gate after ``storage_locator_audit`` and
``storage_locator_probe``. Operators must explicitly select Version IDs. The
command is dry-run by default and only writes with ``--apply``:

    uv run python -m domain.storage_locator_rehome --version <uuid>
    uv run python -m domain.storage_locator_rehome --version <uuid> --apply

The source Version and legacy object are never modified or deleted. Output is
privacy-safe: no raw Storage keys, filenames, owner IDs, or provider exception
text are emitted.
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
from domain.storage_locator_audit import (
    AuditRows,
    audit_storage_locator_rows,
    load_audit_rows,
)
from domain.storage_locator_policy import StorageLocatorKind, classify_version_storage_locator
from domain.storage_locator_probe import _download_selected_object

_REHOME_METHOD = "storage_locator_rehome_v1"
_STORAGE_BUCKET = "artifacts"
_SAFE_SUFFIX = re.compile(r"\.[A-Za-z0-9]{1,10}$")


def _rows_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in rows if row.get("id") is not None}


def _replacement_version_id(source_version_id: UUID) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"listencloser:{_REHOME_METHOD}:{source_version_id}",
    )


def _safe_source_suffix(storage_key: str) -> str:
    match = _SAFE_SUFFIX.search(storage_key)
    return match.group(0).lower() if match else ".bin"


def _locator_digest(storage_key: str) -> str:
    return hashlib.sha256(storage_key.encode("utf-8")).hexdigest()


def _extended_lineage(source: Version) -> list[UUID]:
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


def _authority_context(
    rows: AuditRows,
    detail: dict[str, Any],
) -> tuple[str, UUID, UUID]:
    artifacts = _rows_by_id(rows.artifacts)
    works = _rows_by_id(rows.works)
    projects = _rows_by_id(rows.projects)

    artifact_row = artifacts.get(str(detail.get("artifact_id")))
    if artifact_row is None:
        raise ValueError("selected Version has no authoritative Artifact")
    work_row = works.get(str(artifact_row.get("work_id")))
    if work_row is None:
        raise ValueError("selected Version has no authoritative Work")
    project_row = projects.get(str(work_row.get("project_id")))
    if project_row is None:
        raise ValueError("selected Version has no authoritative Project")

    owner_id = project_row.get("owner_id")
    if not owner_id:
        raise ValueError("selected Version has no authoritative owner")

    try:
        project_id = UUID(str(project_row["id"]))
        artifact_id = UUID(str(artifact_row["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("selected Version has an invalid authority graph") from exc

    return str(owner_id), project_id, artifact_id


def _replacement_storage_key(
    *,
    owner_id: str,
    project_id: UUID,
    artifact_id: UUID,
    replacement_id: UUID,
    source_storage_key: str,
) -> str:
    suffix = _safe_source_suffix(source_storage_key)
    return f"{owner_id}/{project_id}/{artifact_id}/{replacement_id.hex}{suffix}"


def _static_replacement_matches(
    existing: Version,
    source: Version,
    *,
    owner_id: str,
    storage_key: str,
    detail: dict[str, Any],
) -> bool:
    provenance = existing.metadata.get("storage_locator_rehome")
    return (
        existing.artifact_id == source.artifact_id
        and existing.parent_version_id == source.id
        and existing.lineage == _extended_lineage(source)
        and existing.storage_bucket == _STORAGE_BUCKET
        and existing.storage_key == storage_key
        and existing.created_by == owner_id
        and existing.produced_by_job_id is None
        and existing.label == source.label
        and isinstance(provenance, dict)
        and provenance.get("method") == _REHOME_METHOD
        and provenance.get("source_version_id") == str(source.id)
        and provenance.get("source_storage_key_sha256") == detail["storage_key_sha256"]
    )


def _verify_trusted_replacement(
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
    if not decision.trusted or decision.kind is not StorageLocatorKind.owner_upload:
        raise RuntimeError("replacement Version failed the trusted owner-upload policy")


def _verify_bytes(content: bytes, *, byte_size: int | None, sha256: str | None) -> bool:
    if byte_size is not None and len(content) != byte_size:
        return False
    if sha256 is not None and hashlib.sha256(content).hexdigest() != sha256:
        return False
    return True


def _remove_uploaded_destination(client: Client, storage_key: str) -> bool:
    try:
        client.storage.from_(_STORAGE_BUCKET).remove([storage_key])
    except Exception:
        return False
    return True


def _upload_destination(
    client: Client,
    *,
    storage_key: str,
    content: bytes,
    mime_type: str,
) -> None:
    try:
        client.storage.from_(_STORAGE_BUCKET).upload(
            storage_key,
            content,
            {"content-type": mime_type},
        )
    except Exception:
        raise RuntimeError("Storage re-home upload failed") from None


def _insert_replacement_version(client: Client, version: Version) -> Version:
    try:
        result = (
            client.table("artifact_versions")
            .insert(version.model_dump(mode="json"))
            .execute()
        )
    except Exception:
        raise RuntimeError("replacement Version publication failed") from None
    if not result.data:
        raise RuntimeError("replacement Version publication returned no row")
    try:
        return Version.model_validate(result.data[0])
    except ValidationError:
        raise RuntimeError("replacement Version publication returned an invalid row") from None


def _result_base(
    *,
    source: Version,
    detail: dict[str, Any],
    replacement_id: UUID,
    replacement_storage_key: str,
) -> dict[str, Any]:
    return {
        "source_version_id": str(source.id),
        "source_reason": detail["reason"],
        "source_legacy_path_class": detail["legacy_path_class"],
        "source_storage_key_sha256": detail["storage_key_sha256"],
        "replacement_version_id": str(replacement_id),
        "replacement_storage_key_sha256": _locator_digest(replacement_storage_key),
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
    version_rows = _rows_by_id(rows.versions)
    results: list[dict[str, Any]] = []

    for detail in selected:
        source_id = str(detail["version_id"])
        if detail["trusted"]:
            raise ValueError(f"selected Version is already trusted: {source_id}")

        source_row = version_rows.get(source_id)
        if source_row is None:
            raise ValueError(f"selected Version row not found: {source_id}")
        try:
            source = Version.model_validate(source_row)
        except ValidationError as exc:
            raise ValueError(f"selected Version row is invalid: {source_id}") from exc

        owner_id, project_id, artifact_id = _authority_context(rows, detail)
        mime_type = mimetypes.guess_type(source.storage_key)[0] or "application/octet-stream"
        if source.artifact_id != artifact_id:
            raise ValueError("selected Version does not match its authoritative Artifact")

        replacement_id = _replacement_version_id(source.id)
        replacement_storage_key = _replacement_storage_key(
            owner_id=owner_id,
            project_id=project_id,
            artifact_id=artifact_id,
            replacement_id=replacement_id,
            source_storage_key=source.storage_key,
        )
        base = _result_base(
            source=source,
            detail=detail,
            replacement_id=replacement_id,
            replacement_storage_key=replacement_storage_key,
        )

        existing_row = version_rows.get(str(replacement_id))
        if existing_row is not None:
            try:
                existing = Version.model_validate(existing_row)
            except ValidationError:
                raise RuntimeError("existing replacement Version row is invalid") from None
            if not _static_replacement_matches(
                existing,
                source,
                owner_id=owner_id,
                storage_key=replacement_storage_key,
                detail=detail,
            ):
                raise RuntimeError(
                    "deterministic replacement Version conflicts with existing state"
                )
            _verify_trusted_replacement(
                existing,
                owner_id=owner_id,
                project_id=project_id,
                artifact_id=artifact_id,
            )
            destination = _download_selected_object(
                client,
                existing.storage_bucket,
                existing.storage_key,
            )
            if destination is None or not _verify_bytes(
                destination,
                byte_size=existing.byte_size,
                sha256=existing.sha256,
            ):
                raise RuntimeError("existing replacement bytes failed integrity verification")
            results.append(
                {
                    **base,
                    "state": "already_applied",
                    "applied": True,
                    "actual_byte_size": len(destination),
                    "actual_sha256": hashlib.sha256(destination).hexdigest(),
                    "source_byte_size_matches": None,
                    "source_sha256_matches": None,
                    "destination_reused": True,
                }
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

        actual_byte_size = len(source_content)
        actual_sha256 = hashlib.sha256(source_content).hexdigest()
        byte_size_matches = (
            None if source.byte_size is None else source.byte_size == actual_byte_size
        )
        sha256_matches = None if source.sha256 is None else source.sha256 == actual_sha256
        if byte_size_matches is False or sha256_matches is False:
            results.append(
                {
                    **base,
                    "state": "source_metadata_mismatch",
                    "applied": False,
                    "actual_byte_size": actual_byte_size,
                    "actual_sha256": actual_sha256,
                    "source_byte_size_matches": byte_size_matches,
                    "source_sha256_matches": sha256_matches,
                    "destination_reused": False,
                }
            )
            continue

        replacement = Version(
            id=replacement_id,
            artifact_id=source.artifact_id,
            parent_version_id=source.id,
            lineage=_extended_lineage(source),
            storage_key=replacement_storage_key,
            storage_bucket=_STORAGE_BUCKET,
            byte_size=actual_byte_size,
            sha256=actual_sha256,
            created_by=owner_id,
            produced_by_job_id=None,
            label=source.label,
            metadata=_migration_metadata(source, detail),
        )
        _verify_trusted_replacement(
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
                    "actual_byte_size": actual_byte_size,
                    "actual_sha256": actual_sha256,
                    "source_byte_size_matches": byte_size_matches,
                    "source_sha256_matches": sha256_matches,
                    "destination_reused": False,
                }
            )
            continue

        destination = _download_selected_object(
            client,
            _STORAGE_BUCKET,
            replacement_storage_key,
        )
        uploaded = False
        if destination is None:
            _upload_destination(
                client,
                storage_key=replacement_storage_key,
                content=source_content,
                mime_type=mime_type,
            )
            uploaded = True
            destination = _download_selected_object(
                client,
                _STORAGE_BUCKET,
                replacement_storage_key,
            )

        if destination is None or not _verify_bytes(
            destination,
            byte_size=actual_byte_size,
            sha256=actual_sha256,
        ):
            if uploaded:
                _remove_uploaded_destination(client, replacement_storage_key)
            raise RuntimeError("replacement Storage bytes failed post-copy verification")

        try:
            created = _insert_replacement_version(client, replacement)
        except RuntimeError:
            if uploaded:
                _remove_uploaded_destination(client, replacement_storage_key)
            raise

        _verify_trusted_replacement(
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
                "actual_byte_size": actual_byte_size,
                "actual_sha256": actual_sha256,
                "source_byte_size_matches": byte_size_matches,
                "source_sha256_matches": sha256_matches,
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
        results = rehome_selected_storage(
            client,
            rows,
            args.version_ids,
            apply=args.apply,
        )
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None

    payload = {
        "apply": args.apply,
        "rehome_results": results,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
