"""Docker Compose configuration invariants.

The backend container must receive the LLM provider configuration
(LLM_BASE_URL, LLM_API_KEY, LLM_MODEL) so the Ask feature can
reach the configured LLM provider. The worker container does NOT
need these credentials because no worker-invoked code path touches
the ask/ package.

Both long-lived services run the production image as a non-root user and must
also drop Docker's default Linux capability set. Deployment-only helper
containers may add back the minimum capabilities required to initialize the
shared runtime volume.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "backend" / "docker-compose.yml"
DEPLOY_PATH = REPO_ROOT / "scripts" / "deploy.sh"


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text())


def test_backend_service_has_llm_environment_variables() -> None:
    """The backend container must receive LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL."""
    compose = _load_compose()
    backend_env = compose["services"]["backend"]["environment"]
    for var in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        assert var in backend_env, (
            f"Backend service is missing {var} in docker-compose.yml environment. "
            f"The Ask endpoint requires this to reach the LLM provider."
        )


def test_worker_service_does_not_have_llm_credentials() -> None:
    """The worker must NOT receive LLM_API_KEY — no worker code path touches Ask."""
    compose = _load_compose()
    worker_env = compose["services"]["worker"]["environment"]
    assert "LLM_API_KEY" not in worker_env, (
        "Worker service must not receive LLM_API_KEY. "
        "No worker-invoked code path touches the ask/ package."
    )


def test_long_lived_services_drop_linux_capabilities_and_block_privilege_gain() -> None:
    compose = _load_compose()

    for service_name in ("backend", "worker"):
        service = compose["services"][service_name]
        assert service.get("cap_drop") == ["ALL"]
        assert service.get("security_opt") == ["no-new-privileges:true"]
        assert "cap_add" not in service


def test_runtime_volume_root_helpers_add_back_only_required_capabilities() -> None:
    deploy = DEPLOY_PATH.read_text()
    hardened_root_helper = "--cap-add CHOWN --cap-add DAC_OVERRIDE --user root"

    assert deploy.count(hardened_root_helper) == 2
