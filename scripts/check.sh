#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-full}"
PASS=0
FAIL=0
TOTAL_START=$SECONDS

pass() { PASS=$((PASS + 1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  ❌ $1"; }

usage() {
  cat <<'EOF'
Usage: scripts/check.sh [full|fast|frontend|backend|e2e]

  full      Canonical local gate: build, lint, typecheck, API contract,
            backend/frontend tests, optional backend health, and Playwright.
  fast      Inner loop: lint, typecheck, API contract, backend/frontend tests.
            Skips production build, live health checks, and Playwright.
  frontend  Frontend lint, typecheck, and Vitest only.
  backend   Locked backend sync, Ruff, API contract, and backend unit tests.
  e2e       Production frontend build and Playwright only.
EOF
}

case "$MODE" in
  full|fast|frontend|backend|e2e) ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown check mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac

needs_backend=false
case "$MODE" in
  full|fast|backend) needs_backend=true ;;
esac

if "$needs_backend" && ! command -v uv >/dev/null 2>&1; then
  echo "uv is required for '$MODE'. Install uv 0.12.6, then rerun this command." >&2
  exit 2
fi

run_frontend_build() {
  echo ""
  echo "── Frontend build ──"
  local started=$SECONDS
  if npm run build; then
    pass "build ($((SECONDS - started))s)"
  else
    fail "build ($((SECONDS - started))s)"
  fi
}

run_frontend_static() {
  echo ""
  echo "── Frontend lint ──"
  local started=$SECONDS
  if npm run lint; then
    pass "lint ($((SECONDS - started))s)"
  else
    fail "lint ($((SECONDS - started))s)"
  fi

  echo ""
  echo "── Frontend typecheck ──"
  started=$SECONDS
  if npm run typecheck; then
    pass "typecheck ($((SECONDS - started))s)"
  else
    fail "typecheck ($((SECONDS - started))s)"
  fi
}

run_frontend_tests() {
  echo ""
  echo "── Frontend tests ──"
  local started=$SECONDS
  if npm test; then
    pass "vitest ($((SECONDS - started))s)"
  else
    fail "vitest ($((SECONDS - started))s)"
  fi
}

run_backend_sync() {
  echo ""
  echo "── Locked backend environment ──"
  local started=$SECONDS
  if uv sync --project backend --locked; then
    pass "uv sync --locked ($((SECONDS - started))s)"
  else
    fail "uv sync --locked ($((SECONDS - started))s)"
  fi
}

run_backend_static() {
  echo ""
  echo "── Backend static checks ──"
  local started=$SECONDS
  if uv run --project backend --locked ruff check backend/ && \
     uv run --project backend --locked ruff format backend/ --check; then
    pass "ruff ($((SECONDS - started))s)"
  else
    fail "ruff ($((SECONDS - started))s)"
  fi

  echo ""
  echo "── Generated API contract ──"
  started=$SECONDS
  if npm run api:check; then
    pass "api contract ($((SECONDS - started))s)"
  else
    fail "api contract ($((SECONDS - started))s)"
  fi
}

run_backend_tests() {
  echo ""
  echo "── Backend tests ──"
  local started=$SECONDS
  if uv run --project backend --locked python -m pytest backend/tests/ -v \
      --durations=20 --durations-min=1.0; then
    pass "pytest ($((SECONDS - started))s)"
  else
    fail "pytest ($((SECONDS - started))s)"
  fi
}

run_backend_health() {
  echo ""
  echo "── Backend health (optional live service) ──"
  local be_url="${MUSIC_BACKEND_URL:-}"
  if [ -n "$be_url" ]; then
    local health
    local started=$SECONDS
    if health=$(curl -sf "$be_url/health/live"); then
      pass "health/live ($health, $((SECONDS - started))s)"
    else
      fail "health/live (unreachable, $((SECONDS - started))s)"
    fi
    started=$SECONDS
    if health=$(curl -sf "$be_url/health/ready"); then
      pass "health/ready ($health, $((SECONDS - started))s)"
    else
      fail "health/ready (unreachable, $((SECONDS - started))s)"
    fi
  else
    echo "  ℹ️  MUSIC_BACKEND_URL not set — live health checks not requested"
  fi
}

run_e2e() {
  echo ""
  echo "── Playwright E2E ──"
  local started=$SECONDS
  if npx playwright test --reporter=line; then
    pass "e2e ($((SECONDS - started))s)"
  else
    fail "e2e ($((SECONDS - started))s)"
  fi
}

echo "══════════════════════════════════════════"
echo "  hello-ai — $MODE check"
echo "══════════════════════════════════════════"

case "$MODE" in
  full)
    run_backend_sync
    run_frontend_build
    run_frontend_static
    run_backend_static
    run_backend_tests
    run_frontend_tests
    run_backend_health
    run_e2e
    ;;
  fast)
    run_frontend_static
    run_backend_static
    run_backend_tests
    run_frontend_tests
    ;;
  frontend)
    run_frontend_static
    run_frontend_tests
    ;;
  backend)
    run_backend_sync
    run_backend_static
    run_backend_tests
    ;;
  e2e)
    run_frontend_build
    run_e2e
    ;;
esac

echo ""
echo "══════════════════════════════════════════"
echo "  $PASS passed, $FAIL failed in $((SECONDS - TOTAL_START))s"
echo "══════════════════════════════════════════"
exit "$FAIL"
