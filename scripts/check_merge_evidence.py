#!/usr/bin/env python3
"""Wait for the risk-relevant PR workflows before the protected build turns green.

`main` branch protection intentionally requires one stable context named `build`.
This script makes that context an aggregate gate without duplicating heavyweight
work inside build.yml: it inspects the PR diff, determines which independent
workflows are relevant, then waits for their latest run on the exact PR head SHA.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from typing import Any

ALWAYS_REQUIRED = {
    "CodeQL",
    "Dependency Review",
    "Secrets scan (Gitleaks)",
}


def _is_docs_only(path: str) -> bool:
    return ("/" not in path and path.endswith(".md")) or path.startswith("docs/")


def _is_backend_runtime(path: str) -> bool:
    return (
        path.startswith("backend/")
        and not path.startswith("backend/evaluation/")
        and not path.startswith("backend/tests/")
    )


def _needs_real_stack(path: str) -> bool:
    if _is_backend_runtime(path):
        return True
    if path.startswith(("app/", "components/", "lib/")):
        return True
    return path in {
        "package.json",
        "package-lock.json",
        "next.config.mjs",
        "tsconfig.json",
        "tests/e2e/real-stack-workflow.spec.ts",
        "tests/e2e/real-stack-golden.spec.ts",
        "playwright.realstack.config.ts",
        ".github/workflows/real-stack-e2e.yml",
    }


def _needs_database(path: str) -> bool:
    return (
        path.startswith("supabase/migrations/")
        or path.startswith("backend/domain/")
        or path.startswith("backend/tests/integration/")
        or path
        in {
            "backend/music_features.py",
            "backend/tests/test_rls_domain.py",
            "backend/pyproject.toml",
            "backend/uv.lock",
            "scripts/verify_database.sql",
            ".github/workflows/database-integration.yml",
        }
    )


def _needs_backend_image(path: str) -> bool:
    return _is_backend_runtime(path) or path in {
        ".github/workflows/backend-image.yml",
        ".github/workflows/deploy-backend.yml",
        "scripts/deploy.sh",
    }


def required_workflows(paths: Iterable[str]) -> set[str]:
    files = tuple(paths)
    required = set(ALWAYS_REQUIRED)
    if not files or not all(_is_docs_only(path) for path in files):
        required.update({"CI", "E2E"})
    if any(_needs_real_stack(path) for path in files):
        required.add("Real-stack E2E")
    if any(_needs_database(path) for path in files):
        required.add("Database Integration")
    if any(_needs_backend_image(path) for path in files):
        required.add("Backend Image")
    return required


def _api_json(url: str, token: str) -> dict[str, Any] | list[Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hello-ai-merge-evidence-gate",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {url}: {body}") from exc


def _pr_files(repo: str, pr_number: int, token: str) -> list[str]:
    result: list[str] = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files?"
            + urllib.parse.urlencode({"per_page": 100, "page": page})
        )
        payload = _api_json(url, token)
        if not isinstance(payload, list):
            raise RuntimeError("unexpected PR files response")
        result.extend(str(item["filename"]) for item in payload)
        if len(payload) < 100:
            return result
        page += 1


def _latest_runs(repo: str, head_sha: str, token: str) -> dict[str, dict[str, Any]]:
    url = (
        f"https://api.github.com/repos/{repo}/actions/runs?"
        + urllib.parse.urlencode(
            {
                "head_sha": head_sha,
                "event": "pull_request",
                "per_page": 100,
            }
        )
    )
    payload = _api_json(url, token)
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected workflow runs response")

    latest: dict[str, dict[str, Any]] = {}
    for run in payload.get("workflow_runs", []):
        name = str(run.get("name", ""))
        previous = latest.get(name)
        rank = (
            int(run.get("run_number") or 0),
            int(run.get("run_attempt") or 0),
            str(run.get("created_at") or ""),
        )
        if previous is None:
            latest[name] = run
            continue
        previous_rank = (
            int(previous.get("run_number") or 0),
            int(previous.get("run_attempt") or 0),
            str(previous.get("created_at") or ""),
        )
        if rank > previous_rank:
            latest[name] = run
    return latest


def _self_test() -> None:
    assert required_workflows(["README.md"]) == ALWAYS_REQUIRED
    assert required_workflows(["docs/PLATFORM.md"]) == ALWAYS_REQUIRED

    component = required_workflows(["components/workspace/Inspector.tsx"])
    assert component == ALWAYS_REQUIRED | {"CI", "E2E", "Real-stack E2E"}

    evaluation = required_workflows(["backend/evaluation/foo.py"])
    assert evaluation == ALWAYS_REQUIRED | {"CI", "E2E"}

    domain = required_workflows(["backend/domain/job_worker.py"])
    assert domain == ALWAYS_REQUIRED | {
        "CI",
        "E2E",
        "Real-stack E2E",
        "Database Integration",
        "Backend Image",
    }

    integration_test = required_workflows(["backend/tests/integration/test_jobs.py"])
    assert integration_test == ALWAYS_REQUIRED | {"CI", "E2E", "Database Integration"}

    deploy = required_workflows(["scripts/deploy.sh"])
    assert deploy == ALWAYS_REQUIRED | {"CI", "E2E", "Backend Image"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--sha")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--timeout-seconds", type=int, default=1500)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    _self_test()
    if args.self_test:
        print("merge evidence matcher self-test passed")
        return 0

    if not args.repo or not args.pr or not args.sha or not args.token:
        parser.error("--repo, --pr, --sha, and a token are required")

    paths = _pr_files(args.repo, args.pr, args.token)
    required = required_workflows(paths)
    print(f"changed files ({len(paths)}):")
    for path in paths:
        print(f"  - {path}")
    print("required workflow evidence:")
    for name in sorted(required):
        print(f"  - {name}")

    deadline = time.monotonic() + args.timeout_seconds
    while True:
        runs = _latest_runs(args.repo, args.sha, args.token)
        missing: list[str] = []
        pending: list[str] = []
        failed: list[str] = []

        for name in sorted(required):
            run = runs.get(name)
            if run is None:
                missing.append(name)
                continue
            status = str(run.get("status") or "")
            conclusion = run.get("conclusion")
            if status != "completed":
                pending.append(f"{name} ({status})")
            elif conclusion != "success":
                failed.append(f"{name} ({conclusion})")

        if failed:
            print("merge evidence failed:", ", ".join(failed), file=sys.stderr)
            return 1
        if not missing and not pending:
            print("all risk-relevant workflow evidence is green on the exact PR head")
            return 0
        if time.monotonic() >= deadline:
            details = [*(f"missing {name}" for name in missing), *pending]
            print("merge evidence timed out: " + ", ".join(details), file=sys.stderr)
            return 1

        details = [*(f"missing {name}" for name in missing), *pending]
        print("waiting for: " + ", ".join(details), flush=True)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
