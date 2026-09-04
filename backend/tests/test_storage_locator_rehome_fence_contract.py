from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    REPO_ROOT / "supabase" / "migrations" / "20260903195000_storage_locator_rehome_fence.sql"
)


def test_rehome_fence_serializes_every_version_insert_before_latest_check() -> None:
    sql = MIGRATION.read_text()

    key_share = sql.index("for key share;")
    recovery_branch = sql.index("storage_locator_rehome_v1")
    update_lock = sql.index("for update;")
    latest_check = sql.index("order by created_at desc, id desc")
    stale_rejection = sql.index("storage re-home source is no longer latest")

    assert key_share < recovery_branch < update_lock < latest_check < stale_rejection
    assert "before insert on public.artifact_versions" in sql


def test_rehome_fence_keeps_checks_inside_database_boundary() -> None:
    sql = MIGRATION.read_text()

    assert "new.parent_version_id" in sql
    assert "new.created_by is distinct from v_owner_id" in sql
    assert "new.produced_by_job_id is not null" in sql
    assert "new.storage_bucket is distinct from 'artifacts'" in sql
    assert "from storage.objects object" in sql
    assert "replacement Storage object does not exist in declared bucket" in sql
    assert "set search_path = ''" in sql
