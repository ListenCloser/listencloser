"""Read-only Storage byte/hash probe for selected legacy Version locators.

This is the second #593 recovery gate after ``storage_locator_audit``. It never
uploads, deletes, or mutates rows. Operators must explicitly select Version IDs:

    uv run python -m domain.storage_locator_probe --version <uuid>

The output never includes raw Storage keys, filenames, owner IDs, or provider
exception text. Missing source objects are reported as state, not errors that
could leak a locator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from storage3.exceptions import StorageApiError
from supabase import Client

from domain.repositories import get_supabase
from domain.storage_locator_audit import (
    AuditRows,
    audit_storage_locator_rows,
    load_audit_rows,
)


def _version_rows_by_id(rows: AuditRows) -> dict[str, dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in rows.versions:
        if row.get("id") is not None:
            rows_by_id[str(row["id"])] = row
    return rows_by_id


def _metadata_matches(actual: int | str, stored: int | str | None) -> bool | None:
    if stored is None:
        return None
    return actual == stored


def _is_missing_object_error(error: StorageApiError) -> bool:
    return error.code in {"NoSuchKey", "not_found"}


def _download_selected_object(client: Client, bucket: str, key: str) -> bytes | None:
    try:
        return client.storage.from_(bucket).download(key)
    except StorageApiError as exc:
        if _is_missing_object_error(exc):
            return None
        raise RuntimeError(
            "Storage probe failed without proving the source object is missing"
        ) from None
    except Exception:
        raise RuntimeError(
            "Storage probe failed without proving the source object is missing"
        ) from None


def probe_selected_storage(
    client: Client,
    rows: AuditRows,
    version_ids: list[str],
) -> list[dict[str, Any]]:
    """Download selected untrusted source objects and verify persisted metadata.

    This helper intentionally accepts explicit Version IDs only. Trusted modern
    locators do not need recovery probing and are rejected so this operator tool
    cannot become a general privileged Storage download path.
    """
    if not version_ids:
        raise ValueError("at least one Version must be selected")

    report = audit_storage_locator_rows(rows)
    selected = report.selected(version_ids)
    rows_by_id = _version_rows_by_id(rows)
    probes: list[dict[str, Any]] = []

    for detail in selected:
        version_id = detail["version_id"]
        if detail["trusted"]:
            raise ValueError(f"selected Version is already trusted: {version_id}")

        row = rows_by_id.get(version_id)
        if row is None:
            raise ValueError(f"selected Version row not found: {version_id}")

        storage_bucket = str(row.get("storage_bucket") or "")
        storage_key = str(row.get("storage_key") or "")
        stored_byte_size = detail["byte_size"]
        stored_sha256 = detail["stored_sha256"]
        content = _download_selected_object(client, storage_bucket, storage_key)

        if content is None:
            probes.append(
                {
                    "version_id": version_id,
                    "reason": detail["reason"],
                    "legacy_path_class": detail["legacy_path_class"],
                    "is_latest": detail["is_latest"],
                    "storage_key_sha256": detail["storage_key_sha256"],
                    "object_exists": False,
                    "actual_byte_size": None,
                    "actual_sha256": None,
                    "stored_byte_size": stored_byte_size,
                    "stored_sha256": stored_sha256,
                    "byte_size_matches": None,
                    "sha256_matches": None,
                }
            )
            continue

        actual_byte_size = len(content)
        actual_sha256 = hashlib.sha256(content).hexdigest()
        probes.append(
            {
                "version_id": version_id,
                "reason": detail["reason"],
                "legacy_path_class": detail["legacy_path_class"],
                "is_latest": detail["is_latest"],
                "storage_key_sha256": detail["storage_key_sha256"],
                "object_exists": True,
                "actual_byte_size": actual_byte_size,
                "actual_sha256": actual_sha256,
                "stored_byte_size": stored_byte_size,
                "stored_sha256": stored_sha256,
                "byte_size_matches": _metadata_matches(
                    actual_byte_size,
                    stored_byte_size,
                ),
                "sha256_matches": _metadata_matches(actual_sha256, stored_sha256),
            }
        )

    return probes


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    description = "Read-only byte/hash probe for selected legacy Version Storage objects."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--version",
        dest="version_ids",
        action="append",
        required=True,
        metavar="UUID",
        help="Probe this explicitly selected Version. Repeatable.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    client = get_supabase()
    if client is None:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    rows = load_audit_rows(client)
    try:
        probes = probe_selected_storage(client, rows, args.version_ids)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    payload = {
        "read_only": True,
        "selected_storage_probes": probes,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
