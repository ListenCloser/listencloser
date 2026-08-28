#!/usr/bin/env python3
"""Fail when a workflow uses a remote GitHub Action by a mutable ref."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(".github/workflows")
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def main() -> int:
    offenders: list[str] = []
    for workflow in sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml"))):
        for line_number, line in enumerate(workflow.read_text().splitlines(), start=1):
            match = USES_RE.match(line)
            if not match:
                continue
            action = match.group(1)
            if action.startswith("./") or action.startswith("docker://"):
                continue
            name, separator, ref = action.rpartition("@")
            if not separator or not name or not FULL_SHA_RE.fullmatch(ref):
                offenders.append(f"{workflow}:{line_number}: {action}")

    if offenders:
        print("Remote GitHub Actions must be pinned to full 40-character commit SHAs:")
        for offender in offenders:
            print(f"  {offender}")
        return 1

    print("All remote GitHub Actions are pinned to immutable commit SHAs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
