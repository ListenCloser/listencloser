#!/usr/bin/env python3
"""Validate the narrow repo-native focused-contract dependency graph."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_MODES = {"discovery", "evaluation", "delivery"}
ISSUE_KEY = re.compile(r"[1-9][0-9]*")
DEFAULT_GRAPH = Path(__file__).resolve().parents[1] / "contract-dependencies.json"


class ContractGraphError(ValueError):
    pass


def _exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    if set(value) != expected:
        raise ContractGraphError(
            f"{where} keys must be exactly {sorted(expected)}; got {sorted(value)}"
        )


def validate_graph(data: Any) -> None:
    if not isinstance(data, dict):
        raise ContractGraphError("graph must be an object")
    _exact_keys(data, {"schema_version", "contracts"}, "graph")
    if data["schema_version"] != 1:
        raise ContractGraphError("schema_version must be 1")

    contracts = data["contracts"]
    if not isinstance(contracts, dict) or not contracts:
        raise ContractGraphError("contracts must be a non-empty object")

    by_mode: dict[str, dict[int, set[int]]] = {mode: {} for mode in ALLOWED_MODES}
    for source_key, contract in contracts.items():
        if not isinstance(source_key, str) or not ISSUE_KEY.fullmatch(source_key):
            raise ContractGraphError(f"invalid contract issue id: {source_key!r}")
        source = int(source_key)
        if not isinstance(contract, dict):
            raise ContractGraphError(f"contract #{source} must be an object")
        _exact_keys(contract, {"dependencies"}, f"contract #{source}")

        dependencies = contract["dependencies"]
        if not isinstance(dependencies, list) or not dependencies:
            raise ContractGraphError(f"contract #{source} needs at least one dependency")

        targets: set[int] = set()
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                raise ContractGraphError(f"contract #{source} dependency must be an object")
            _exact_keys(dependency, {"issue", "modes"}, f"contract #{source} dependency")

            target = dependency["issue"]
            if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
                raise ContractGraphError("dependency issue must be a positive integer")
            if target == source:
                raise ContractGraphError(f"contract #{source} cannot depend on itself")
            if target in targets:
                raise ContractGraphError(
                    f"contract #{source} repeats target #{target}; combine modes on one edge"
                )
            targets.add(target)

            modes = dependency["modes"]
            if not isinstance(modes, list) or not modes:
                raise ContractGraphError("dependency modes must be a non-empty list")
            if len(modes) != len(set(modes)):
                raise ContractGraphError("dependency modes must not repeat")
            invalid = [mode for mode in modes if mode not in ALLOWED_MODES]
            if invalid:
                raise ContractGraphError(f"invalid mode: {invalid[0]!r}")
            for mode in modes:
                by_mode[mode].setdefault(source, set()).add(target)

    for mode, edges in by_mode.items():
        visiting: set[int] = set()
        visited: set[int] = set()

        def visit(node: int) -> None:
            if node in visiting:
                raise ContractGraphError(f"{mode} dependency cycle")
            if node in visited:
                return
            visiting.add(node)
            for target in edges.get(node, ()):
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in edges:
            visit(node)


def load_graph(path: Path = DEFAULT_GRAPH) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractGraphError(f"cannot read {path}: {exc}") from exc
    validate_graph(data)
    return data


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_GRAPH
    if len(sys.argv) > 2:
        raise SystemExit("usage: contract_dependencies.py [graph.json]")
    try:
        load_graph(path)
    except ContractGraphError as exc:
        raise SystemExit(f"contract dependency graph invalid: {exc}") from exc
    print(f"contract dependency graph valid: {path}")
