from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _privileged_worker_runs(script: str) -> list[str]:
    normalized = script.replace("\\\n", " ")
    return re.findall(
        r'docker compose -f "\$COMPOSE" run --rm --no-deps --user root (.*?) --entrypoint sh worker',
        normalized,
    )


def test_privileged_deploy_helpers_strip_application_credentials() -> None:
    script = (REPO_ROOT / "scripts" / "deploy.sh").read_text()
    privileged_runs = _privileged_worker_runs(script)

    assert privileged_runs, "expected at least one privileged worker housekeeping helper"
    for run_args in privileged_runs:
        assert "-e SUPABASE_SERVICE_ROLE_KEY=" in run_args
        assert "-e SENTRY_DSN_BACKEND=" in run_args
        assert "-e OTEL_EXPORTER_OTLP_HEADERS=" in run_args
