from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "recovery" / "backup-supabase.sh"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "recovery" / "restore-supabase-isolated.sh"
STORAGE_RESTORE = REPO_ROOT / "scripts" / "recovery" / "restore-storage.mjs"
RECOVERY_DOC = REPO_ROOT / "docs" / "RECOVERY.md"


def test_recovery_shell_scripts_have_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(BACKUP_SCRIPT)], check=True)
    subprocess.run(["bash", "-n", str(RESTORE_SCRIPT)], check=True)


def test_storage_restore_has_valid_node_syntax() -> None:
    subprocess.run(["node", "--check", str(STORAGE_RESTORE)], check=True)


def test_backup_capture_is_private_complete_and_non_destructive() -> None:
    script = BACKUP_SCRIPT.read_text()

    assert 'REQUIRED_SUPABASE_CLI_VERSION="2.113.0"' in script
    assert "umask 077" in script
    assert "RECOVERY_OUTPUT_ROOT" in script
    assert "must be outside the Git repository" in script

    assert "auth.users" in script
    assert "storage.objects" in script
    assert "from storage.buckets b" in script
    assert "auth_storage_changes.sql" in script
    assert "supabase db diff --linked --schema auth,storage" in script
    assert 'supabase storage cp -r "ss:///$bucket"' in script
    assert "private-file-hashes.jsonl" in script
    assert "BACKUP_COMPLETE" in script

    # Capture must never grow into an automatic/destructive restore path.
    assert "supabase db reset --linked" not in script
    assert "supabase storage rm" not in script
    assert "drop database" not in script.lower()
    assert "delete from" not in script.lower()


def test_isolated_restore_fails_closed_before_mutation() -> None:
    script = RESTORE_SCRIPT.read_text()

    assert "I_UNDERSTAND_THIS_TARGET_IS_ISOLATED_AND_DISPOSABLE" in script
    assert "BACKUP_COMPLETE" in script
    assert "private-file-hashes.jsonl" in script
    assert "failed SHA-256 verification" in script
    assert "target identity matches the backup source" in script
    assert "target connection points at the backup source project" in script
    assert "isolated target already contains Auth users" in script
    assert "isolated target already contains Storage objects" in script
    assert "isolated target already contains ListenCloser domain tables" in script

    # The provider-managed diff must be reviewed/edited separately before apply.
    assert "RECOVERY_REVIEWED_AUTH_STORAGE_SQL" in script
    assert "refusing to apply the captured auth/storage diff" in script
    assert 'psql --quiet --single-transaction --variable ON_ERROR_STOP=1' in script
    assert '--file "$REVIEWED_OVERLAY"' in script


def test_isolated_restore_follows_provider_database_order_and_verifies_security() -> None:
    script = RESTORE_SCRIPT.read_text()

    roles = script.index('--file "$BUNDLE/database/roles.sql"')
    schema = script.index('--file "$BUNDLE/database/schema.sql"')
    replica = script.index("SET session_replication_role = replica")
    data = script.index('--file "$BUNDLE/database/data.sql"')
    history = script.index('--file "$BUNDLE/database/history_schema.sql"')
    assert roles < schema < replica < data < history

    assert "missing Version locator does not resolve" not in script
    assert "a restored Version locator does not resolve to Storage metadata" in script
    assert "required domain tables do not have RLS enabled" in script
    assert "browser roles regained domain DML privileges" in script
    assert "canonical artifacts bucket is missing or public" in script
    assert "Canonical product smoke" in script

    # Restore must never mutate Storage metadata directly; bytes go through API.
    assert "insert into storage.objects" not in script.lower()
    assert "update storage.objects" not in script.lower()
    assert "delete from storage.objects" not in script.lower()


def test_storage_bytes_restore_through_api_with_integrity_and_signed_read() -> None:
    script = STORAGE_RESTORE.read_text()

    assert 'from "@supabase/supabase-js"' in script
    assert "upsert: true" in script
    assert ".upload(objectName, bytes, options)" in script
    assert ".download(objectName)" in script
    assert "failed pre-upload integrity verification" in script
    assert "failed post-upload integrity verification" in script
    assert ".createSignedUrl(objectName, 60)" in script
    assert "private signed artifact read failed" in script

    # Object names, signed URLs, and file paths are private drill data.
    assert "console.log(objectName" not in script
    assert "console.log(filePath" not in script
    assert "console.log(signed.signedUrl" not in script


def test_recovery_runbook_keeps_restore_isolated_and_storage_separate() -> None:
    runbook = RECOVERY_DOC.read_text()

    assert "RPO target: 24 hours" in runbook
    assert "RTO target: 4 hours" in runbook
    assert "Database state" in runbook
    assert "Storage bytes" in runbook
    assert "auth_storage_changes.sql" in runbook
    assert "no automated production restore command" in runbook
    assert "BACKUP_COMPLETE" in runbook
    assert "Auth provider/OAuth configuration" in runbook
