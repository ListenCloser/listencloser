from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "recovery" / "backup-supabase.sh"
RECOVERY_DOC = REPO_ROOT / "docs" / "RECOVERY.md"


def test_backup_script_has_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(BACKUP_SCRIPT)], check=True)


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
