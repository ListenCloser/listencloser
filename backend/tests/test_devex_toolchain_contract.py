from __future__ import annotations

import json
import re

from tests.repository_paths import BACKEND_ROOT, REPOSITORY_ROOT


def _service_block(compose_text: str, service: str, next_service: str | None = None) -> str:
    start = compose_text.index(f"  {service}:\n")
    if next_service is None:
        return compose_text[start:]
    end = compose_text.index(f"  {next_service}:\n", start)
    return compose_text[start:end]


def test_node_acquisition_pin_matches_package_contract() -> None:
    package = json.loads((REPOSITORY_ROOT / "package.json").read_text())
    engine_range = package["engines"]["node"]
    dev_range = package["devEngines"]["runtime"]["version"]
    major_match = re.fullmatch(r"(\d+)\.x", engine_range)

    assert major_match is not None, "engines.node must declare one major as N.x"
    assert dev_range == engine_range
    assert (REPOSITORY_ROOT / ".nvmrc").read_text().strip() == major_match.group(1)


def test_root_package_owns_the_web_workspace_contract() -> None:
    root = json.loads((REPOSITORY_ROOT / "package.json").read_text())
    web = json.loads((REPOSITORY_ROOT / "apps" / "web" / "package.json").read_text())

    assert root["workspaces"] == ["apps/web"]
    assert web["name"] == "@listencloser/web"
    for script in ("dev", "build", "lint", "typecheck", "test"):
        assert root["scripts"][script].endswith("--workspace @listencloser/web")


def test_local_worker_consumes_worker_dependency_group() -> None:
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text()
    backend = _service_block(compose, "backend", "worker")
    worker = _service_block(compose, "worker")
    worker_sync = "uv sync --project /workspace/backend --locked --group worker"
    worker_run = "uv run --project /workspace/backend --group worker"

    assert worker_sync not in backend
    assert worker_run not in backend
    assert worker_sync in worker
    assert worker_run in worker


def test_dev_stack_uses_the_image_owned_soundfont() -> None:
    compose = (REPOSITORY_ROOT / "docker-compose.yml").read_text()
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text()

    assert "fluid-soundfont-gm" in dockerfile
    assert compose.count("SOUNDFONT_PATH=/usr/share/sounds/sf2/FluidR3_GM.sf2") == 2
    assert "backend/soundfonts" not in compose


def test_precommit_backend_hook_targets_live_contract_tests() -> None:
    config = (REPOSITORY_ROOT / ".pre-commit-config.yaml").read_text()
    targets = (
        "tests/test_audio_processing_security.py",
        "tests/test_domain_contracts.py",
    )

    for target in targets:
        assert target in config
        assert (BACKEND_ROOT / target).is_file()
