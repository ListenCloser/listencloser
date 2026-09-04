from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _service_block(compose_text: str, service: str, next_service: str | None = None) -> str:
    start = compose_text.index(f"  {service}:\n")
    if next_service is None:
        return compose_text[start:]
    end = compose_text.index(f"  {next_service}:\n", start)
    return compose_text[start:end]


def test_node_acquisition_pin_matches_package_contract() -> None:
    package = json.loads((REPO_ROOT / "package.json").read_text())
    engine_range = package["engines"]["node"]
    dev_range = package["devEngines"]["runtime"]["version"]
    major_match = re.fullmatch(r"(\d+)\.x", engine_range)

    assert major_match is not None, "engines.node must declare one major as N.x"
    assert dev_range == engine_range
    assert (REPO_ROOT / ".nvmrc").read_text().strip() == major_match.group(1)


def test_local_worker_consumes_worker_dependency_group() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    backend = _service_block(compose, "backend", "worker")
    worker = _service_block(compose, "worker")
    worker_sync = "uv sync --project /workspace/backend --locked --group worker"
    worker_run = "uv run --project /workspace/backend --group worker"

    assert worker_sync not in backend
    assert worker_run not in backend
    assert worker_sync in worker
    assert worker_run in worker
