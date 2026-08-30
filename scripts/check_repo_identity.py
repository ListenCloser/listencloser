#!/usr/bin/env python3
"""Fail when tracked text files retain pre-migration repository/product identities."""

from __future__ import annotations

import subprocess
from pathlib import Path

# Build the forbidden product slug from parts so this guard does not itself
# retain the exact legacy identifier it is responsible for rejecting.
LEGACY_IDENTIFIERS = (
    "hello" + "-" + "ai",
    "hello" + "-h7k6w5h4d-giancarloricci.vercel.app",
)


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def main() -> int:
    matches: list[str] = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            folded = line.casefold()
            for identifier in LEGACY_IDENTIFIERS:
                if identifier.casefold() in folded:
                    matches.append(f"{path}:{line_number}: {identifier}")

    if matches:
        print("Legacy repository/product identity references remain:")
        for match in matches:
            print(f"  {match}")
        return 1

    print("Repository identity is fully migrated to Listen Closer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
