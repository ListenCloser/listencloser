"""Docker Compose configuration invariants.

The backend container must receive configuration required by API-only features.
The worker container should not receive API-only credentials or policy values.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE_PATH = Path(__file__).resolve().parents[1] / "docker-compose.yml"


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


def test_backend_service_receives_upload_size_policy() -> None:
    """Direct-upload authorization must use the configured deployment limit."""
    compose = _load_compose()
    backend_env = compose["services"]["backend"]["environment"]
    assert backend_env["MAX_UPLOAD_BYTES"] == "${MAX_UPLOAD_BYTES:-26214400}", (
        "Backend service must receive MAX_UPLOAD_BYTES with the documented 25 MB fallback."
    )


def test_worker_service_does_not_have_llm_credentials() -> None:
    """The worker must NOT receive LLM_API_KEY — no worker code path touches Ask."""
    compose = _load_compose()
    worker_env = compose["services"]["worker"]["environment"]
    assert "LLM_API_KEY" not in worker_env, (
        "Worker service must not receive LLM_API_KEY. "
        "No worker-invoked code path touches the ask/ package."
    )
