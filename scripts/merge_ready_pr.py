#!/usr/bin/env python3
"""Merge a green PR against current main without needless global serialization.

The protected Build workflow already aggregates all risk-relevant exact-head
checks. This script runs only after that Build succeeds. It re-evaluates the PR
against the *current* base branch immediately before merge:

- disjoint leaf changes may merge even if main advanced;
- direct file overlap or shared/global integration surfaces trigger an automatic
  update-branch so the PR re-runs CI on the new base;
- no agent needs to coordinate merge ordering manually.

PRs opt in by checking the pull-request-template box:
    - [x] Merge automatically when green
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from typing import Any

AUTO_MERGE_MARKER = "- [x] Merge automatically when green"
AUTO_MERGE_MARKER_UPPER = "- [X] Merge automatically when green"

GLOBAL_FILES = {
    ".vercelignore",
    "next.config.mjs",
    "package-lock.json",
    "package.json",
    "playwright.config.ts",
    "playwright.realstack.config.ts",
    "postcss.config.mjs",
    "proxy.ts",
    "tsconfig.json",
    "vercel.json",
    "vitest.config.ts",
}


def _is_docs(path: str) -> bool:
    return ("/" not in path and path.endswith(".md")) or path.startswith("docs/")


def _path_kind(path: str) -> str:
    """Classify paths by how broadly an intervening change can invalidate CI."""
    if _is_docs(path):
        return "docs"
    if path in GLOBAL_FILES or path.startswith((".github/", "scripts/")):
        return "global"
    if path.startswith(("tests/", "app/api/", "lib/")):
        return "frontend-shared"
    if path.startswith(("app/", "components/", "public/")):
        return "frontend-leaf"
    if path.startswith("backend/evaluation/"):
        return "backend-leaf"
    if path.startswith(("backend/", "supabase/")):
        return "backend-shared"
    return "other"


def _non_docs_kinds(paths: Iterable[str]) -> set[str]:
    return {kind for path in paths if (kind := _path_kind(path)) != "docs"}


def parallel_conflicts(pr_paths: Iterable[str], intervening_paths: Iterable[str]) -> list[str]:
    """Return reasons a stale PR must refresh before merge.

    Two leaf changes in distinct files may proceed in parallel. Shared surfaces
    (lib/store/API/tests/backend runtime) force a refresh only when the other
    side changed the corresponding product domain. Global build/CI/config
    changes force any non-doc PR to refresh.
    """
    pr = set(pr_paths)
    intervening = set(intervening_paths)
    reasons: list[str] = []

    overlap = sorted(pr & intervening)
    if overlap:
        reasons.append("same files changed: " + ", ".join(overlap[:12]))

    pr_kinds = _non_docs_kinds(pr)
    intervening_kinds = _non_docs_kinds(intervening)
    if not pr_kinds or not intervening_kinds:
        return reasons

    if "global" in pr_kinds or "global" in intervening_kinds:
        reasons.append("global build/CI/config surface changed")

    frontend = {"frontend-leaf", "frontend-shared"}
    if (
        "frontend-shared" in pr_kinds
        and bool(intervening_kinds & frontend)
    ) or (
        "frontend-shared" in intervening_kinds
        and bool(pr_kinds & frontend)
    ):
        reasons.append("shared frontend/API/test surface changed")

    backend = {"backend-leaf", "backend-shared"}
    if (
        "backend-shared" in pr_kinds
        and bool(intervening_kinds & backend)
    ) or (
        "backend-shared" in intervening_kinds
        and bool(pr_kinds & backend)
    ):
        reasons.append("shared backend/database/test surface changed")

    return list(dict.fromkeys(reasons))


def _request_json(
    url: str,
    token: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "hello-ai-merge-ready",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {method} {url}: {payload}") from exc


def _pr(repo: str, number: int, token: str) -> dict[str, Any]:
    payload = _request_json(f"https://api.github.com/repos/{repo}/pulls/{number}", token)
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected pull request response")
    return payload


def _pr_files(repo: str, number: int, token: str) -> list[str]:
    paths: list[str] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"per_page": 100, "page": page})
        payload = _request_json(
            f"https://api.github.com/repos/{repo}/pulls/{number}/files?{query}",
            token,
        )
        if not isinstance(payload, list):
            raise RuntimeError("unexpected PR files response")
        paths.extend(str(item["filename"]) for item in payload)
        if len(payload) < 100:
            return paths
        page += 1


def _branch_sha(repo: str, branch: str, token: str) -> str:
    encoded = urllib.parse.quote(branch, safe="")
    payload = _request_json(
        f"https://api.github.com/repos/{repo}/branches/{encoded}",
        token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected branch response")
    return str(payload["commit"]["sha"])


def _compare_files(repo: str, base: str, head: str, token: str) -> list[str]:
    payload = _request_json(
        f"https://api.github.com/repos/{repo}/compare/{base}...{head}",
        token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected compare response")
    files = payload.get("files", [])
    if len(files) >= 300:
        raise RuntimeError("intervening compare reached GitHub's 300-file safety limit")
    return [str(item["filename"]) for item in files]


def _update_branch(repo: str, number: int, head_sha: str, token: str) -> None:
    _request_json(
        f"https://api.github.com/repos/{repo}/pulls/{number}/update-branch",
        token,
        method="PUT",
        body={"expected_head_sha": head_sha},
    )


def _merge(repo: str, number: int, head_sha: str, token: str) -> dict[str, Any]:
    payload = _request_json(
        f"https://api.github.com/repos/{repo}/pulls/{number}/merge",
        token,
        method="PUT",
        body={"sha": head_sha, "merge_method": "squash"},
    )
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected merge response")
    return payload


def _opted_in(body: str) -> bool:
    return AUTO_MERGE_MARKER in body or AUTO_MERGE_MARKER_UPPER in body


def _self_test() -> None:
    assert not parallel_conflicts(
        ["components/Waveform.tsx"],
        ["components/workspace/LibraryPanel.tsx"],
    )
    assert parallel_conflicts(
        ["components/Waveform.tsx"],
        ["lib/audio-buffer-cache.ts"],
    )
    assert parallel_conflicts(
        ["components/Waveform.tsx"],
        ["components/Waveform.tsx"],
    )
    assert not parallel_conflicts(
        ["components/Waveform.tsx"],
        ["docs/ARCHITECTURE.md"],
    )
    assert parallel_conflicts(
        ["components/Waveform.tsx"],
        ["package-lock.json"],
    )
    assert not parallel_conflicts(
        ["backend/evaluation/beat_eval.py"],
        ["backend/evaluation/separation_eval.py"],
    )
    assert parallel_conflicts(
        ["backend/evaluation/beat_eval.py"],
        ["backend/domain/job_worker.py"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--head-sha")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    _self_test()
    if args.self_test:
        print("parallel merge classifier self-test passed")
        return 0

    if not args.repo or not args.pr or not args.head_sha or not args.token:
        parser.error("--repo, --pr, --head-sha, and a token are required")

    for _ in range(5):
        pull = _pr(args.repo, args.pr, args.token)
        if pull.get("state") != "open":
            print("PR is no longer open; nothing to do")
            return 0
        if pull.get("draft"):
            print("PR is draft; merge coordinator is inactive")
            return 0
        body = str(pull.get("body") or "")
        if not _opted_in(body):
            print("PR did not opt into repository merge automation")
            return 0

        head_sha = str(pull["head"]["sha"])
        if head_sha != args.head_sha:
            print(f"workflow head {args.head_sha} is stale; current PR head is {head_sha}")
            return 0

        base_ref = str(pull["base"]["ref"])
        tested_base_sha = str(pull["base"]["sha"])
        current_base_sha = _branch_sha(args.repo, base_ref, args.token)

        if current_base_sha != tested_base_sha:
            pr_paths = _pr_files(args.repo, args.pr, args.token)
            intervening = _compare_files(
                args.repo,
                tested_base_sha,
                current_base_sha,
                args.token,
            )
            conflicts = parallel_conflicts(pr_paths, intervening)
            if conflicts:
                print("current main overlaps this PR's tested integration surface:")
                for reason in conflicts:
                    print(f"  - {reason}")
                print("updating the PR branch so CI re-runs on current main")
                _update_branch(args.repo, args.pr, head_sha, args.token)
                return 0
            print(
                "main advanced, but intervening changes are disjoint from this PR; "
                "merge may proceed without a redundant CI cycle"
            )

        # Close the small race between safety evaluation and merge. If main moved
        # again, loop and classify the new intervening delta before mutating.
        latest_base_sha = _branch_sha(args.repo, base_ref, args.token)
        if latest_base_sha != current_base_sha:
            print("main advanced during merge evaluation; rechecking")
            continue

        try:
            result = _merge(args.repo, args.pr, head_sha, args.token)
        except RuntimeError as exc:
            message = str(exc)
            if "405" in message or "409" in message:
                print("repository merge policy requires a refreshed branch; updating it")
                _update_branch(args.repo, args.pr, head_sha, args.token)
                return 0
            raise

        if not result.get("merged"):
            raise RuntimeError(f"merge was not accepted: {result}")
        print(f"merged PR #{args.pr}: {result.get('sha')}")
        return 0

    raise RuntimeError("main changed repeatedly during merge evaluation; retry on next Build event")


if __name__ == "__main__":
    raise SystemExit(main())
