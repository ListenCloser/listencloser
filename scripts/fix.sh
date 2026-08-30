#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"

usage() {
  cat <<'EOF'
Usage: scripts/fix.sh [all|python|frontend]

  all       Apply safe Python and frontend autofixes.
  python    Apply Ruff safe fixes and formatting.
  frontend  Apply ESLint fixes.

This script never uses Ruff --unsafe-fixes. It is intended as a cheap pre-push
step; the normal CI/static checks remain authoritative for anything that cannot
be repaired deterministically.
EOF
}

case "$MODE" in
  all|python|frontend) ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown fix mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac

fix_python() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required for Python autofix (expected repository-pinned toolchain)." >&2
    exit 2
  fi

  echo "── Python autofix ──"
  uv run --project backend --locked ruff check backend/ --fix
  uv run --project backend --locked ruff format backend/
}

fix_frontend() {
  if [ ! -d node_modules ]; then
    echo "node_modules is missing; run npm ci before frontend autofix." >&2
    exit 2
  fi

  echo "── Frontend autofix ──"
  npm run lint:fix
}

case "$MODE" in
  all)
    fix_python
    fix_frontend
    ;;
  python)
    fix_python
    ;;
  frontend)
    fix_frontend
    ;;
esac
