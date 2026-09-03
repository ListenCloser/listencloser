"""Keep production release scope explicit across backend and database delivery."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = REPO_ROOT / "scripts" / "classify_production_scope.py"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-backend.yml"
SMOKE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "production-smoke.yml"


def _components(*paths: str) -> set[str]:
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER), "--production-scope"],
        input="\n".join(paths) + "\n",
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def test_release_classifier_separates_runtime_from_database() -> None:
    assert _components("backend/domain/job_worker.py") == {"backend"}
    assert _components("supabase/migrations/20260831_example.sql") == {"database"}
    assert _components("supabase/config.toml") == {"database"}
    assert _components(
        "backend/domain/job_worker.py",
        "supabase/migrations/20260831_example.sql",
    ) == {"backend", "database"}


def test_release_contract_changes_fail_closed_to_both_components() -> None:
    assert _components(".github/workflows/deploy-backend.yml") == {"backend", "database"}
    assert _components("scripts/classify_production_scope.py") == {"backend", "database"}


def test_backend_release_reconciles_database_before_runtime_deploy() -> None:
    workflow = DEPLOY_WORKFLOW.read_text()
    backend_reconciliation = (
        'if [[ "$backend" == "true" ]]; then\n'
        "            database=true\n"
        "          fi"
    )

    assert backend_reconciliation in workflow
    assert "needs: [scope, publish-image]" in workflow
    assert "needs: [scope, publish-image, migrate]" in workflow
    assert "needs.migrate.result == 'success'" in workflow


def test_deploy_workflow_can_migrate_without_publishing_runtime() -> None:
    workflow = DEPLOY_WORKFLOW.read_text()

    assert "needs.scope.outputs.backend == 'true'" in workflow
    assert "needs.scope.outputs.database == 'true'" in workflow
    assert "needs.publish-image.result == 'skipped'" in workflow
    assert "needs.publish-image.result == 'success'" in workflow
    assert "needs.migrate.result == 'success'" in workflow


def test_production_smoke_waits_for_database_delivery_without_requiring_release_sha() -> None:
    workflow = SMOKE_WORKFLOW.read_text()

    assert (
        "steps.scope.outputs.backend == 'true' || steps.scope.outputs.database == 'true'"
        in workflow
    )
    assert "REQUIRE_EXACT_BACKEND_RELEASE: ${{ steps.scope.outputs.backend }}" in workflow
