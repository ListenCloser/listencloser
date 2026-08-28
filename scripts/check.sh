#!/usr/bin/env bash
set -euo pipefail

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  ❌ $1"; }

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install uv 0.12.6, then rerun this command." >&2
  exit 2
fi

echo "══════════════════════════════════════════"
echo "  hello-ai — full check"
echo "══════════════════════════════════════════"
echo ""

echo "── Locked backend environment ──"
if uv sync --project backend --locked; then pass "uv sync --locked"; else fail "uv sync --locked"; fi

# ── Frontend ──────────────────────────────────
echo ""
echo "── Frontend build ──"
if npm run build; then pass "build"; else fail "build"; fi

echo ""
echo "── Frontend lint ──"
if npm run lint; then pass "lint"; else fail "lint"; fi

 echo ""
echo "── Frontend typecheck ──"
if npm run typecheck; then pass "typecheck"; else fail "typecheck"; fi

# ── Backend ───────────────────────────────────
echo ""
echo "── Backend (Python) ──"
if uv run --project backend ruff check backend/ && uv run --project backend ruff format backend/ --check; then
  pass "ruff"
else
  fail "ruff"
fi

echo ""
echo "── Backend tests ──"
if uv run --project backend python -m pytest backend/tests/ -v; then
  pass "pytest"
else
  fail "pytest"
fi

echo ""
echo "── Frontend tests ──"
if npm test; then
  pass "vitest"
else
  fail "vitest"
fi

echo ""
echo "── Backend health (optional live service) ──"
BE_URL="${MUSIC_BACKEND_URL:-}"
if [ -n "$BE_URL" ]; then
  if health=$(curl -sf "$BE_URL/health/live"); then
    pass "health/live ($health)"
  else
    fail "health/live (unreachable)"
  fi
  if health=$(curl -sf "$BE_URL/health/ready"); then
    pass "health/ready ($health)"
  else
    fail "health/ready (unreachable)"
  fi
else
  echo "  ℹ️  MUSIC_BACKEND_URL not set — live health checks not requested"
fi

# ── E2E ───────────────────────────────────────
echo ""
echo "── Playwright E2E ──"
if npx playwright test --reporter=line; then
  pass "e2e"
else
  fail "e2e"
fi

echo ""
echo "══════════════════════════════════════════"
echo "  $PASS passed, $FAIL failed"
echo "══════════════════════════════════════════"
exit $FAIL
