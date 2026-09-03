#!/usr/bin/env bash
set -euo pipefail

SUPABASE_VERSION_REQUIRED="2.113.0"
TBLS_VERSION_REQUIRED="1.95.0"
STARTED_SUPABASE=false

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

cleanup() {
  if "$STARTED_SUPABASE"; then
    supabase stop --no-backup || true
  fi
}
trap cleanup EXIT INT TERM

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
  die "a local Supabase stack is already running; stop it with 'supabase stop --no-backup' so this check can own a fresh disposable database"
fi

echo "── Fresh database ──"
# `supabase start` creates the fresh local stack and applies migration history once.
# Do not immediately run `db reset`: CI previously observed Docker exit 125 while
# containers were still settling after that redundant second bootstrap.
supabase start
STARTED_SUPABASE=true

echo "── pgTAP database contracts ──"
supabase test db

echo "── Generated database documentation ──"
TBLS_DSN="pg://postgres:postgres@127.0.0.1:54322/postgres?sslmode=disable"
tbls diff "$TBLS_DSN" docs/generated/database --config supabase/tbls.yml

echo "── Locked backend + worker environment ──"
uv sync --project backend --locked --group worker

echo "── Backend integration tests ──"
eval "$(supabase status -o env)"
# Normalize version-dependent Supabase CLI names to the application contract.
export SUPABASE_URL="${SUPABASE_URL:-${API_URL:-http://127.0.0.1:54321}}"
export SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY}}"
export SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:-${ANON_KEY}}"
uv run --project backend python -m pytest backend/tests/ -m real_stack -v

echo "database check passed"
