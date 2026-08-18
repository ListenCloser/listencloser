"""Steady-state deploy invariants.

The deploy workflow must never mutate historical migration status or
force-replay migrations. A previous version of deploy-backend.yml ran

    supabase migration repair --status reverted 20260716 20260728
    supabase db push --include-all

on every deployment, which re-applied 202607160001_finetune_studio.sql and
recreated the permissive jobs/models policies and the vestigial models table
on the production database. The one-time history correction for that rename
transition lives in a separate, manually-triggered workflow
(.github/workflows/migrate-history-correction.yml) and must not re-enter the
steady-state deploy path.
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


def test_steady_state_deploy_never_force_replays_migrations() -> None:
    text = DEPLOY_WORKFLOW.read_text()
    assert (
        "--include-all" not in text
    ), "deploy-backend.yml must not force-replay already-applied migrations"
