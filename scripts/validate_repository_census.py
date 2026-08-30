#!/usr/bin/env python3
"""Validate the structural contract of audit/repository-census.json.

This is intentionally dependency-free and does not judge whether a finding's
classification is correct. It prevents malformed/ambiguous census entries from
becoming another hand-maintained documentation format.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("audit/repository-census.json")
CLASSIFICATIONS = {
    "DELETE",
    "CONSOLIDATE",
    "RENAME_MOVE",
    "REFACTOR",
    "KEEP",
    "INVESTIGATE",
}
FINDING_REQUIRED = {
    "id",
    "subsystem",
    "path",
    "kind",
    "classification",
    "evidence",
    "canonical_replacement_or_owner",
    "risk",
    "verification_before_change",
}
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")


def _error(errors: list[str], location: str, message: str) -> None:
    errors.append(f"{location}: {message}")


def _require_nonempty_string(
    value: Any, *, errors: list[str], location: str
) -> None:
    if not isinstance(value, str) or not value.strip():
        _error(errors, location, "must be a non-empty string")


def _require_string_list(
    value: Any, *, errors: list[str], location: str, allow_empty: bool = False
) -> None:
    if not isinstance(value, list):
        _error(errors, location, "must be an array")
        return
    if not allow_empty and not value:
        _error(errors, location, "must contain at least one item")
    for index, item in enumerate(value):
        _require_nonempty_string(item, errors=errors, location=f"{location}[{index}]")
    if all(isinstance(item, str) for item in value) and len(value) != len(set(value)):
        _error(errors, location, "must not contain duplicate items")


def validate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root: must be an object"]

    if data.get("schema_version") != 1:
        _error(errors, "schema_version", "must equal 1")

    baseline_sha = data.get("baseline_sha")
    if not isinstance(baseline_sha, str) or not HEX_SHA.fullmatch(baseline_sha):
        _error(errors, "baseline_sha", "must be a lowercase 40-character git SHA")

    _require_nonempty_string(data.get("generated_at"), errors=errors, location="generated_at")
    _require_nonempty_string(data.get("status"), errors=errors, location="status")

    declared_classifications = data.get("classification_values")
    if not isinstance(declared_classifications, list) or set(declared_classifications) != CLASSIFICATIONS:
        _error(
            errors,
            "classification_values",
            f"must contain exactly {sorted(CLASSIFICATIONS)}",
        )

    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        _error(errors, "coverage", "must be an object")
    else:
        _require_string_list(
            coverage.get("completed_passes"),
            errors=errors,
            location="coverage.completed_passes",
            allow_empty=True,
        )
        _require_string_list(
            coverage.get("remaining_passes"),
            errors=errors,
            location="coverage.remaining_passes",
            allow_empty=True,
        )

    findings = data.get("findings")
    if not isinstance(findings, list):
        _error(errors, "findings", "must be an array")
        return errors
    if not findings:
        _error(errors, "findings", "must contain at least one finding")
        return errors

    seen_ids: set[str] = set()
    for index, finding in enumerate(findings):
        location = f"findings[{index}]"
        if not isinstance(finding, dict):
            _error(errors, location, "must be an object")
            continue

        missing = sorted(FINDING_REQUIRED - finding.keys())
        if missing:
            _error(errors, location, f"missing required keys: {', '.join(missing)}")

        for key in ("id", "subsystem", "path", "kind", "canonical_replacement_or_owner"):
            _require_nonempty_string(finding.get(key), errors=errors, location=f"{location}.{key}")

        finding_id = finding.get("id")
        if isinstance(finding_id, str):
            if finding_id in seen_ids:
                _error(errors, f"{location}.id", f"duplicate id {finding_id!r}")
            seen_ids.add(finding_id)

        classification = finding.get("classification")
        if classification not in CLASSIFICATIONS:
            _error(
                errors,
                f"{location}.classification",
                f"must be one of {sorted(CLASSIFICATIONS)}",
            )

        _require_string_list(
            finding.get("evidence"), errors=errors, location=f"{location}.evidence"
        )
        _require_string_list(
            finding.get("risk"), errors=errors, location=f"{location}.risk"
        )
        _require_string_list(
            finding.get("verification_before_change"),
            errors=errors,
            location=f"{location}.verification_before_change",
        )

    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"repository census not found: {path}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"invalid JSON in {path}: {exc}", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        print(f"repository census validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        f"repository census valid: {len(data['findings'])} findings at {data['baseline_sha']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
