#!/usr/bin/env bash
set -euo pipefail

FAIL=0
WARN=0

ok() { printf '  [ok] %s\n' "$1"; }
warn() { WARN=$((WARN + 1)); printf '  [warn] %s\n' "$1"; }
fail() { FAIL=$((FAIL + 1)); printf '  [fail] %s\n' "$1"; }

version_of() {
  "$@" 2>/dev/null | head -n 1
}

semver_from() {
  grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
}

require_command() {
  local command_name="$1"
  local purpose="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    ok "$command_name available ($purpose)"
  else
    fail "$command_name missing ($purpose)"
  fi
}

printf 'ListenCloser development environment\n'
printf '====================================\n'

require_command git "source control"
require_command node "frontend runtime; repository requires Node 22.x"
require_command npm "frontend package manager; repository requires npm 10.x"
require_command uv "locked Python environment; backend requires uv 0.12.6"

if command -v node >/dev/null 2>&1; then
  NODE_VERSION="$(node --version | sed 's/^v//')"
  case "$NODE_VERSION" in
    22.*) ok "Node $NODE_VERSION matches 22.x" ;;
    *) fail "Node $NODE_VERSION does not match required 22.x; with nvm, run 'nvm install' then 'nvm use' from the repository root" ;;
  esac
fi

if command -v npm >/dev/null 2>&1; then
  NPM_VERSION="$(npm --version)"
  case "$NPM_VERSION" in
    10.*) ok "npm $NPM_VERSION matches 10.x" ;;
    *) fail "npm $NPM_VERSION does not match required 10.x" ;;
  esac
fi

if command -v uv >/dev/null 2>&1; then
  UV_VERSION="$(uv --version | awk '{print $2}')"
  if [ "$UV_VERSION" = "0.12.6" ]; then
    ok "uv $UV_VERSION matches backend toolchain"
  else
    fail "uv $UV_VERSION does not match required 0.12.6"
  fi
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_VERSION="$(python3 -c 'import platform; print(platform.python_version())')"
  case "$PYTHON_VERSION" in
    3.11.*) ok "host Python $PYTHON_VERSION matches backend 3.11" ;;
    *) warn "host Python is $PYTHON_VERSION; backend commands use uv + .python-version to select Python 3.11" ;;
  esac
else
  warn "python3 is not on PATH; uv can still manage the backend Python 3.11 environment"
fi

printf '\nOptional tier prerequisites\n'
printf '%s\n' '---------------------------'
if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg available (backend media tests/database integration)"
else
  warn "ffmpeg missing; backend media/database integration tests may fail (the devcontainer provides it)"
fi

if command -v docker >/dev/null 2>&1; then
  ok "docker available (devcontainer/local database and container workflows)"
else
  warn "docker missing; core lint/unit work is still possible, but container/local database workflows are not"
fi

if command -v supabase >/dev/null 2>&1; then
  SUPABASE_VERSION="$(version_of supabase --version | semver_from || true)"
  if [ "$SUPABASE_VERSION" = "2.113.0" ]; then
    ok "Supabase CLI $SUPABASE_VERSION matches database/real-stack toolchain"
  else
    warn "Supabase CLI ${SUPABASE_VERSION:-unknown}; database/real-stack tiers use 2.113.0"
  fi
else
  warn "Supabase CLI missing; database/real-stack tiers require 2.113.0"
fi

if command -v tbls >/dev/null 2>&1; then
  TBLS_VERSION="$(
    { tbls version 2>/dev/null || tbls --version 2>/dev/null || true; } | semver_from || true
  )"
  if [ "$TBLS_VERSION" = "1.95.0" ]; then
    ok "tbls $TBLS_VERSION matches database documentation toolchain"
  else
    warn "tbls ${TBLS_VERSION:-unknown}; database verification uses 1.95.0"
  fi
else
  warn "tbls missing; database verification requires 1.95.0"
fi

printf '\nRepository state\n'
printf '%s\n' '----------------'
if [ -f package-lock.json ]; then
  ok "package-lock.json present; use npm ci (not npm install) for reproducible setup"
else
  fail "package-lock.json missing"
fi

if [ -f backend/uv.lock ] && [ -f backend/pyproject.toml ]; then
  ok "backend pyproject.toml + uv.lock present"
else
  fail "backend locked dependency authority is incomplete"
fi

if [ -f .nvmrc ] && [ "$(tr -d '[:space:]' < .nvmrc)" = "22" ]; then
  ok ".nvmrc pins Node 22"
else
  fail ".nvmrc is missing or does not pin Node 22"
fi

if [ -f .python-version ] && [ "$(tr -d '[:space:]' < .python-version)" = "3.11" ]; then
  ok ".python-version pins Python 3.11"
else
  fail ".python-version is missing or does not pin Python 3.11"
fi

printf '\nSummary\n'
printf '%s\n' '-------'
if [ "$FAIL" -ne 0 ]; then
  printf '%d required check(s) failed; fix them before running the canonical local gates.\n' "$FAIL"
  exit 1
fi

printf 'Core toolchain is ready.'
if [ "$WARN" -ne 0 ]; then
  printf ' %d optional warning(s) above only affect the named heavier tiers.' "$WARN"
fi
printf '\n'
printf 'Next: npm run bootstrap, then npm run check:fast.\n'
