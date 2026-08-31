"""Steady-state deploy migration-history invariants.

The deploy workflow must never mutate historical migration status. A previous
version of deploy-backend.yml combined

    supabase migration repair --status reverted 20260716 20260728
    supabase db push --include-all

on every deployment. The dangerous operation was the history rewrite: it made
already-applied migrations look pending, after which the push re-applied them
and recreated retired production objects/policies.

`db push --include-all` by itself has a different purpose in the current
merge-queue topology: it lets Supabase apply a genuinely missing local
migration whose timestamp sorts before the current remote tip. Already-recorded
migrations remain recorded and are not made pending. The one-time history
correction for the old rename transition stays in the separate manually
triggered workflow (.github/workflows/migrate-history-correction.yml).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-backend.yml"


def test_steady_state_deploy_never_repairs_migration_history() -> None:
    text = DEPLOY_WORKFLOW.read_text()
    assert (
        "migration repair" not in text
    ), "deploy-backend.yml must not mutate migration history during steady-state deploys"


def test_steady_state_deploy_applies_missing_out_of_order_history_without_repair() -> None:
    text = DEPLOY_WORKFLOW.read_text()
    command = 'supabase db push --linked --include-all --password "$SUPABASE_DB_PASSWORD"'

    assert command in text
    assert "migration repair" not in text
