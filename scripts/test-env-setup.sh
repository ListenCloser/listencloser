#!/usr/bin/env bash
set -euo pipefail

# ────────────────────────────────────────────────────────────────────────────
# test-env-setup.sh — seed a test environment for the listencloser feedback loop
# ────────────────────────────────────────────────────────────────────────────
# Creates test users, seeds a project with sample data, and exports the
# TEST_RUN_ID so downstream tests/teardown can scope across namespaced records.
#
# Required env vars:
#   SUPABASE_URL               https://<ref>.supabase.co
#   SUPABASE_SERVICE_ROLE_KEY  supabase service-role JWT
#
# Optional env vars:
#   TEST_AUDIO_DIR             path to audio fixtures (default: tests/fixtures/audio)
#   TEST_USER_EMAIL            base email for test users (default: test+run_{run_id}@listencloser.dev)
#   TEST_USER_PASSWORD         password for test users (default: auto-generated)
#   SUPABASE_ANON_KEY          anon key (used for some client operations)
#
# Generates:
#   TEST_RUN_ID                timestamp-based unique id, e.g. test_20260728_143022_abc123
#   TEST_PROJECT_ID            UUID of seeded project
#   TEST_USER_IDS              comma-separated test user UUIDs
#   TEST_JWT_TOKENS            comma-separated access tokens for each test user
# ────────────────────────────────────────────────────────────────────────────

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  ❌ $1"; }
warn() { echo "  ⚠️  $1"; }

echo "══════════════════════════════════════════"
echo "  listencloser — test environment setup"
echo "══════════════════════════════════════════"
echo ""

# ── Safe-guard: never run against production ───────────────────────────────
PROD_GUARD_FILE=".env.test-guard"
if [ ! -f "$PROD_GUARD_FILE" ]; then
  echo ""
  echo "  ⚠️  WARNING: No .env.test-guard file found."
  echo "  This script uses the Supabase ADMIN API to create users and seed data."
  echo "  It should ONLY run against a dedicated test/staging Supabase project."
  echo ""
  cat <<'GUARDEOF'
To create the guard file:
  echo "test-only" > .env.test-guard

If you understand the risk and this IS a test project, set:
  export BYPASS_PROD_GUARD=1
GUARDEOF
  if [ "${BYPASS_PROD_GUARD:-}" != "1" ]; then
    echo ""
    echo "  Aborting. Set BYPASS_PROD_GUARD=1 to override."
    exit 1
  fi
fi

# ── Validate required env vars ─────────────────────────────────────────────
echo "── Checking environment ──"

REQUIRED_VARS=(
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
)

for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    fail "$var is not set"
  else
    pass "$var is set"
  fi
done

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "  Missing required environment variables. Aborting."
  exit 1
fi

SUPABASE_URL="${SUPABASE_URL%/}"

# ── Generate run ID ────────────────────────────────────────────────────────
RUN_TS=$(date -u +%Y%m%d_%H%M%S)
RUN_RANDOM=$(python3 -c "import secrets; print(secrets.token_hex(3))" 2>/dev/null || openssl rand -hex 3)
TEST_RUN_ID="test_${RUN_TS}_${RUN_RANDOM}"
export TEST_RUN_ID

echo ""
echo "  Run ID:  $TEST_RUN_ID"
echo "  URL:     $SUPABASE_URL"
echo ""

# ── Defaults ───────────────────────────────────────────────────────────────
TEST_USER_EMAIL="${TEST_USER_EMAIL:-test+run_${RUN_TS}@listencloser.dev}"
TEST_USER_PASSWORD="${TEST_USER_PASSWORD:-$(python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24)))" 2>/dev/null || openssl rand -base64 18)}"
TEST_AUDIO_DIR="${TEST_AUDIO_DIR:-${PWD}/tests/fixtures/audio}"

echo "  Test user: ${TEST_USER_EMAIL}"
echo ""

# ── Create test users via Supabase Admin API ───────────────────────────────
echo "── Creating test users ──"

create_user() {
  local email="$1"
  local password="$2"
  local display_name="$3"

  local resp
  resp=$(curl -sS -w "\n%{http_code}" \
    -X POST "${SUPABASE_URL}/auth/v1/admin/users" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -d "$(cat <<EOF
{
  "email": "${email}",
  "password": "${password}",
  "email_confirm": true,
  "user_metadata": {
    "display_name": "${display_name}",
    "test_run_id": "${TEST_RUN_ID}"
  }
}
EOF
)" 2>&1)

  local status_code
  status_code=$(echo "$resp" | tail -1)
  local body
  body=$(echo "$resp" | sed '$d')

  if [ "$status_code" -ge 200 ] && [ "$status_code" -lt 300 ]; then
    local user_id
    user_id=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
    if [ -n "$user_id" ]; then
      echo "$user_id"
      return 0
    fi
  fi

  if echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('code')=='user_already_exists' else 1)" 2>/dev/null; then
    warn "User ${email} already exists — fetching existing user"
    local existing
    existing=$(curl -sS "${SUPABASE_URL}/auth/v1/admin/users?email=${email}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null)
    local existing_id
    existing_id=$(echo "$existing" | python3 -c "import sys,json; users=json.load(sys.stdin).get('users',[]); print(users[0].get('id','') if users else '')" 2>/dev/null || echo "")
    if [ -n "$existing_id" ]; then
      echo "$existing_id"
      return 0
    fi
  fi

  echo "ERROR:${status_code}:${body}" >&2
  return 1
}

USER_IDS=()
JWT_TOKENS=()

# Create owner user
echo "  Creating owner user..."
OWNER_ID=$(create_user "${TEST_USER_EMAIL}" "${TEST_USER_PASSWORD}" "Test Owner (${TEST_RUN_ID})")
if [[ "$OWNER_ID" == ERROR:* ]]; then
  fail "owner user creation — $(echo "$OWNER_ID" | cut -d: -f3-)"
  exit 1
fi
USER_IDS+=("$OWNER_ID")
pass "owner user created ($OWNER_ID)"

# Create collaborator user
COLLAB_EMAIL="test+collab_${RUN_TS}@listencloser.dev"
COLLAB_PASS=$(python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))" 2>/dev/null || openssl rand -base64 18)
echo "  Creating collaborator user..."
COLLAB_ID=$(create_user "${COLLAB_EMAIL}" "${COLLAB_PASS}" "Test Collaborator (${TEST_RUN_ID})")
if [[ "$COLLAB_ID" == ERROR:* ]]; then
  fail "collaborator user creation — $(echo "$COLLAB_ID" | cut -d: -f3-)"
  exit 1
fi
USER_IDS+=("$COLLAB_ID")
pass "collaborator user created ($COLLAB_ID)"

# ── Sign in to get JWT tokens ─────────────────────────────────────────────
echo ""
echo "── Obtaining auth tokens ──"

get_token() {
  local email="$1"
  local password="$2"

  local resp
  resp=$(curl -sS -w "\n%{http_code}" \
    -X POST "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
    -H "Content-Type: application/json" \
    -H "apikey: ${SUPABASE_ANON_KEY:-${SUPABASE_SERVICE_ROLE_KEY}}" \
    -d "{\"email\":\"${email}\",\"password\":\"${password}\",\"gotrue_meta_security\":{}}" 2>/dev/null)

  local status_code
  status_code=$(echo "$resp" | tail -1)
  local body
  body=$(echo "$resp" | sed '$d')

  if [ "$status_code" -ge 200 ] && [ "$status_code" -lt 300 ]; then
    echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null
    return 0
  fi
  return 1
}

OWNER_TOKEN=$(get_token "${TEST_USER_EMAIL}" "${TEST_USER_PASSWORD}")
if [ -z "$OWNER_TOKEN" ]; then
  fail "owner token — could not sign in (email=${TEST_USER_EMAIL})"
  exit 1
fi
JWT_TOKENS+=("$OWNER_TOKEN")
pass "owner token obtained"

COLLAB_TOKEN=$(get_token "${COLLAB_EMAIL}" "${COLLAB_PASS}")
if [ -z "$COLLAB_TOKEN" ]; then
  fail "collaborator token — could not sign in"
  exit 1
fi
JWT_TOKENS+=("$COLLAB_TOKEN")
pass "collaborator token obtained"

# ── Seed test project via domain API ───────────────────────────────────────
echo ""
echo "── Seeding test data ──"

api_call() {
  local method="$1"
  local path="$2"
  local token="$3"
  local data="${4:-}"

  local args=(-sS -X "$method" "${SUPABASE_URL}/rest/v1${path}" -H "Authorization: Bearer ${token}" -H "apikey: ${SUPABASE_ANON_KEY:-${SUPABASE_SERVICE_ROLE_KEY}}" -H "Content-Type: application/json" -H "Prefer: return=representation")
  if [ -n "$data" ]; then
    args+=(-d "$data")
  fi
  curl "${args[@]}" 2>/dev/null
}

# Note: The domain API lives on the FastAPI backend, not Supabase.
# We seed directly via the Supabase REST API (service role) for simplicity,
# which is equivalent to what the domain repos do under the hood.

seed_via_db() {
  local qualifier="${TEST_RUN_ID/_/-}"

  # Create project
  local project_json
  project_json=$(cat <<EOF
{"owner_id":"${OWNER_ID}","name":"Seed Project - ${qualifier}","description":"Auto-seeded test project for ${TEST_RUN_ID}","created_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","updated_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
)

  local project_resp
  project_resp=$(curl -sS -w "\n%{http_code}" \
    -X POST "${SUPABASE_URL}/rest/v1/projects" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    -d "$project_json" 2>/dev/null)

  local project_status
  project_status=$(echo "$project_resp" | tail -1)
  if [ "$project_status" -lt 200 ] || [ "$project_status" -ge 300 ]; then
    echo "ERROR:project:$(echo "$project_resp" | sed '$d')" >&2
    return 1
  fi

  local project_id
  project_id=$(echo "$project_resp" | sed '$d' | python3 -c "import sys,json; print(json.load(sys.stdin)[0].get('id',''))" 2>/dev/null)
  if [ -z "$project_id" ]; then
    echo "ERROR:project:no_id" >&2
    return 1
  fi

  echo "$project_id"
}

TEST_PROJECT_ID=$(seed_via_db)
if [[ "$TEST_PROJECT_ID" == ERROR:* ]]; then
  fail "project seeding — $(echo "$TEST_PROJECT_ID" | cut -d: -f3-)"
  exit 1
fi
export TEST_PROJECT_ID
pass "test project created ($TEST_PROJECT_ID)"

# ── Create a test work ─────────────────────────────────────────────────────
echo ""
echo "  Creating test work..."

WORK_JSON=$(cat <<EOF
{"project_id":"${TEST_PROJECT_ID}","title":"Test Piece - ${TEST_RUN_ID/_/-}","composer":"Test Composer","created_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","updated_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
)

WORK_RESP=$(curl -sS \
  -X POST "${SUPABASE_URL}/rest/v1/works" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Type: application/json" \
  -H "Prefer: return=representation" \
  -d "$WORK_JSON" 2>/dev/null)

TEST_WORK_ID=$(echo "$WORK_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)[0].get('id',''))" 2>/dev/null || echo "")
if [ -n "$TEST_WORK_ID" ]; then
  export TEST_WORK_ID
  pass "test work created ($TEST_WORK_ID)"
else
  fail "test work creation"
fi

# ── Export results ─────────────────────────────────────────────────────────
TEST_USER_IDS=$(IFS=,; echo "${USER_IDS[*]}")
TEST_JWT_TOKENS=$(IFS=,; echo "${JWT_TOKENS[*]}")

export TEST_USER_IDS
export TEST_JWT_TOKENS
export TEST_USER_EMAIL
export TEST_USER_PASSWORD

# ── Write run metadata file (used by teardown) ────────────────────────────
RUN_FILE=".test-run-${TEST_RUN_ID}.json"
cat > "$RUN_FILE" <<RUNEOF
{
  "run_id": "${TEST_RUN_ID}",
  "project_id": "${TEST_PROJECT_ID}",
  "work_id": "${TEST_WORK_ID:-}",
  "user_ids": [$(printf '"%s",' "${USER_IDS[@]}" | sed 's/,$//')],
  "user_emails": ["${TEST_USER_EMAIL}", "${COLLAB_EMAIL}"],
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
RUNEOF
pass "run metadata written to ${RUN_FILE}"

# ── Optional: upload audio fixtures if available ──────────────────────────
echo ""
echo "── Audio fixtures ──"
if [ -d "$TEST_AUDIO_DIR" ] && [ -n "$(ls -A "$TEST_AUDIO_DIR" 2>/dev/null)" ]; then
  for audio_file in "$TEST_AUDIO_DIR"/*; do
    [ -f "$audio_file" ] || continue
    local basename_file
    basename_file=$(basename "$audio_file")
    echo "  Found fixture: ${basename_file}"
  done
  pass "audio fixtures present (${TEST_AUDIO_DIR})"
else
  warn "no audio fixtures found at ${TEST_AUDIO_DIR} — skipping uploads"
  warn "place .wav/.mp3 files here for full seed coverage"
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  Test environment ready — ${PASS} passed, ${FAIL} failed"
echo "══════════════════════════════════════════"
echo ""
echo "  Exported variables:"
echo "    TEST_RUN_ID        = ${TEST_RUN_ID}"
echo "    TEST_PROJECT_ID    = ${TEST_PROJECT_ID}"
echo "    TEST_WORK_ID       = ${TEST_WORK_ID:-n/a}"
echo "    TEST_USER_IDS      = ${TEST_USER_IDS}"
echo "    TEST_USER_EMAIL    = ${TEST_USER_EMAIL}"
echo "    TEST_USER_PASSWORD = ${TEST_USER_PASSWORD}"
echo ""
echo "  To source these into your shell:"
echo "    source <(./scripts/test-env-setup.sh)"
echo ""
echo "  To tear down:"
echo "    TEST_RUN_ID=${TEST_RUN_ID} ./scripts/test-env-teardown.sh"
echo ""

exit $FAIL
