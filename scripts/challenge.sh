#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-help}"
RESULTS_DIR="${CHALLENGE_RESULTS_DIR:-challenge-results}"
SCHEMATHESIS_VERSION="4.24.2"
AXE_VERSION="4.13.0"
LHCI_VERSION="0.15.1"
STRYKER_VERSION="10.0.0"

mkdir -p "$RESULTS_DIR"

usage() {
  cat <<'EOF'
Usage: scripts/challenge.sh <mode>

Advisory adversarial probes. These search for weaknesses; they are intentionally
separate from scripts/check.sh, which enforces already-understood invariants.

Modes:
  browser       Run accessibility + Lighthouse probes against a running frontend.
  a11y          Scan signed-out, authenticated desktop, and authenticated mobile UI.
  lighthouse    Collect a Lighthouse report for the running frontend.
  mutation-js   Mutation-test one bounded, high-value TypeScript policy module.
  api           Fuzz a LOCAL FastAPI/OpenAPI service with Schemathesis.
  all           Run browser + mutation-js; API also runs when CHALLENGE_API_URL is set.
  help          Show this help.

Environment:
  CHALLENGE_FRONTEND_URL     Frontend base URL (default http://127.0.0.1:3000)
  CHALLENGE_API_URL          FastAPI base URL for api mode
  CHALLENGE_OPENAPI_SCHEMA   Schema URL/path (default $CHALLENGE_API_URL/openapi.json)
  CHALLENGE_ALLOW_REMOTE_API=true
                             Explicit opt-in required before fuzzing a non-local API
  CHALLENGE_RESULTS_DIR      Output directory (default challenge-results)

Typical local use:
  # terminal 1: run the normal mock frontend
  NEXT_PUBLIC_MOCK_ENABLED=true npm run dev -- --hostname 127.0.0.1
  # terminal 2:
  npm run challenge -- browser

API fuzzing is deliberately local-only by default because generated requests may
exercise mutating endpoints. Point it at an isolated local/test stack, never prod.
EOF
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "challenge: required command not found: $1" >&2
    exit 2
  fi
}

frontend_url() {
  printf '%s' "${CHALLENGE_FRONTEND_URL:-http://127.0.0.1:3000}"
}

run_a11y() {
  require_command npm
  require_command node
  if [ ! -d node_modules/playwright ] && [ ! -d node_modules/@playwright/test ]; then
    echo "challenge: Playwright is not installed; run npm ci first" >&2
    exit 2
  fi

  echo ""
  echo "── Accessibility adversary (axe-core ${AXE_VERSION}) ──"
  local temp_dir
  temp_dir="$(mktemp -d)"
  trap 'rm -rf "${temp_dir:-}"' RETURN

  if ! npm install \
    --silent \
    --no-audit \
    --no-fund \
    --no-save \
    --package-lock=false \
    --prefix "$temp_dir" \
    "axe-core@${AXE_VERSION}"; then
    rm -rf "$temp_dir"
    trap - RETURN
    return 2
  fi

  local status=0
  set +e
  NODE_PATH="$temp_dir/node_modules${NODE_PATH:+:$NODE_PATH}" \
    CHALLENGE_FRONTEND_URL="$(frontend_url)" \
    CHALLENGE_RESULTS_DIR="$RESULTS_DIR" \
    node scripts/challenge-accessibility.cjs
  status=$?
  set -e

  rm -rf "$temp_dir"
  trap - RETURN
  return "$status"
}

run_lighthouse() {
  require_command npx
  local url
  url="$(frontend_url)"

  echo ""
  echo "── Browser quality adversary (Lighthouse CI ${LHCI_VERSION}) ──"
  rm -rf .lighthouseci "$RESULTS_DIR/lighthouse"
  mkdir -p "$RESULTS_DIR/lighthouse"

  local status=0
  set +e
  npx --yes --package="@lhci/cli@${LHCI_VERSION}" \
    lhci collect \
      --url="$url/" \
      --numberOfRuns=1
  status=$?
  set -e

  if [ -d .lighthouseci ]; then
    cp -R .lighthouseci/. "$RESULTS_DIR/lighthouse/"
  fi
  return "$status"
}

run_mutation_js() {
  require_command npx
  if [ ! -d node_modules/vitest ]; then
    echo "challenge: Vitest is not installed; run npm ci first" >&2
    exit 2
  fi

  echo ""
  echo "── Test-quality adversary (StrykerJS ${STRYKER_VERSION}) ──"
  local status=0
  set +e
  npx --yes \
    --package="@stryker-mutator/core@${STRYKER_VERSION}" \
    --package="@stryker-mutator/vitest-runner@${STRYKER_VERSION}" \
    stryker run stryker.config.mjs 2>&1 | tee "$RESULTS_DIR/mutation-js.txt"
  status=${PIPESTATUS[0]}
  set -e
  return "$status"
}

assert_local_api_or_opted_in() {
  local url="$1"
  case "$url" in
    http://localhost:*|https://localhost:*|http://127.0.0.1:*|https://127.0.0.1:*)
      return 0
      ;;
  esac

  if [ "${CHALLENGE_ALLOW_REMOTE_API:-false}" != "true" ]; then
    cat >&2 <<EOF
challenge: refusing to fuzz non-local API: $url
Schemathesis may exercise mutating endpoints. Use an isolated local/test stack.
If this remote target is intentionally disposable, set CHALLENGE_ALLOW_REMOTE_API=true.
EOF
    exit 2
  fi
}

run_api() {
  require_command uv
  local api_url="${CHALLENGE_API_URL:-}"
  if [ -z "$api_url" ]; then
    echo "challenge: CHALLENGE_API_URL is required for api mode" >&2
    exit 2
  fi
  assert_local_api_or_opted_in "$api_url"

  local schema="${CHALLENGE_OPENAPI_SCHEMA:-${api_url%/}/openapi.json}"
  echo ""
  echo "── API adversary (Schemathesis ${SCHEMATHESIS_VERSION}) ──"
  echo "Target: $api_url"
  echo "Schema: $schema"

  local status=0
  set +e
  uvx --from "schemathesis==${SCHEMATHESIS_VERSION}" \
    st run "$schema" \
      --url "$api_url" \
      --workers "${CHALLENGE_SCHEMATHESIS_WORKERS:-2}" \
      2>&1 | tee "$RESULTS_DIR/schemathesis.txt"
  status=${PIPESTATUS[0]}
  set -e
  return "$status"
}

record_status() {
  local current="$1"
  local latest="$2"
  if [ "$current" -eq 0 ]; then
    printf '%s' "$latest"
  else
    printf '%s' "$current"
  fi
}

case "$MODE" in
  browser)
    status=0
    run_a11y || status="$(record_status "$status" "$?")"
    run_lighthouse || status="$(record_status "$status" "$?")"
    exit "$status"
    ;;
  a11y)
    run_a11y
    ;;
  lighthouse)
    run_lighthouse
    ;;
  mutation-js)
    run_mutation_js
    ;;
  api)
    run_api
    ;;
  all)
    status=0
    run_a11y || status="$(record_status "$status" "$?")"
    run_lighthouse || status="$(record_status "$status" "$?")"
    run_mutation_js || status="$(record_status "$status" "$?")"
    if [ -n "${CHALLENGE_API_URL:-}" ]; then
      run_api || status="$(record_status "$status" "$?")"
    else
      echo ""
      echo "ℹ️  CHALLENGE_API_URL not set — destructive-capable API fuzzing skipped"
    fi
    exit "$status"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "challenge: unknown mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac
