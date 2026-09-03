#!/usr/bin/env bash
set -euo pipefail

# Restore a completed ListenCloser recovery bundle into an explicitly isolated,
# empty Supabase target. This command is intentionally unsuitable for production
# restore automation: it requires a hard acknowledgement, a fresh target, and a
# separately reviewed auth/storage overlay before it performs any mutation.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
STORAGE_RESTORE="$REPO_ROOT/scripts/recovery/restore-storage.mjs"
ACK_VALUE="I_UNDERSTAND_THIS_TARGET_IS_ISOLATED_AND_DISPOSABLE"

fail() {
  printf 'restore failed: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

require_env() {
  [ -n "${!1:-}" ] || fail "required environment variable is not set: $1"
}

[ "$#" -eq 1 ] || fail "usage: restore-supabase-isolated.sh <completed-backup-directory>"
require_command psql
require_command python3
require_command node

require_env RECOVERY_TARGET_DB_URL
require_env RECOVERY_TARGET_SUPABASE_URL
require_env RECOVERY_TARGET_SERVICE_ROLE_KEY
require_env RECOVERY_TARGET_ID
require_env RECOVERY_ISOLATED_TARGET_ACK
require_env RECOVERY_REVIEWED_AUTH_STORAGE_SQL

[ "$RECOVERY_ISOLATED_TARGET_ACK" = "$ACK_VALUE" ] || \
  fail "RECOVERY_ISOLATED_TARGET_ACK does not match the required isolated-target acknowledgement"

BUNDLE="$(python3 - "$1" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)"
[ -d "$BUNDLE" ] || fail "backup directory does not exist"
[ -f "$BUNDLE/BACKUP_COMPLETE" ] || fail "backup is missing BACKUP_COMPLETE"
[ "$(cat "$BUNDLE/BACKUP_COMPLETE")" = "complete" ] || fail "backup completion marker is invalid"

REVIEWED_OVERLAY="$(python3 - "$RECOVERY_REVIEWED_AUTH_STORAGE_SQL" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)"
[ -f "$REVIEWED_OVERLAY" ] || fail "reviewed auth/storage overlay file does not exist"
RAW_OVERLAY="$BUNDLE/database/auth_storage_changes.sql"
[ -f "$RAW_OVERLAY" ] || fail "backup is missing captured auth/storage overlay"
[ "$REVIEWED_OVERLAY" != "$RAW_OVERLAY" ] || \
  fail "refusing to apply the captured auth/storage diff without a separately reviewed copy"

umask 077
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# Validate the bundle and every private SQL/Storage hash before touching target state.
python3 - "$BUNDLE" <<'PY'
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
if summary.get("complete") is not True:
    raise SystemExit("restore failed: summary does not mark the backup complete")

manifest = root / "private-file-hashes.jsonl"
if not manifest.is_file():
    raise SystemExit("restore failed: private hash manifest is missing")

seen: set[str] = set()
for line in manifest.read_text(encoding="utf-8").splitlines():
    if not line:
        continue
    record = json.loads(line)
    relative = record.get("path")
    expected = record.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise SystemExit("restore failed: private hash manifest contains an invalid record")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise SystemExit("restore failed: private hash manifest escapes the backup directory") from None
    if not path.is_file():
        raise SystemExit("restore failed: a private manifest file is missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit("restore failed: a private backup file failed SHA-256 verification")
    seen.add(relative)

required_sql = {
    "database/roles.sql",
    "database/schema.sql",
    "database/data.sql",
    "database/history_schema.sql",
    "database/history_data.sql",
    "database/auth_storage_changes.sql",
}
if not required_sql.issubset(seen):
    raise SystemExit("restore failed: private hash manifest omits a required database file")

actual_storage = {
    str(path.relative_to(root)).replace("\\", "/")
    for path in (root / "storage").rglob("*")
    if path.is_file()
}
manifest_storage = {path for path in seen if path.startswith("storage/")}
if actual_storage != manifest_storage:
    raise SystemExit("restore failed: Storage files and private hash manifest do not match")
PY

SOURCE_PROJECT_REF="$(python3 - "$BUNDLE/summary.json" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["project_ref"])
PY
)"
[ "$RECOVERY_TARGET_ID" != "$SOURCE_PROJECT_REF" ] || fail "target identity matches the backup source"
case "$RECOVERY_TARGET_DB_URL $RECOVERY_TARGET_SUPABASE_URL" in
  *"$SOURCE_PROJECT_REF"*) fail "target connection points at the backup source project" ;;
esac

# A restore drill starts from an empty target. Refuse a target containing either
# user state or the ListenCloser application schema, even with acknowledgement.
IFS=$'\t' read -r target_auth_users target_storage_objects target_domain_tables < <(
  psql "$RECOVERY_TARGET_DB_URL" -X -A -t -F $'\t' -v ON_ERROR_STOP=1 -c "
    select
      (select count(*)::bigint from auth.users),
      (select count(*)::bigint from storage.objects),
      (select count(*)::bigint
         from information_schema.tables
        where table_schema = 'public'
          and table_name in ('projects','works','artifacts','artifact_versions','entities','insights','alignments','workflows','jobs'));"
)
[ "$target_auth_users" -eq 0 ] || fail "isolated target already contains Auth users"
[ "$target_storage_objects" -eq 0 ] || fail "isolated target already contains Storage objects"
[ "$target_domain_tables" -eq 0 ] || fail "isolated target already contains ListenCloser domain tables"

restore_started="$(date +%s)"
printf 'Restoring database state into verified empty isolated target...\n'
psql \
  --quiet \
  --single-transaction \
  --variable ON_ERROR_STOP=1 \
  --file "$BUNDLE/database/roles.sql" \
  --file "$BUNDLE/database/schema.sql" \
  --command 'SET session_replication_role = replica' \
  --file "$BUNDLE/database/data.sql" \
  --dbname "$RECOVERY_TARGET_DB_URL"

# Supabase requires custom auth/storage schema changes to be restored separately.
# The raw captured diff is never applied directly; the operator supplies a reviewed
# (and, if necessary, edited) copy for this isolated target's managed-schema version.
printf 'Applying separately reviewed auth/storage overlay...\n'
psql --quiet --single-transaction --variable ON_ERROR_STOP=1 \
  --file "$REVIEWED_OVERLAY" --dbname "$RECOVERY_TARGET_DB_URL"

printf 'Restoring repository migration history after schema/data verification phase...\n'
psql \
  --quiet \
  --single-transaction \
  --variable ON_ERROR_STOP=1 \
  --file "$BUNDLE/database/history_schema.sql" \
  --file "$BUNDLE/database/history_data.sql" \
  --dbname "$RECOVERY_TARGET_DB_URL"
restore_finished="$(date +%s)"

# Export only to a private temp file. Raw object names are needed to address the
# Storage API but are never emitted by the restore helper or retained as evidence.
STORAGE_METADATA="$TMP_DIR/storage-object-metadata.jsonl"
psql "$RECOVERY_TARGET_DB_URL" -X -A -t -v ON_ERROR_STOP=1 >"$STORAGE_METADATA" <<'SQL'
select json_build_object(
  'bucket', bucket_id,
  'name', name,
  'contentType', metadata->>'mimetype',
  'cacheControl', metadata->>'cacheControl'
)::text
from storage.objects
order by bucket_id, name;
SQL

validation_started="$(date +%s)"
printf 'Restoring and verifying Storage bytes through the Supabase Storage API...\n'
RECOVERY_TARGET_STORAGE_METADATA_JSONL="$STORAGE_METADATA" \
  node "$STORAGE_RESTORE" "$BUNDLE" >"$TMP_DIR/storage-result.json"

source_auth_users="$(python3 - "$BUNDLE/summary.json" <<'PY'
import json
import sys
print(int(json.load(open(sys.argv[1], encoding="utf-8"))["auth_user_count"]))
PY
)"
source_storage_objects="$(python3 - "$BUNDLE/summary.json" <<'PY'
import json
import sys
print(int(json.load(open(sys.argv[1], encoding="utf-8"))["storage_object_count"]))
PY
)"

IFS=$'\t' read -r restored_auth_users restored_storage_objects missing_version_objects missing_rls_tables browser_dml_grants artifact_bucket_public < <(
  psql "$RECOVERY_TARGET_DB_URL" -X -A -t -F $'\t' -v ON_ERROR_STOP=1 -c "
    with required_rls(table_name) as (
      values ('projects'),('works'),('artifacts'),('artifact_versions'),('entities'),('insights'),('alignments'),('workflows'),('jobs')
    ), rls_missing as (
      select count(*)::bigint as n
      from required_rls r
      left join pg_class c on c.relname = r.table_name
      left join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
      where n.oid is null or not c.relrowsecurity
    ), dml_grants as (
      select count(*)::bigint as n
      from information_schema.role_table_grants
      where table_schema = 'public'
        and table_name in ('projects','works','artifacts','artifact_versions','entities','insights','alignments','workflows','jobs')
        and grantee in ('anon','authenticated')
        and privilege_type in ('INSERT','UPDATE','DELETE')
    ), missing_objects as (
      select count(*)::bigint as n
      from public.artifact_versions v
      left join storage.objects o
        on o.bucket_id = v.storage_bucket and o.name = v.storage_key
      where o.id is null
    )
    select
      (select count(*)::bigint from auth.users),
      (select count(*)::bigint from storage.objects),
      (select n from missing_objects),
      (select n from rls_missing),
      (select n from dml_grants),
      coalesce((select public::text from storage.buckets where id = 'artifacts'), 'missing');"
)

[ "$restored_auth_users" -eq "$source_auth_users" ] || fail "restored Auth count does not match backup summary"
[ "$restored_storage_objects" -eq "$source_storage_objects" ] || fail "restored Storage metadata count does not match backup summary"
[ "$missing_version_objects" -eq 0 ] || fail "a restored Version locator does not resolve to Storage metadata"
[ "$missing_rls_tables" -eq 0 ] || fail "one or more required domain tables do not have RLS enabled"
[ "$browser_dml_grants" -eq 0 ] || fail "browser roles regained domain DML privileges during restore"
[ "$artifact_bucket_public" = "false" ] || fail "canonical artifacts bucket is missing or public after restore"
validation_finished="$(date +%s)"

python3 - "$TMP_DIR/storage-result.json" "$((restore_finished - restore_started))" "$((validation_finished - validation_started))" <<'PY'
import json
import sys
storage = json.load(open(sys.argv[1], encoding="utf-8"))
print(json.dumps({
    "database_restore_seconds": int(sys.argv[2]),
    "validation_seconds": int(sys.argv[3]),
    "restored_storage_objects": storage["restored_storage_objects"],
    "restored_storage_bytes": storage["restored_storage_bytes"],
    "private_signed_read_verified": storage["private_signed_read_verified"],
    "auth_count_parity": True,
    "storage_count_parity": True,
    "version_storage_metadata_lineage_verified": True,
    "domain_rls_verified": True,
    "browser_dml_revocation_verified": True,
}, sort_keys=True))
PY

printf 'Isolated database + Storage restore validation complete.\n'
printf 'Canonical product smoke and provider/Auth configuration verification remain operator gates before this drill can satisfy #633.\n'
