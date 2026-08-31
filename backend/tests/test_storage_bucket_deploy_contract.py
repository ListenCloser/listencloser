"""Keep declarative Supabase Storage configuration in the production deploy path."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-backend.yml"
SUPABASE_CONFIG = REPO_ROOT / "supabase" / "config.toml"
LEGACY_POLICY_MIGRATION = (
    REPO_ROOT
    / "supabase"
    / "migrations"
    / "20260831232500_retire_remaining_legacy_storage_policies.sql"
)
LEGACY_BUCKETS = ("analysis", "enhanced", "library", "midi", "transcriptions")


def _bucket_config(config: str, bucket: str) -> str:
    return config.split(f"[storage.buckets.{bucket}]", 1)[1].split("[", 1)[0]


def test_deploy_triggers_on_supabase_storage_config() -> None:
    workflow = DEPLOY_WORKFLOW.read_text()
    assert "'supabase/config.toml'" in workflow


def test_deploy_syncs_buckets_after_database_migrations() -> None:
    workflow = DEPLOY_WORKFLOW.read_text()
    db_push = 'supabase db push --linked --include-all --password "$SUPABASE_DB_PASSWORD"'
    bucket_seed = "supabase seed buckets --linked"

    assert db_push in workflow
    assert bucket_seed in workflow
    assert workflow.index(db_push) < workflow.index(bucket_seed)


def test_artifact_bucket_contract_is_private_and_25_mib() -> None:
    config = SUPABASE_CONFIG.read_text()
    artifacts = _bucket_config(config, "artifacts")

    assert "public = false" in artifacts
    assert 'file_size_limit = "25MiB"' in artifacts


def test_retained_legacy_buckets_are_declaratively_private() -> None:
    config = SUPABASE_CONFIG.read_text()

    for bucket in LEGACY_BUCKETS:
        assert "public = false" in _bucket_config(config, bucket)


def test_legacy_policy_migration_does_not_mutate_bucket_metadata() -> None:
    migration = LEGACY_POLICY_MIGRATION.read_text().lower()

    assert "update storage.buckets" not in migration
    assert "delete from storage.buckets" not in migration
