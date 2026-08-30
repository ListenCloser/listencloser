from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _service_block(compose_text: str, service: str, next_service: str) -> str:
    start = compose_text.index(f"  {service}:\n")
    end = compose_text.index(f"  {next_service}:\n", start)
    return compose_text[start:end]


def _active_yaml_text(block: str) -> str:
    active_lines = []
    for line in block.splitlines():
        if not line.lstrip().startswith("#"):
            active_lines.append(line)
    return "\n".join(active_lines)


def test_default_agent_service_is_not_privileged() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text()
    opencode = _active_yaml_text(_service_block(compose, "opencode", "frontend"))

    assert "env_file:" not in opencode
    assert ".env.local" not in opencode
    assert "/var/run/docker.sock" not in opencode
    assert "SUPABASE_SERVICE_ROLE_KEY" not in opencode
    assert "SENTRY_ACCESS_TOKEN" not in opencode
    assert "SENTRY_AUTH_TOKEN" not in opencode


def test_devcontainer_uses_only_default_agent_service() -> None:
    devcontainer = (REPO_ROOT / ".devcontainer" / "devcontainer.json").read_text()

    assert '"dockerComposeFile": "../docker-compose.yml"' in devcontainer
    assert "agent-privileged" not in devcontainer


def test_privileged_agent_mode_is_explicit_override() -> None:
    override = (REPO_ROOT / "docker-compose.agent-privileged.yml").read_text()

    assert "Explicit opt-in override" in override
    assert "/var/run/docker.sock:/var/run/docker.sock" in override
    assert ".env.local" in override
    assert "SUPABASE_SERVICE_ROLE_KEY" in override


def test_devcontainer_cli_versions_are_explicit_and_supabase_matches_real_stack() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    real_stack = (REPO_ROOT / ".github" / "workflows" / "real-stack-e2e.yml").read_text()

    opencode_match = re.search(r"^ARG OPENCODE_VERSION=(\d+\.\d+\.\d+)$", dockerfile, re.MULTILINE)
    supabase_match = re.search(
        r"^ARG SUPABASE_CLI_VERSION=(\d+\.\d+\.\d+)$", dockerfile, re.MULTILINE
    )
    assert opencode_match is not None
    assert supabase_match is not None

    assert '"opencode-ai@${OPENCODE_VERSION}"' in dockerfile
    assert '"supabase@${SUPABASE_CLI_VERSION}"' in dockerfile
    assert "npm install -g opencode-ai supabase" not in dockerfile
    assert f"version: {supabase_match.group(1)}" in real_stack
