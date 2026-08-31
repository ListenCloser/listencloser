"""Keep declarative Supabase Storage configuration in the production deploy path."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-backend.yml"
SUPABASE_CONFIG = REPO_ROOT / "supabase" / "config.toml"


def test_deploy_triggers_on_supabase_storage_config() -> None:
    workflow = DEPLOY_WORKFLOW.read_text()
    assert "'supabase/config.toml'" in workflow


def test_deploy_syncs_buckets_after_database_migrations() -> None:
    workflow = DEPLOY_WORKFLOW.read_text()
    db_push = 'supabase db push --linked --password "$SUPABASE_DB_PASSWORD"'
    bucket_seed = "supabase seed buckets --linked"

    assert db_push in workflow
    assert bucket_seed in workflow
    assert workflow.index(db_push) < workflow.index(bucket_seed)


def test_artifact_bucket_contract_is_private_and_25_mib() -> None:
    config = SUPABASE_CONFIG.read_text()
    artifacts = config.split("[storage.buckets.artifacts]", 1)[1].split("[", 1)[0]

    assert "public = false" in artifacts
    assert 'file_size_limit = "25MiB"' in artifacts
