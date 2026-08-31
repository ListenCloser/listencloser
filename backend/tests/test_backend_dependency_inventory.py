from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_inventory_module():
    script = Path(__file__).resolve().parents[2] / "scripts" / "backend_dependency_inventory.py"
    spec = importlib.util.spec_from_file_location("backend_dependency_inventory", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory_module = _load_inventory_module()


def _write_project(tmp_path: Path) -> Path:
    backend = tmp_path / "backend"
    (backend / "evaluation").mkdir(parents=True)
    (backend / "tests").mkdir()
    (backend / "pyproject.toml").write_text(
        """
[project]
name = "fixture"
version = "0.1.0"
dependencies = [
  "fastapi==1.0",
  "httpx>=0.27",
  "torch==2.6.0",
  "numpy==1.26.4",
  "python-multipart==0.0.20",
]

[dependency-groups]
dev = ["pytest==9.1.1"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (backend / "main.py").write_text(
        "import fastapi\nfrom shared import helper\n",
        encoding="utf-8",
    )
    (backend / "worker.py").write_text(
        "import torch\nfrom shared import helper\n",
        encoding="utf-8",
    )
    (backend / "shared.py").write_text("import httpx\n", encoding="utf-8")
    (backend / "evaluation" / "probe.py").write_text("import numpy\n", encoding="utf-8")
    (backend / "tests" / "test_worker.py").write_text(
        "import pytest\nimport worker\n",
        encoding="utf-8",
    )
    return tmp_path


def test_requirement_name_handles_extras_and_normalizes() -> None:
    assert inventory_module.requirement_name("uvicorn[standard]==0.30.6") == "uvicorn"
    assert inventory_module.requirement_name("sentry_sdk>=2") == "sentry-sdk"


def test_inventory_uses_transitive_source_graph_for_entrypoint_ownership(tmp_path: Path) -> None:
    repo = _write_project(tmp_path)
    payload = inventory_module.inventory(repo)
    dependencies = {item["name"]: item for item in payload["dependencies"]}

    assert dependencies["fastapi"]["used_by"] == ["api"]
    assert dependencies["httpx"]["used_by"] == ["api", "worker", "tests"]
    assert dependencies["torch"]["used_by"] == ["worker", "tests"]
    assert dependencies["numpy"]["used_by"] == ["evaluation"]
    assert dependencies["pytest"]["used_by"] == ["tests"]


def test_runtime_only_dependency_is_not_mislabeled_as_import_backed(tmp_path: Path) -> None:
    repo = _write_project(tmp_path)
    payload = inventory_module.inventory(repo)
    dependencies = {item["name"]: item for item in payload["dependencies"]}

    multipart = dependencies["python-multipart"]
    assert multipart["used_by"] == []
    assert "FastAPI" in multipart["runtime_only_reason"]
    assert "python-multipart" in payload["declared_without_first_party_import_evidence"]


def test_unmatched_external_imports_remain_visible(tmp_path: Path) -> None:
    repo = _write_project(tmp_path)
    (repo / "backend" / "worker.py").write_text(
        "import torch\nimport mystery_plugin\nfrom shared import helper\n",
        encoding="utf-8",
    )

    payload = inventory_module.inventory(repo)

    assert payload["unmatched_external_imports"]["worker"]["mystery_plugin"] == [
        "backend/worker.py"
    ]


def test_current_repository_inventory_is_parseable() -> None:
    repo = Path(__file__).resolve().parents[2]
    payload = inventory_module.inventory(repo)
    dependencies = {item["name"]: item for item in payload["dependencies"]}

    assert payload["entrypoints"]["api"] == ["backend/main.py"]
    assert payload["entrypoints"]["worker"] == ["backend/worker.py"]
    assert {"fastapi", "basic-pitch", "lv-chordia", "pytest"} <= dependencies.keys()
    assert payload["reachable_python_files"]["api"] > 0
    assert payload["reachable_python_files"]["worker"] > 0
