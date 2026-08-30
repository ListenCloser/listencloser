#!/usr/bin/env python3
"""Classify changed paths by deployed production component.

This intentionally contains no GitHub API calls, workflow polling, or merge-policy
logic. It is consumed only by the post-merge production smoke workflow.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable

FRONTEND_DEPLOY_FILES = {
    ".vercelignore",
    "instrumentation-client.ts",
    "instrumentation.ts",
    "next.config.mjs",
    "package-lock.json",
    "package.json",
    "postcss.config.mjs",
    "proxy.ts",
    "tsconfig.json",
    "vercel.json",
}
FRONTEND_DEPLOY_PREFIXES = ("app/", "components/", "lib/", "public/")


def _is_backend_runtime(path: str) -> bool:
    return (
        path.startswith("backend/")
        and not path.startswith("backend/evaluation/")
        and not path.startswith("backend/tests/")
    )


def _needs_backend_deploy(path: str) -> bool:
    return (
        _is_backend_runtime(path)
        or path.startswith("supabase/migrations/")
        or path in {".github/workflows/deploy-backend.yml", "scripts/deploy.sh"}
    )


def _needs_frontend_deploy(path: str) -> bool:
    return path.startswith(FRONTEND_DEPLOY_PREFIXES) or path in FRONTEND_DEPLOY_FILES


def production_components(paths: Iterable[str]) -> set[str]:
    files = tuple(paths)
    result: set[str] = set()
    if any(_needs_frontend_deploy(path) for path in files):
        result.add("frontend")
    if any(_needs_backend_deploy(path) for path in files):
        result.add("backend")
    return result


def _self_test() -> None:
    assert production_components(["README.md"]) == set()
    assert production_components(["docs/PLATFORM.md"]) == set()
    assert production_components(["backend/evaluation/foo.py"]) == set()
    assert production_components(["backend/tests/test_worker.py"]) == set()
    assert production_components(["components/workspace/Inspector.tsx"]) == {"frontend"}
    assert production_components(["app/api/health/live/route.ts"]) == {"frontend"}
    assert production_components(["vercel.json"]) == {"frontend"}
    assert production_components(["backend/domain/job_worker.py"]) == {"backend"}
    assert production_components(["supabase/migrations/20260828.sql"]) == {"backend"}
    assert production_components(["scripts/deploy.sh"]) == {"backend"}
    assert production_components(
        ["components/workspace/Inspector.tsx", "backend/domain/job_worker.py"]
    ) == {"frontend", "backend"}


def main() -> int:
    _self_test()
    paths = [line.strip() for line in sys.stdin if line.strip()]
    for component in sorted(production_components(paths)):
        print(component)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
