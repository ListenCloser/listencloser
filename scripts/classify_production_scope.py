#!/usr/bin/env python3
"""Classify changed paths by deployed production component.

This intentionally contains no GitHub API calls, workflow polling, or merge-policy
logic. It is shared by post-merge Production Smoke and Vercel's Ignored Build Step
so both use the same production-scope authority.
"""

from __future__ import annotations

import argparse
import os
import subprocess
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

# Vercel skipping is deliberately stricter than generic production classification.
# Only paths already excluded from the Vercel source context, obvious docs, or paths
# owned exclusively by the backend deploy contract may skip a frontend build.
VERCEL_SAFE_NONFRONTEND_PREFIXES = ("backend/", "docs/", "soundfonts/", "tests/")


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


def _is_known_vercel_nonfrontend(path: str) -> bool:
    if path.startswith(VERCEL_SAFE_NONFRONTEND_PREFIXES):
        return True
    if "/" not in path and path.endswith(".md"):
        return True
    return _needs_backend_deploy(path)


def should_ignore_vercel_build(paths: Iterable[str]) -> bool:
    """Return True only when every changed path is known not to affect Vercel."""
    files = tuple(paths)
    if not files or "frontend" in production_components(files):
        return False
    return all(_is_known_vercel_nonfrontend(path) for path in files)


def _vercel_changed_paths() -> list[str]:
    previous_sha = os.environ.get("VERCEL_GIT_PREVIOUS_SHA", "").strip()
    if not previous_sha:
        raise RuntimeError("VERCEL_GIT_PREVIOUS_SHA is unavailable")

    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", previous_sha, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


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

    assert should_ignore_vercel_build(["README.md"])
    assert should_ignore_vercel_build(["docs/PLATFORM.md"])
    assert should_ignore_vercel_build(["backend/evaluation/foo.py"])
    assert should_ignore_vercel_build(["backend/domain/job_worker.py"])
    assert should_ignore_vercel_build(["tests/e2e/example.spec.ts"])
    assert should_ignore_vercel_build(["supabase/migrations/20260828.sql"])
    assert should_ignore_vercel_build(["scripts/deploy.sh"])
    assert not should_ignore_vercel_build([])
    assert not should_ignore_vercel_build(["components/workspace/Inspector.tsx"])
    assert not should_ignore_vercel_build(["lib/api-types.ts"])
    assert not should_ignore_vercel_build(["package.json"])
    assert not should_ignore_vercel_build([".npmrc"])
    assert not should_ignore_vercel_build(["scripts/check.sh"])
    assert not should_ignore_vercel_build(
        ["backend/domain/job_worker.py", "next.config.mjs"]
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--production-scope",
        action="store_true",
        help="read changed paths from stdin and print affected production components",
    )
    mode.add_argument(
        "--vercel-ignore",
        action="store_true",
        help="return Vercel Ignored Build Step semantics for changes since its previous SHA",
    )
    mode.add_argument("--self-test", action="store_true", help="run classifier assertions")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _self_test()

    if args.self_test:
        print("production scope classifier self-test passed")
        return 0

    if args.vercel_ignore:
        try:
            paths = _vercel_changed_paths()
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Cannot prove Vercel build is irrelevant ({exc}); continuing build.", file=sys.stderr)
            return 1

        if should_ignore_vercel_build(paths):
            print("Only known non-frontend production paths changed; skipping Vercel build.")
            return 0

        print("Frontend or ambiguous production path changed; continuing Vercel build.")
        return 1

    paths = [line.strip() for line in sys.stdin if line.strip()]
    for component in sorted(production_components(paths)):
        print(component)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
