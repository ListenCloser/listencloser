#!/usr/bin/env bash
set -euo pipefail

# Capture a private, destination-agnostic Supabase recovery bundle.
# This script deliberately does not upload the bundle anywhere and never restores
# a database. The operator is responsible for moving a completed bundle to an
# off-site destination outside the Supabase project failure domain.

REQUIRED_SUPABASE_CLI_VERSION="2.113.0"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

fail() {
  printf 'backup failed: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

require_env() {
  [ -n "${!1:-}" ] || fail "required environment variable is not set: $1"
}

require_command supabase
require_command docker
require_command psql
require_command python3
require_command git

require_env SUPABASE_DB_URL
require_env SUPABASE_PROJECT_REF
require_env SUPABASE_ACCESS_TOKEN
require_env SUPABASE_DB_PASSWORD

actual_supabase_version="$(supabase --version | head -n 1 | tr -d '[:space:]')"
[ "$actual_supabase_version" = "$REQUIRED_SUPABASE_CLI_VERSION" ] || \
  fail "Supabase CLI $REQUIRED_SUPABASE_CLI_VERSION is required; found $actual_supabase_version"

OUTPUT_ROOT="${RECOVERY_OUTPUT_ROOT:-$HOME/.listencloser-recovery}"
OUTPUT_ROOT="$(python3 - "$OUTPUT_ROOT" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)"

case "$OUTPUT_ROOT" in
  "$REPO_ROOT"|"$REPO_ROOT"/*)
    fail "RECOVERY_OUTPUT_ROOT must be outside the Git repository"
    ;;
esac

BACKUP_DIR="$OUTPUT_ROOT/$SUPABASE_PROJECT_REF/$STAMP"
[ ! -e "$BACKUP_DIR" ] || fail "backup directory already exists: $BACKUP_DIR"
umask 077
mkdir -p "$BACKUP_DIR/database" "$BACKUP_DIR/storage"

TMP_PROJECT="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_PROJECT"
}
trap cleanup EXIT

printf 'Capturing database backup into a private local directory...\n'
supabase db dump --db-url "$SUPABASE_DB_URL" -f "$BACKUP_DIR/database/roles.sql" --role-only
supabase db dump --db-url "$SUPABASE_DB_URL" -f "$BACKUP_DIR/database/schema.sql"
supabase db dump --db-url "$SUPABASE_DB_URL" -f "$BACKUP_DIR/database/data.sql" \
  --use-copy --data-only \
  -x "storage.buckets_vectors" \
  -x "storage.vector_indexes"

# Migration history is intentionally separate because ordinary schema dumps do
# not make the repository's migration ledger a restoration authority.
supabase db dump --db-url "$SUPABASE_DB_URL" \
  -f "$BACKUP_DIR/database/history_schema.sql" --schema supabase_migrations
supabase db dump --db-url "$SUPABASE_DB_URL" \
  -f "$BACKUP_DIR/database/history_data.sql" --use-copy --data-only \
  --schema supabase_migrations

auth_users="$(psql "$SUPABASE_DB_URL" -X -A -t -v ON_ERROR_STOP=1 \
  -c 'select count(*)::bigint from auth.users;')"
storage_objects="$(psql "$SUPABASE_DB_URL" -X -A -t -v ON_ERROR_STOP=1 \
  -c 'select count(*)::bigint from storage.objects;')"

# Current Supabase platform->self-hosted restore guidance says the three-file
# dump contains auth.users and Storage metadata. Fail closed if the actual CLI
# stops satisfying that recovery contract while those tables contain data.
if [ "$auth_users" -gt 0 ] && \
   ! grep -Eq '^COPY (auth\.users|"auth"\."users") ' "$BACKUP_DIR/database/data.sql"; then
  fail "data dump omitted auth.users despite $auth_users current Auth rows"
fi
if [ "$storage_objects" -gt 0 ] && \
   ! grep -Eq '^COPY (storage\.objects|"storage"\."objects") ' "$BACKUP_DIR/database/data.sql"; then
  fail "data dump omitted storage.objects metadata despite $storage_objects current objects"
fi

psql "$SUPABASE_DB_URL" -X -A -t -F $'\t' -v ON_ERROR_STOP=1 > "$BACKUP_DIR/storage-inventory.tsv" <<'SQL'
select b.id,
       b.public::text,
       count(o.id)::bigint,
       count(*) filter (where o.id is not null and o.metadata ? 'size')::bigint,
       coalesce(sum(nullif(o.metadata->>'size', '')::bigint), 0)::bigint
from storage.buckets b
left join storage.objects o on o.bucket_id = b.id
group by b.id, b.public
order by b.id;
SQL

# Link from an isolated temporary Supabase workdir so backup capture never
# rewrites the repository's own linked-project state.
(
  cd "$TMP_PROJECT"
  supabase init >/dev/null
  supabase link --project-ref "$SUPABASE_PROJECT_REF" --password "$SUPABASE_DB_PASSWORD" >/dev/null
)

printf 'Copying Storage objects from every current bucket...\n'
while IFS=$'\t' read -r bucket public object_count sized_object_count expected_bytes; do
  [ -n "$bucket" ] || continue
  bucket_dir="$BACKUP_DIR/storage/$bucket"
  mkdir -p "$bucket_dir"

  if [ "$object_count" -gt 0 ]; then
    (
      cd "$TMP_PROJECT"
      supabase storage cp -r "ss://$bucket" "$bucket_dir" --experimental --linked
    )
  fi

  actual_count="$(find "$bucket_dir" -type f | wc -l | tr -d '[:space:]')"
  [ "$actual_count" -eq "$object_count" ] || \
    fail "bucket $bucket copied $actual_count files; expected $object_count"

  if [ "$sized_object_count" -eq "$object_count" ]; then
    actual_bytes="$(python3 - "$bucket_dir" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
print(sum(path.stat().st_size for path in root.rglob('*') if path.is_file()))
PY
)"
    [ "$actual_bytes" -eq "$expected_bytes" ] || \
      fail "bucket $bucket copied $actual_bytes bytes; expected $expected_bytes"
  fi

done < "$BACKUP_DIR/storage-inventory.tsv"

python3 - "$BACKUP_DIR" "$SUPABASE_PROJECT_REF" "$actual_supabase_version" "$auth_users" "$storage_objects" "$REPO_ROOT" <<'PY'
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1])
project_ref = sys.argv[2]
cli_version = sys.argv[3]
auth_users = int(sys.argv[4])
storage_objects = int(sys.argv[5])
repo_root = Path(sys.argv[6])

hashes_path = root / "private-file-hashes.jsonl"
with hashes_path.open("w", encoding="utf-8") as output:
    for path in sorted((root / "database").glob("*.sql")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        output.write(json.dumps({"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": digest}) + "\n")
    for path in sorted((root / "storage").rglob("*")):
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        output.write(json.dumps({"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}) + "\n")

try:
    repository_sha = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
except Exception:
    repository_sha = "unknown"

summary = {
    "schema_version": 1,
    "captured_at_utc": datetime.now(timezone.utc).isoformat(),
    "project_ref": project_ref,
    "repository_sha": repository_sha,
    "supabase_cli_version": cli_version,
    "auth_user_count": auth_users,
    "storage_object_count": storage_objects,
    "complete": True,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(root / "BACKUP_COMPLETE").write_text("complete\n", encoding="utf-8")
PY

printf 'Backup capture complete: %s\n' "$BACKUP_DIR"
printf 'Move this private directory to the approved off-site destination; local capture alone does not satisfy the RPO.\n'
