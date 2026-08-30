#!/usr/bin/env python3
"""Compatibility wrapper for production deploy-scope classification.

PR merge evidence now lives entirely in `.github/workflows/build.yml`; this file
must not regain GitHub API polling or merge-policy responsibilities. It remains
briefly because Production Smoke still invokes the historical command name.
"""

from __future__ import annotations

import argparse

from classify_production_scope import main as classify_production_scope


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-scope", action="store_true")
    args = parser.parse_args()
    if not args.production_scope:
        parser.error(
            "merge-evidence polling was removed; only --production-scope remains "
            "for the legacy Production Smoke caller"
        )
    return classify_production_scope()


if __name__ == "__main__":
    raise SystemExit(main())
