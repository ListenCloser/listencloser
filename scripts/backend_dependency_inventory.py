#!/usr/bin/env python3
"""Inventory backend dependency ownership from the repository's Python import graph.

This is a characterization tool for issue #287. It does not decide that a
dependency is unused or safe to remove. Dependencies without first-party import
evidence remain visible as review/runtime-only candidates.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys
import tomllib
from collections import deque
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 1
REQUIREMENT_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")

# Distribution names and import names are not always the same. Keep this list
# limited to direct dependencies whose import surface cannot be derived safely
# by replacing '-' with '_'.
IMPORT_PREFIX_OVERRIDES: dict[str, tuple[str, ...]] = {
    "python-multipart": ("multipart",),
    "sentry-sdk": ("sentry_sdk",),
    "opentelemetry-api": ("opentelemetry",),
    "opentelemetry-sdk": ("opentelemetry.sdk",),
    "opentelemetry-exporter-otlp-proto-http": (
        "opentelemetry.exporter.otlp.proto.http",
    ),
    "opentelemetry-instrumentation-fastapi": (
        "opentelemetry.instrumentation.fastapi",
    ),
    "opentelemetry-instrumentation-httpx": (
        "opentelemetry.instrumentation.httpx",
    ),
    "basic-pitch": ("basic_pitch",),
    "pretty-midi": ("pretty_midi",),
    "pyfluidsynth": ("fluidsynth",),
    "beat-this": ("beat_this",),
    "lv-chordia": ("lv_chordia",),
}

# These are intentionally direct dependencies even though ListenCloser does not
# import them itself. Recording the reason is safer than teaching the inventory
# that "no import" means "unused".
RUNTIME_ONLY_REASONS: dict[str, str] = {
    "python-multipart": (
        "FastAPI loads python-multipart when parsing multipart/form-data; "
        "application code does not import it directly."
    ),
    "uvicorn": (
        "Uvicorn is the production ASGI process entrypoint, invoked as a command "
        "rather than imported by application modules."
    ),
    "setuptools": (
        "Compatibility pin: OpenTelemetry instrumentation 0.47b0 still imports "
        "pkg_resources, which setuptools 82 removed."
    ),
}

ENTRYPOINT_FILENAMES: dict[str, tuple[str, ...]] = {
    "api": ("main.py",),
    "worker": ("worker.py",),
}


def requirement_name(requirement: str) -> str:
    """Return the normalized distribution name from a PEP 508 requirement string."""
    match = REQUIREMENT_NAME_RE.match(requirement.strip())
    if not match:
        raise ValueError(f"cannot parse dependency requirement: {requirement!r}")
    return match.group(0).lower().replace("_", "-")


def import_prefixes(distribution_name: str) -> tuple[str, ...]:
    if distribution_name in IMPORT_PREFIX_OVERRIDES:
        return IMPORT_PREFIX_OVERRIDES[distribution_name]
    return (distribution_name.replace("-", "_"),)


def load_declared_dependencies(pyproject_path: Path) -> list[dict[str, str]]:
    with pyproject_path.open("rb") as handle:
        config = tomllib.load(handle)

    declared: list[dict[str, str]] = []
    for requirement in config.get("project", {}).get("dependencies", []):
        declared.append(
            {
                "name": requirement_name(requirement),
                "requirement": requirement,
                "declared_in": "project.dependencies",
            }
        )

    for group_name, requirements in sorted(config.get("dependency-groups", {}).items()):
        for requirement in requirements:
            declared.append(
                {
                    "name": requirement_name(requirement),
                    "requirement": requirement,
                    "declared_in": f"dependency-groups.{group_name}",
                }
            )
    return declared


def module_name_for_path(path: Path, backend_root: Path) -> str:
    relative = path.relative_to(backend_root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def module_aliases(path: Path, backend_root: Path) -> tuple[str, ...]:
    module = module_name_for_path(path, backend_root)
    if not module:
        return ("backend",)
    return (module, f"backend.{module}")


def discover_python_files(backend_root: Path) -> list[Path]:
    return sorted(
        path
        for path in backend_root.rglob("*.py")
        if "__pycache__" not in path.parts and ".venv" not in path.parts
    )


def resolve_relative_import(
    module: str | None,
    level: int,
    current_module: str,
    is_init: bool,
) -> str:
    if level == 0:
        return module or ""
    package = current_module if is_init else current_module.rpartition(".")[0]
    if not package:
        return module or ""
    relative = "." * level + (module or "")
    try:
        return importlib.util.resolve_name(relative, package)
    except (ImportError, ValueError):
        return module or ""


def imported_modules(path: Path, backend_root: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current_module = module_name_for_path(path, backend_root)
    is_init = path.name == "__init__.py"
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(node.module, node.level, current_module, is_init)
            if base:
                modules.add(base)
                for alias in node.names:
                    if alias.name != "*":
                        modules.add(f"{base}.{alias.name}")
    return modules


def build_module_index(files: Iterable[Path], backend_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in files:
        for alias in module_aliases(path, backend_root):
            index[alias] = path
    return index


def local_target(module: str, module_index: dict[str, Path]) -> Path | None:
    candidate = module
    while candidate:
        if candidate in module_index:
            return module_index[candidate]
        candidate, _, _ = candidate.rpartition(".")
    return None


def build_import_graph(
    files: Iterable[Path], backend_root: Path
) -> tuple[dict[Path, set[Path]], dict[Path, set[str]]]:
    file_list = list(files)
    module_index = build_module_index(file_list, backend_root)
    local_graph: dict[Path, set[Path]] = {}
    external_imports: dict[Path, set[str]] = {}

    for path in file_list:
        local: set[Path] = set()
        external: set[str] = set()
        for module in imported_modules(path, backend_root):
            target = local_target(module, module_index)
            if target is not None:
                if target != path:
                    local.add(target)
                continue
            root = module.split(".", 1)[0]
            if root in sys.stdlib_module_names or root == "__future__":
                continue
            external.add(module)
        local_graph[path] = local
        external_imports[path] = external

    return local_graph, external_imports


def entrypoint_groups(files: Iterable[Path], backend_root: Path) -> dict[str, list[Path]]:
    file_list = list(files)
    groups: dict[str, list[Path]] = {}
    for group, filenames in ENTRYPOINT_FILENAMES.items():
        groups[group] = [
            backend_root / filename
            for filename in filenames
            if (backend_root / filename).is_file()
        ]

    groups["evaluation"] = [
        path
        for path in file_list
        if "evaluation" in path.relative_to(backend_root).parts
        or path.name.endswith("_eval.py")
    ]
    groups["tests"] = [
        path for path in file_list if "tests" in path.relative_to(backend_root).parts
    ]
    return groups


def reachable_files(roots: Iterable[Path], graph: dict[Path, set[Path]]) -> set[Path]:
    seen: set[Path] = set()
    queue = deque(roots)
    while queue:
        path = queue.popleft()
        if path in seen or path not in graph:
            continue
        seen.add(path)
        queue.extend(sorted(graph[path]))
    return seen


def matched_dependency(
    imported_module: str, dependency_prefixes: dict[str, tuple[str, ...]]
) -> str | None:
    matches: list[tuple[int, str]] = []
    for dependency, prefixes in dependency_prefixes.items():
        for prefix in prefixes:
            if imported_module == prefix or imported_module.startswith(f"{prefix}."):
                matches.append((len(prefix), dependency))
    if not matches:
        return None
    longest = max(length for length, _ in matches)
    winners = sorted(dependency for length, dependency in matches if length == longest)
    return winners[0]


def _relative_paths(paths: Iterable[Path], repo_root: Path) -> list[str]:
    return sorted(path.relative_to(repo_root).as_posix() for path in paths)


def inventory(repo_root: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    backend_root = repo_root / "backend"
    pyproject_path = backend_root / "pyproject.toml"

    files = discover_python_files(backend_root)
    graph, external_imports = build_import_graph(files, backend_root)
    groups = entrypoint_groups(files, backend_root)
    reachable = {group: reachable_files(roots, graph) for group, roots in groups.items()}

    declared = load_declared_dependencies(pyproject_path)
    prefix_map = {item["name"]: import_prefixes(item["name"]) for item in declared}

    evidence: dict[str, dict[str, set[Path]]] = {
        item["name"]: {group: set() for group in groups} for item in declared
    }
    unmatched: dict[str, dict[str, set[Path]]] = {group: {} for group in groups}

    for group, reachable_group in reachable.items():
        for path in reachable_group:
            for module in external_imports[path]:
                dependency = matched_dependency(module, prefix_map)
                if dependency is None:
                    unmatched[group].setdefault(module, set()).add(path)
                    continue
                evidence[dependency][group].add(path)

    dependencies: list[dict[str, object]] = []
    for item in declared:
        name = item["name"]
        group_evidence = evidence[name]
        used_by = [group for group in groups if group_evidence[group]]
        dependencies.append(
            {
                **item,
                "import_prefixes": list(prefix_map[name]),
                "used_by": used_by,
                "runtime_only_reason": RUNTIME_ONLY_REASONS.get(name),
                "evidence": {
                    group: _relative_paths(paths, repo_root)
                    for group, paths in group_evidence.items()
                    if paths
                },
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "pyproject": pyproject_path.relative_to(repo_root).as_posix(),
            "backend_root": backend_root.relative_to(repo_root).as_posix(),
        },
        "entrypoints": {
            group: _relative_paths(roots, repo_root) for group, roots in groups.items()
        },
        "reachable_python_files": {group: len(paths) for group, paths in reachable.items()},
        "dependencies": dependencies,
        "declared_without_first_party_import_evidence": [
            item["name"] for item in dependencies if not item["used_by"]
        ],
        "unmatched_external_imports": {
            group: {
                module: _relative_paths(paths, repo_root)
                for module, paths in sorted(modules.items())
            }
            for group, modules in unmatched.items()
            if modules
        },
        "notes": [
            "Import evidence is source-graph evidence, not proof that a dependency is removable.",
            "Dynamic imports, framework-loaded plugins, command entrypoints, and "
            "transitive compatibility pins can have no first-party import.",
            "The inventory intentionally does not mutate pyproject.toml or uv.lock.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON instead of indented JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = inventory(args.repo_root)
    if args.compact:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())