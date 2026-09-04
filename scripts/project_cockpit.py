#!/usr/bin/env python3
"""Compile a read-only project cockpit from repo authority and live GitHub facts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROADMAP = ROOT / "docs" / "product" / "ROADMAP.md"
DEFAULT_GRAPH = ROOT / "contract-dependencies.json"
POSTURES = {"ACTIVE", "NEXT_PROBE", "GATED", "REVISIT", "REJECT", "DONE"}
MODES = {"delivery", "evaluation", "discovery"}
ISSUE_REF = re.compile(r"#([1-9][0-9]*)")
OWNERSHIP_VERB = re.compile(
    r"(?im)^\s*(?:refs?|closes?|fix(?:e[sd])?|resolves?|addresses?)\s*:?[ \t]+#([1-9][0-9]*)\b"
)
TITLE_OWNER = re.compile(r"\(#([1-9][0-9]*)\)\s*$")
POSTURE_FIELD = re.compile(
    r"(?im)^\s*(?:roadmap[ \t]+)?posture\s*:\s*(ACTIVE|NEXT_PROBE|GATED|REVISIT|REJECT|DONE)\b"
)
MODE_FIELD = re.compile(r"(?im)^\s*mode\s*:\s*(delivery|evaluation|discovery)\b")
DECISION_MARKER = re.compile(
    r"(?i)\b(?:requires judgment|needs? (?:human|product|owner) (?:decision|input)|"
    r"waiting (?:for|on) (?:human|product|owner) (?:decision|input)|owner input required)\b"
)


def _run_gh(args: list[str]) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"gh {' '.join(args)}: {detail}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh {' '.join(args)} returned invalid JSON: {exc}") from exc


def _safe_gh(errors: list[str], name: str, args: list[str], fallback: Any) -> Any:
    try:
        return _run_gh(args)
    except (OSError, RuntimeError) as exc:
        errors.append(f"{name}: {exc}")
        return fallback


def collect_live(repo: str | None = None) -> dict[str, Any]:
    """Collect only live, read-only GitHub facts needed by the compiler."""
    errors: list[str] = []
    if repo is None:
        repo_data = _safe_gh(errors, "repository", ["repo", "view", "--json", "nameWithOwner"], {})
        repo = repo_data.get("nameWithOwner") if isinstance(repo_data, dict) else None
    if not repo:
        errors.append("repository: unable to determine repository name")
        return {"main": {}, "issues": [], "open_prs": [], "merged_prs": [], "errors": errors}

    main = _safe_gh(errors, "main", ["api", f"repos/{repo}/commits/main"], {})
    issues = _safe_gh(
        errors,
        "issues",
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,url,body,updatedAt",
        ],
        [],
    )
    open_prs = _safe_gh(
        errors,
        "open pull requests",
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,url,body,isDraft,headRefOid,mergeStateStatus,statusCheckRollup,updatedAt",
        ],
        [],
    )
    merged_prs = _safe_gh(
        errors,
        "merged pull requests",
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "merged",
            "--limit",
            "50",
            "--json",
            "number,title,url,body,mergedAt,headRefOid",
        ],
        [],
    )
    return {
        "repo": repo,
        "main": main,
        "issues": issues if isinstance(issues, list) else [],
        "open_prs": open_prs if isinstance(open_prs, list) else [],
        "merged_prs": merged_prs if isinstance(merged_prs, list) else [],
        "errors": errors,
    }


def load_graph(path: Path = DEFAULT_GRAPH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("contract dependency graph must use schema_version 1")
    contracts = data.get("contracts")
    if not isinstance(contracts, dict):
        raise ValueError("contract dependency graph contracts must be an object")
    return data


def parse_roadmap(text: str) -> dict[int, set[str]]:
    """Return posture mentions keyed by focused-owner issue, without interpreting prose."""
    postures: dict[int, set[str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or line.count("|") < 3:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        posture: str | None = None
        for cell in cells:
            match = re.search(r"\b(ACTIVE|NEXT_PROBE|GATED|REVISIT|REJECT|DONE)\b", cell)
            if match:
                posture = match.group(1)
                break
        if posture not in POSTURES:
            continue
        owner_cell = cells[-1]
        for issue_text in ISSUE_REF.findall(owner_cell):
            postures.setdefault(int(issue_text), set()).add(posture)
    return postures


def issue_owner(pr: dict[str, Any]) -> int | None:
    """Find the focused responsibility explicitly claimed by a PR, if exactly one is clear."""
    title = str(pr.get("title") or "")
    title_match = TITLE_OWNER.search(title)
    if title_match:
        return int(title_match.group(1))
    body = str(pr.get("body") or "")
    matches = {int(value) for value in OWNERSHIP_VERB.findall(body)}
    return next(iter(matches)) if len(matches) == 1 else None


def explicit_posture(issue: dict[str, Any], roadmap: dict[int, set[str]]) -> str:
    body = str(issue.get("body") or "")
    field = POSTURE_FIELD.search(body)
    if field:
        return field.group(1)
    mentions = roadmap.get(int(issue["number"]), set())
    if len(mentions) == 1:
        return next(iter(mentions))
    return "requires judgment"


def explicit_mode(issue: dict[str, Any]) -> str | None:
    field = MODE_FIELD.search(str(issue.get("body") or ""))
    return field.group(1).lower() if field else None


def build_state(pr: dict[str, Any]) -> str:
    checks = pr.get("statusCheckRollup") or []
    if not isinstance(checks, list):
        return "unknown"
    builds = [
        check
        for check in checks
        if str(check.get("name") or check.get("context") or "") == "Build"
    ]
    if not builds:
        return "unknown"
    check = builds[-1]
    conclusion = str(check.get("conclusion") or check.get("state") or "").upper()
    status = str(check.get("status") or "").upper()
    if conclusion in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
        return "green"
    if conclusion in {
        "FAILURE",
        "ERROR",
        "CANCELLED",
        "TIMED_OUT",
        "ACTION_REQUIRED",
        "STARTUP_FAILURE",
    }:
        return "red"
    if status in {"QUEUED", "IN_PROGRESS", "PENDING", "WAITING", "REQUESTED"} or conclusion in {
        "PENDING",
        "EXPECTED",
    }:
        return "pending"
    return "unknown"


def _dependencies_for(
    graph: dict[str, Any], issue_number: int, mode: str | None
) -> list[int] | None:
    contract = graph.get("contracts", {}).get(str(issue_number))
    if not contract:
        return []
    dependencies = contract.get("dependencies", [])
    if mode is None:
        return None if dependencies else []
    return [
        int(dep["issue"])
        for dep in dependencies
        if isinstance(dep, dict)
        and mode in dep.get("modes", [])
        and isinstance(dep.get("issue"), int)
    ]


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compile_cockpit(
    live: dict[str, Any],
    roadmap_text: str,
    graph: dict[str, Any],
    *,
    now: datetime | None = None,
    recent_days: int = 7,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    roadmap = parse_roadmap(roadmap_text)
    issues = {int(issue["number"]): issue for issue in live.get("issues", []) if "number" in issue}
    open_prs = list(live.get("open_prs", []))
    merged_prs = list(live.get("merged_prs", []))
    errors = list(live.get("errors", []))

    owners: dict[int, list[dict[str, Any]]] = {}
    for pr in open_prs:
        owner = issue_owner(pr)
        if owner is not None:
            owners.setdefault(owner, []).append(pr)

    warnings: list[str] = []
    if errors:
        warnings.append("incomplete status: GitHub/API query failed: " + "; ".join(errors))
    for issue_number, prs in sorted(owners.items()):
        if len(prs) > 1:
            refs = ", ".join(
                f"#{pr['number']}" for pr in sorted(prs, key=lambda item: item["number"])
            )
            warnings.append(f"duplicate active PR ownership for issue #{issue_number}: {refs}")
        if issue_number not in issues:
            warnings.append(f"active PR ownership references non-open issue #{issue_number}")

    in_flight: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    needs_decision: list[dict[str, Any]] = []
    for pr in sorted(open_prs, key=lambda item: item.get("number", 0)):
        owner = issue_owner(pr)
        build = build_state(pr)
        merge_state = str(pr.get("mergeStateStatus") or "UNKNOWN").lower()
        entry = {
            "pr": int(pr["number"]),
            "issue": owner,
            "title": str(pr.get("title") or ""),
            "url": str(pr.get("url") or ""),
            "draft": bool(pr.get("isDraft")),
            "head_sha": str(pr.get("headRefOid") or ""),
            "build": build,
            "merge_state": merge_state,
        }
        in_flight.append(entry)
        if build == "red":
            blocked.append(
                {"kind": "pr", "number": entry["pr"], "reason": "Build red", "url": entry["url"]}
            )
        elif build == "pending":
            blocked.append(
                {
                    "kind": "pr",
                    "number": entry["pr"],
                    "reason": "Build pending",
                    "url": entry["url"],
                }
            )
        if merge_state in {"blocked", "dirty"}:
            blocked.append(
                {
                    "kind": "pr",
                    "number": entry["pr"],
                    "reason": f"merge state {merge_state}",
                    "url": entry["url"],
                }
            )
        if DECISION_MARKER.search(str(pr.get("body") or "")):
            needs_decision.append({"kind": "pr", "number": entry["pr"], "url": entry["url"]})

    eligible_next: list[dict[str, Any]] = []
    authority_issue_numbers = set(roadmap) | {
        int(key) for key in graph.get("contracts", {}) if str(key).isdigit()
    }
    authority_issue_numbers |= {
        int(dep["issue"])
        for contract in graph.get("contracts", {}).values()
        for dep in contract.get("dependencies", [])
        if isinstance(dep, dict) and isinstance(dep.get("issue"), int)
    }

    for issue_number in sorted(authority_issue_numbers & set(issues)):
        issue = issues[issue_number]
        posture = explicit_posture(issue, roadmap)
        mode = explicit_mode(issue)
        deps = _dependencies_for(graph, issue_number, mode)
        open_deps = [dep for dep in (deps or []) if dep in issues]
        if DECISION_MARKER.search(str(issue.get("body") or "")):
            needs_decision.append(
                {"kind": "issue", "number": issue_number, "url": str(issue.get("url") or "")}
            )
        if posture == "GATED":
            blocked.append(
                {
                    "kind": "issue",
                    "number": issue_number,
                    "reason": "ROADMAP posture GATED",
                    "url": str(issue.get("url") or ""),
                }
            )
            continue
        if open_deps:
            blocked.append(
                {
                    "kind": "issue",
                    "number": issue_number,
                    "reason": f"hard {mode} dependency open: "
                    + ", ".join(f"#{dep}" for dep in open_deps),
                    "url": str(issue.get("url") or ""),
                }
            )
            continue
        if deps is None:
            warnings.append(
                f"issue #{issue_number} dependency eligibility requires judgment: "
                "work mode is not explicit"
            )
            continue
        if issue_number in owners:
            continue
        if posture in {"ACTIVE", "NEXT_PROBE"}:
            eligible_next.append(
                {
                    "issue": issue_number,
                    "title": str(issue.get("title") or ""),
                    "url": str(issue.get("url") or ""),
                    "posture": posture,
                    "mode": mode,
                }
            )
        elif posture == "requires judgment":
            warnings.append(f"issue #{issue_number} eligibility: requires judgment")

    recently_landed: list[dict[str, Any]] = []
    cutoff = now - timedelta(days=recent_days)
    for pr in merged_prs:
        merged_at = _iso(pr.get("mergedAt"))
        if merged_at is None or merged_at < cutoff:
            continue
        recently_landed.append(
            {
                "pr": int(pr["number"]),
                "issue": issue_owner(pr),
                "title": str(pr.get("title") or ""),
                "url": str(pr.get("url") or ""),
                "merged_at": merged_at.isoformat(),
                "head_sha": str(pr.get("headRefOid") or ""),
            }
        )
    recently_landed.sort(key=lambda item: item["merged_at"], reverse=True)

    main = live.get("main") if isinstance(live.get("main"), dict) else {}
    main_sha = str(main.get("sha") or "")
    if not main_sha:
        warnings.append("incomplete status: current main SHA unavailable")

    return {
        "complete": not errors and bool(main_sha),
        "repo": live.get("repo"),
        "main_sha": main_sha or None,
        "needs_decision": needs_decision,
        "in_flight": in_flight,
        "blocked": blocked,
        "recently_landed": recently_landed,
        "eligible_next": eligible_next,
        "warnings": warnings,
    }


def render_markdown(cockpit: dict[str, Any]) -> str:
    lines = [
        "# Project cockpit",
        "",
        f"Current main SHA: `{cockpit.get('main_sha') or 'unavailable'}`",
    ]
    if not cockpit.get("complete"):
        lines += ["", "**Status: incomplete**"]

    lines += ["", "## Needs human/product decision"]
    if cockpit["needs_decision"]:
        for item in cockpit["needs_decision"]:
            lines.append(
                f"- {item['kind']} #{item['number']} — explicit decision/input marker — "
                f"{item['url']}"
            )
    else:
        lines.append("- None mechanically established.")

    lines += ["", "## In flight"]
    if cockpit["in_flight"]:
        for item in cockpit["in_flight"]:
            owner = (
                f"issue #{item['issue']}" if item["issue"] else "focused issue requires judgment"
            )
            readiness = "draft" if item["draft"] else "ready"
            lines.append(
                f"- PR #{item['pr']} — {owner} — {readiness} — `{item['head_sha'][:12]}` — "
                f"Build {item['build']} — merge {item['merge_state']} — {item['url']}"
            )
    else:
        lines.append("- None.")

    lines += ["", "## Blocked / waiting"]
    if cockpit["blocked"]:
        for item in cockpit["blocked"]:
            lines.append(f"- {item['kind']} #{item['number']} — {item['reason']} — {item['url']}")
    else:
        lines.append("- None mechanically established.")

    lines += ["", "## Recently landed"]
    if cockpit["recently_landed"]:
        for item in cockpit["recently_landed"]:
            owner = f"issue #{item['issue']}" if item["issue"] else "linked issue requires judgment"
            lines.append(f"- PR #{item['pr']} — {owner} — {item['merged_at']} — {item['url']}")
    else:
        lines.append("- None in the bounded window.")

    lines += ["", "## Eligible next"]
    if cockpit["eligible_next"]:
        for item in cockpit["eligible_next"]:
            mode = item["mode"] or "mode not explicit"
            lines.append(f"- issue #{item['issue']} — {item['posture']} — {mode} — {item['url']}")
    else:
        lines.append("- None mechanically established; unresolved posture is `requires judgment`.")

    lines += ["", "## Warnings"]
    if cockpit["warnings"]:
        lines.extend(f"- {warning}" for warning in cockpit["warnings"])
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def _load_authority(roadmap_path: Path, graph_path: Path) -> tuple[str, dict[str, Any]]:
    return roadmap_path.read_text(encoding="utf-8"), load_graph(graph_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", help="GitHub repository in owner/name form; defaults to gh repo view"
    )
    parser.add_argument("--format", choices=("markdown", "json", "both"), default="markdown")
    parser.add_argument("--recent-days", type=int, default=7)
    parser.add_argument("--roadmap", type=Path, default=DEFAULT_ROADMAP)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    args = parser.parse_args(argv)
    if args.recent_days < 1:
        parser.error("--recent-days must be positive")

    try:
        roadmap_text, graph = _load_authority(args.roadmap, args.graph)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"project cockpit authority error: {exc}", file=sys.stderr)
        return 2

    live = collect_live(args.repo)
    cockpit = compile_cockpit(live, roadmap_text, graph, recent_days=args.recent_days)
    if args.format in {"markdown", "both"}:
        print(render_markdown(cockpit), end="")
    if args.format == "both":
        print("\n```json")
    if args.format in {"json", "both"}:
        print(json.dumps(cockpit, indent=2, sort_keys=True))
    if args.format == "both":
        print("```")
    return 0 if cockpit["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
