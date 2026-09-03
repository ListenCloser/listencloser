#!/usr/bin/env bash
set -euo pipefail

SUPABASE_VERSION_REQUIRED="2.113.0"
TBLS_VERSION_REQUIRED="1.95.0"
STARTED_SUPABASE=false
SUPABASE_WORKDIR=""

die() {
  echo "database check: $*" >&2
  exit 2
}

require_command() {
  local command_name="$1"
  local purpose="$2"
  command -v "$command_name" >/dev/null 2>&1 || die "$command_name is required ($purpose)"
}

semver_from() {
  grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
}

supabase_in_check() {
  (cd "$SUPABASE_WORKDIR" && supabase "$@")
}

cleanup() {
  if "$STARTED_SUPABASE" && [ -n "$SUPABASE_WORKDIR" ]; then
    supabase_in_check stop --no-backup || true
  fi
  if [ -n "$SUPABASE_WORKDIR" ]; then
    rm -rf "$SUPABASE_WORKDIR"
  fi
}
trap cleanup EXIT INT TERM

require_command git "tracked Supabase fixture isolation"
require_command docker "fresh local Supabase"
require_command supabase "database migrations and pgTAP"
require_command tbls "generated database documentation"
require_command uv "locked backend integration environment"
require_command ffmpeg "backend media integration tests"

docker info >/dev/null 2>&1 || die "Docker daemon is not available"

supabase_version="$(supabase --version 2>/dev/null | semver_from || true)"
if [ "$supabase_version" != "$SUPABASE_VERSION_REQUIRED" ]; then
  die "Supabase CLI $SUPABASE_VERSION_REQUIRED is required; found ${supabase_version:-unknown}"
fi

tbls_version="$(
  { tbls version 2>/dev/null || tbls --version 2>/dev/null || true; } | semver_from || true
)"
if [ "$tbls_version" != "$TBLS_VERSION_REQUIRED" ]; then
  die "tbls $TBLS_VERSION_REQUIRED is required; found ${tbls_version:-unknown}"
fi

if supabase status >/dev/null 2>&1; then
  die "a local Supabase stack is already running; stop it normally before running this isolated database check"
fi

# `supabase stop` preserves local data by default, so a stopped developer stack
# may still own persisted volumes even when `supabase status` is down. Build the
# verification stack from tracked Supabase files in a temporary workdir and give
# it a distinct project_id; cleanup can then use --no-backup without touching the
# developer project's stopped or running data.
SUPABASE_WORKDIR="$(mktemp -d)"
while IFS= read -r -d '' source_path; do
  destination="$SUPABASE_WORKDIR/$source_path"
  mkdir -p "$(dirname "$destination")"
  cp "$source_path" "$destination"
done < <(git ls-files -z supabase)

isolated_project_id="listencloser-check-$$-$RANDOM"
awk -v project_id="$isolated_project_id" '
  /^project_id = / {
    print "project_id = \"" project_id "\""
    next
  }
  { print }
' "$SUPABASE_WORKDIR/supabase/config.toml" > "$SUPABASE_WORKDIR/supabase/config.toml.tmp"
mv "$SUPABASE_WORKDIR/supabase/config.toml.tmp" "$SUPABASE_WORKDIR/supabase/config.toml"

echo "── Fresh isolated database ($isolated_project_id) ──"
# On the isolated project `supabase start` creates the database and applies the
# migration history once. Do not immediately run `db reset`: CI previously
# observed Docker exit 125 while containers were still settling after that
# redundant second bootstrap.
supabase_in_check start
STARTED_SUPABASE=true

echo "── pgTAP database contracts ──"
supabase_in_check test db

echo "── Generated database documentation ──"
TBLS_DSN="pg://postgres:postgres@127.0.0.1:54322/postgres?sslmode=disable"
tbls diff "$TBLS_DSN" docs/generated/database --config supabase/tbls.yml

echo "── Locked backend + worker environment ──"
uv sync --project backend --locked --group worker

echo "── Backend integration tests ──"
eval "$(supabase_in_check status -o env)"
# Normalize version-dependent Supabase CLI names to the application contract.
export SUPABASE_URL="${SUPABASE_URL:-${API_URL:-http://127.0.0.1:54321}}"
export SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY}}"
export SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:-${ANON_KEY}}"
uv run --project backend python -m pytest backend/tests/ -m real_stack -v

echo "database check passed"
