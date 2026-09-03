#!/usr/bin/env python3
"""Validate the narrow repo-native focused-contract dependency graph."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_MODES = frozenset({"discovery", "evaluation", "delivery"})
SOURCE_ID_RE = re.compile(r"^[1-9][0-9]*$")
DEFAULT_GRAPH = Path(__file__).resolve().parents[1] / "docs" / "contract-dependencies.json"


class ContractGraphError(ValueError):
    """Raised when the contract dependency graph violates its schema or invariants."""


def _require_exact_keys(value: dict[str, Any], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise ContractGraphError(
            f"{context} must contain exactly {sorted(expected)} ({', '.join(details)})"
        )


def _positive_issue(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractGraphError(f"{context} must be a positive integer")
    return value


def _validate_cycles(edges: dict[str, dict[int, set[int]]]) -> None:
    for mode, adjacency in edges.items():
        visiting: set[int] = set()
        visited: set[int] = set()

        def visit(node: int, path: list[int]) -> None:
            if node in visiting:
                start = path.index(node)
                cycle = path[start:] + [node]
                rendered = " -> ".join(f"#{issue}" for issue in cycle)
                raise ContractGraphError(f"{mode} dependency cycle: {rendered}")
            if node in visited:
                return

            visiting.add(node)
            path.append(node)
            for target in adjacency.get(node, set()):
                visit(target, path)
            path.pop()
            visiting.remove(node)
            visited.add(node)

        for node in adjacency:
            visit(node, [])


def validate_graph(data: Any) -> None:
    if not isinstance(data, dict):
        raise ContractGraphError("graph must be a JSON object")

    _require_exact_keys(data, {"schema_version", "contracts"}, "graph")
    if data["schema_version"] != 1:
        raise ContractGraphError("schema_version must be 1")

    contracts = data["contracts"]
    if not isinstance(contracts, dict) or not contracts:
        raise ContractGraphError("contracts must be a non-empty object")

    per_mode: dict[str, dict[int, set[int]]] = {mode: {} for mode in ALLOWED_MODES}

    for source_text, contract in contracts.items():
        if not isinstance(source_text, str) or not SOURCE_ID_RE.fullmatch(source_text):
            raise ContractGraphError(
                f"contract key {source_text!r} must be a positive GitHub issue number"
            )
        source = int(source_text)

        if not isinstance(contract, dict):
            raise ContractGraphError(f"contract #{source} must be an object")
        _require_exact_keys(contract, {"dependencies"}, f"contract #{source}")

        dependencies = contract["dependencies"]
        if not isinstance(dependencies, list) or not dependencies:
            raise ContractGraphError(
                f"contract #{source} must contain at least one dependency; "
                "omit nodes with no outgoing edges"
            )

        seen_targets: set[int] = set()
        for index, dependency in enumerate(dependencies):
            context = f"contract #{source} dependency[{index}]"
            if not isinstance(dependency, dict):
                raise ContractGraphError(f"{context} must be an object")
            _require_exact_keys(dependency, {"issue", "modes"}, context)

            target = _positive_issue(dependency["issue"], f"{context}.issue")
            if target == source:
                raise ContractGraphError(f"contract #{source} cannot depend on itself")
            if target in seen_targets:
                raise ContractGraphError(
                    f"contract #{source} repeats dependency target #{target}; "
                    "combine its modes into one edge"
                )
            seen_targets.add(target)

            modes = dependency["modes"]
            if not isinstance(modes, list) or not modes:
                raise ContractGraphError(f"{context}.modes must be a non-empty list")

            seen_modes: set[str] = set()
            for mode in modes:
                if not isinstance(mode, str) or mode not in ALLOWED_MODES:
                    raise ContractGraphError(
                        f"{context}.modes contains invalid mode {mode!r}; "
                        f"allowed={sorted(ALLOWED_MODES)}"
                    )
                if mode in seen_modes:
                    raise ContractGraphError(f"{context}.modes repeats {mode!r}")
                seen_modes.add(mode)
                per_mode[mode].setdefault(source, set()).add(target)

    _validate_cycles(per_mode)


def load_graph(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractGraphError(f"cannot read {path}: {exc}") from exc
    validate_graph(data)
    return data


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print(f"usage: {Path(sys.argv[0]).name} [graph.json]", file=sys.stderr)
        return 2

    path = Path(args[0]) if args else DEFAULT_GRAPH
    try:
        load_graph(path)
    except ContractGraphError as exc:
        print(f"contract dependency graph invalid: {exc}", file=sys.stderr)
        return 1

    print(f"contract dependency graph valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
