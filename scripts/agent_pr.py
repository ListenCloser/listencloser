#!/usr/bin/env python3
"""Diff-aware fast path for autonomous PR development.

This script is executable policy: it derives the smallest useful local gate from
what actually changed instead of requiring an agent to remember a long prompt.

Typical loop:

    python scripts/agent_pr.py plan
    # edit
    python scripts/agent_pr.py prepare
    # commit any deterministic fixes, then rerun prepare before opening/updating PR

Machine consumers can use:

    python scripts/agent_pr.py policy --json --base <base-sha>

CI remains authoritative. This tool deliberately does not claim that a local
fast gate substitutes for real-stack, database, benchmark, security, or deploy
verification when those evidence tiers are required by the diff.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Policy:
    files: tuple[str, ...]
    kind: str
    risk: str
    fix_mode: str
    check_mode: str
    required_evidence: tuple[str, ...]
    flags: tuple[str, ...]


FRONTEND_PREFIXES = (
    "app/",
    "components/",
    "hooks/",
    "lib/",
    "public/",
    "tests/components/",
    "tests/e2e/",
    "tests/visual/",
)
FRONTEND_FILES = {
    "package.json",
    "package-lock.json",
    "next.config.mjs",
    "eslint.config.mjs",
    "postcss.config.mjs",
    "tailwind.config.ts",
    "tsconfig.json",
    "vitest.config.ts",
    "playwright.config.ts",
    "playwright.realstack.config.ts",
}
CONTROL_PREFIXES = (".github/", "scripts/", ".devcontainer/")
CONTROL_FILES = {
    "AGENTS.md",
    "CODEOWNERS",
    ".pre-commit-config.yaml",
    "docker-compose.yml",
    "docker-compose.agent-privileged.yml",
}
DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "backend/pyproject.toml",
    "backend/uv.lock",
}


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def repository_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return Path(result.stdout.strip())


def _ref_exists(root: Path, ref: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def resolve_base(root: Path, requested: str | None) -> str:
    candidates = [
        requested,
        os.environ.get("AGENT_BASE_REF"),
        "origin/main",
        "main",
    ]
    for candidate in candidates:
        if candidate and _ref_exists(root, candidate):
            return candidate
    raise SystemExit(
        "Could not resolve a comparison base. Fetch origin/main or pass --base <sha/ref>."
    )


def _lines(result: subprocess.CompletedProcess[str]) -> set[str]:
    return {line.strip() for line in (result.stdout or "").splitlines() if line.strip()}


def changed_files(root: Path, base: str, *, include_worktree: bool = True) -> tuple[str, ...]:
    files = _lines(
        _run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=root,
            capture=True,
        )
    )
    if include_worktree:
        files |= _lines(
            _run(["git", "diff", "--name-only"], cwd=root, capture=True)
        )
        files |= _lines(
            _run(["git", "diff", "--cached", "--name-only"], cwd=root, capture=True)
        )
    return tuple(sorted(files))


def _matches_prefix(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _docs_only(path: str) -> bool:
    return (
        path.startswith("docs/")
        or path.endswith(".md")
        or path.endswith(".txt")
        or path in {"LICENSE", "README"}
    )


def classify(files: Sequence[str]) -> Policy:
    normalized = tuple(sorted({path.removeprefix("./") for path in files if path}))
    if not normalized:
        return Policy((), "empty", "low", "none", "none", (), ())

    frontend = any(
        _matches_prefix(path, FRONTEND_PREFIXES) or path in FRONTEND_FILES
        for path in normalized
    )
    backend = any(path.startswith("backend/") for path in normalized)
    database = any(path.startswith("supabase/") for path in normalized)
    control = any(
        _matches_prefix(path, CONTROL_PREFIXES) or path in CONTROL_FILES
        for path in normalized
    )
    evaluation = any(
        path.startswith("evaluation/") or path.startswith("backend/evaluation/")
        for path in normalized
    )
    dependencies = any(path in DEPENDENCY_FILES for path in normalized)
    workflows = any(path.startswith(".github/workflows/") for path in normalized)
    migrations = any(path.startswith("supabase/migrations/") for path in normalized)
    deploy = any(
        path.startswith("scripts/deploy")
        or path.startswith("backend/docker-compose")
        or path.startswith(".github/workflows/deploy")
        or path.startswith(".github/workflows/backend-image")
        for path in normalized
    )
    capability_policy = any(
        path == "backend/config/capabilities.json"
        or "capabilit" in path.lower()
        or "truthfulness" in path.lower()
        for path in normalized
    )
    security = any(
        token in path.lower()
        for path in normalized
        for token in ("security", "auth", "rls", "secret", "permission")
    )
    docs_only = all(_docs_only(path) for path in normalized)

    flags: list[str] = []
    for enabled, label in (
        (frontend, "frontend"),
        (backend, "backend"),
        (database, "database"),
        (control, "control-plane"),
        (evaluation, "evaluation"),
        (dependencies, "dependencies"),
        (workflows, "workflows"),
        (migrations, "migrations"),
        (deploy, "deploy"),
        (capability_policy, "capability-policy"),
        (security, "security-sensitive"),
    ):
        if enabled:
            flags.append(label)

    if docs_only:
        kind = "docs-research"
    elif control and not (frontend or backend or database):
        kind = "control-plane"
    elif evaluation and not (frontend or database):
        kind = "evaluation"
    elif frontend or backend or database:
        kind = "production"
    else:
        kind = "refactor"

    high_risk = migrations or deploy or workflows or dependencies or security or capability_policy
    risk = "high" if high_risk else ("low" if docs_only else "standard")

    if backend and frontend:
        fix_mode = "all"
        check_mode = "fast"
    elif backend:
        fix_mode = "python"
        check_mode = "backend"
    elif frontend:
        fix_mode = "frontend"
        check_mode = "frontend"
    else:
        fix_mode = "none"
        check_mode = "light"

    evidence: list[str] = ["diff-check"]
    if frontend:
        evidence.extend(("frontend-static", "frontend-unit"))
    if backend:
        evidence.extend(("backend-static", "backend-unit", "api-contract"))
    if database or migrations:
        evidence.append("database-integration")
    if workflows or control:
        evidence.append("control-plane-review")
    if deploy:
        evidence.append("deployment/runtime-verification")
    if evaluation:
        evidence.append("evaluation-artifact")
    if capability_policy:
        evidence.append("capability-registry/truthfulness")
    if any(path.startswith("tests/e2e/") or path.startswith("playwright") for path in normalized):
        evidence.append("mocked-browser-e2e")
    if any(path.startswith("tests/real") or "real-stack" in path for path in normalized):
        evidence.append("fresh-real-stack-e2e")

    return Policy(
        normalized,
        kind,
        risk,
        fix_mode,
        check_mode,
        tuple(dict.fromkeys(evidence)),
        tuple(flags),
    )


def _format_command(args: Sequence[str]) -> str:
    return " ".join(shlex.quote(arg) for arg in args)


def print_policy(policy: Policy, *, base: str, as_json: bool) -> None:
    if as_json:
        payload = asdict(policy)
        payload["base"] = base
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(f"Base:       {base}")
    print(f"Kind:       {policy.kind}")
    print(f"Risk:       {policy.risk}")
    print(f"Fix mode:   {policy.fix_mode}")
    print(f"Check mode: {policy.check_mode}")
    print(f"Flags:      {', '.join(policy.flags) if policy.flags else 'none'}")
    print("Evidence:   " + (", ".join(policy.required_evidence) or "none"))
    print("Changed:")
    if policy.files:
        for path in policy.files:
            print(f"  - {path}")
    else:
        print("  (none)")


def _status(root: Path) -> str:
    return _run(["git", "status", "--porcelain"], cwd=root, capture=True).stdout or ""


def run_diff_check(root: Path, base: str) -> None:
    commands = [["git", "diff", "--check", f"{base}...HEAD"]]
    if _status(root):
        commands.extend(
            (["git", "diff", "--check"], ["git", "diff", "--cached", "--check"])
        )
    for command in commands:
        print(f"+ {_format_command(command)}")
        _run(command, cwd=root)


def run_light_checks(root: Path, files: Sequence[str]) -> None:
    shell_files = [path for path in files if path.endswith(".sh") and (root / path).exists()]
    python_files = [
        path
        for path in files
        if path.startswith("scripts/") and path.endswith(".py") and (root / path).exists()
    ]
    for path in shell_files:
        command = ["bash", "-n", path]
        print(f"+ {_format_command(command)}")
        _run(command, cwd=root)
    for path in python_files:
        command = [sys.executable, "-m", "py_compile", path]
        print(f"+ {_format_command(command)}")
        _run(command, cwd=root)


def run_prepare(root: Path, base: str, policy: Policy, *, apply_fixes: bool) -> None:
    if not policy.files:
        print("No changed files; nothing to prepare.")
        return

    before = _status(root)
    run_diff_check(root, base)

    if apply_fixes and policy.fix_mode != "none":
        command = ["bash", "scripts/fix.sh", policy.fix_mode]
        print(f"+ {_format_command(command)}")
        _run(command, cwd=root)

    if policy.check_mode in {"frontend", "backend", "fast"}:
        command = ["bash", "scripts/check.sh", policy.check_mode]
        print(f"+ {_format_command(command)}")
        _run(command, cwd=root)
    else:
        run_light_checks(root, policy.files)

    run_diff_check(root, base)
    after = _status(root)
    if apply_fixes and after != before:
        print(
            "\nDeterministic fixes changed the working tree. Review/commit them and rerun "
            "`python scripts/agent_pr.py prepare` before opening or updating the PR.",
            file=sys.stderr,
        )
        raise SystemExit(3)

    print("\nFast PR gate passed.")
    if policy.risk == "high":
        print(
            "High-risk diff: this fast gate is not sufficient evidence by itself. "
            "Use the required CI/integration/runtime tiers listed above."
        )


def parser() -> argparse.ArgumentParser:
    arg_parser = argparse.ArgumentParser(
        description="Classify a diff and run the smallest useful autonomous-agent PR gate."
    )
    subparsers = arg_parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "policy", "prepare"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--base", help="comparison base SHA/ref (default: origin/main, then main)")
        sub.add_argument(
            "--committed-only",
            action="store_true",
            help="ignore staged/working-tree paths and classify only base...HEAD",
        )
        if name in {"plan", "policy"}:
            sub.add_argument("--json", action="store_true", help="emit machine-readable policy JSON")
        if name == "prepare":
            sub.add_argument(
                "--no-fix",
                action="store_true",
                help="verify without applying deterministic safe fixes first",
            )
    return arg_parser


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = repository_root()
    base = resolve_base(root, args.base)
    files = changed_files(root, base, include_worktree=not args.committed_only)
    policy = classify(files)

    if args.command in {"plan", "policy"}:
        print_policy(policy, base=base, as_json=args.json)
        return 0

    print_policy(policy, base=base, as_json=False)
    print()
    run_prepare(root, base, policy, apply_fixes=not args.no_fix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
