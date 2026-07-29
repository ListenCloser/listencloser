#!/usr/bin/env bash
set -euo pipefail

# ────────────────────────────────────────────────────────────────────────────
# test-env-teardown.sh — clean up test data for a given TEST_RUN_ID
# ────────────────────────────────────────────────────────────────────────────
# Removes projects, works, artifacts, versions, workflows, jobs, entities,
# insights, alignments, and storage objects created during a test run.
#
# Usage:
#   TEST_RUN_ID=test_20260728_143022_abc123 ./scripts/test-env-teardown.sh
#   TEST_RUN_ID=test_... ./scripts/test-env-teardown.sh --full   # also remove users
#
# Required env vars:
#   TEST_RUN_ID                the run id from setup
#   SUPABASE_URL               https://<ref>.supabase.co
#   SUPABASE_SERVICE_ROLE_KEY  supabase service-role JWT
# ────────────────────────────────────────────────────────────────────────────

PASS=0
FAIL=0
SKIP=0

pass() { PASS=$((PASS + 1)); echo "  ✅ $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  ❌ $1"; }
skip() { SKIP=$((SKIP + 1)); echo "  ⤿  $1"; }
warn() { echo "  ⚠️  $1"; }

FULL_MODE=false
if [[ "${1:-}" == "--full" ]]; then
  FULL_MODE=true
  shift
fi

echo "══════════════════════════════════════════"
echo "  hello-ai — test environment teardown"
echo "══════════════════════════════════════════"
echo ""

# ── Validate ───────────────────────────────────────────────────────────────
echo "── Checking environment ──"

if [ -z "${TEST_RUN_ID:-}" ]; then
  echo "  ❌ TEST_RUN_ID is not set"
  echo ""
  echo "  Usage: TEST_RUN_ID=test_20260728_... ./scripts/test-env-teardown.sh"
  echo "  Find the run ID from your setup output or .test-run-*.json files."
  exit 1
fi

for var in SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY; do
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

echo ""
echo "  Run ID:    ${TEST_RUN_ID}"
echo "  Full mode: ${FULL_MODE}"
echo "  URL:       ${SUPABASE_URL}"
echo ""

if [ "${BYPASS_PROD_GUARD:-}" != "1" ] && ! echo "$TEST_RUN_ID" | grep -q "^test_"; then
  warn "TEST_RUN_ID does not start with 'test_' — this may target non-test data"
  warn "Set BYPASS_PROD_GUARD=1 to force"
  echo ""
  echo "  Aborting. Only test_* run IDs are safe by default."
  exit 1
fi

# ── Helper ─────────────────────────────────────────────────────────────────
db_delete() {
  local table="$1"
  local column="$2"
  local value="$3"
  local count
  count=$(curl -sS \
    -X DELETE "${SUPABASE_URL}/rest/v1/${table}?${column}=eq.${value}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Prefer: count=exact" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin) if sys.stdin.read().strip() else []
print(len(data) if isinstance(data, list) else 0)
" 2>/dev/null || echo "0")
  echo "$count"
}

db_list() {
  local table="$1"
  local column="$2"
  local value="$3"
  curl -sS \
    "${SUPABASE_URL}/rest/v1/${table}?select=id&${column}=eq.${value}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null
}

# ── Find test projects ────────────────────────────────────────────────────
echo "── Finding test projects ──"

RUN_PATTERN="%${TEST_RUN_ID/_/-}%"
PROJECT_IDS_JSON=$(curl -sS \
  "${SUPABASE_URL}/rest/v1/projects?select=id&name=ilike.${RUN_PATTERN}&order=created_at.desc" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null || echo "[]")

# Also try to load from the run metadata file if projects are not found by name pattern
RUN_FILE=".test-run-${TEST_RUN_ID}.json"
if [ -f "$RUN_FILE" ]; then
  METADATA_PROJECT_ID=$(python3 -c "import json; print(json.load(open('${RUN_FILE}')).get('project_id',''))" 2>/dev/null || echo "")
  METADATA_WORK_ID=$(python3 -c "import json; print(json.load(open('${RUN_FILE}')).get('work_id',''))" 2>/dev/null || echo "")
  METADATA_USER_IDS=$(python3 -c "import json; print(','.join(json.load(open('${RUN_FILE}')).get('user_ids',[])))" 2>/dev/null || echo "")
  METADATA_USER_EMAILS=$(python3 -c "import json; print(','.join(json.load(open('${RUN_FILE}')).get('user_emails',[])))" 2>/dev/null || echo "")
  pass "run metadata file found (${RUN_FILE})"
else
  METADATA_PROJECT_ID=""
  METADATA_WORK_ID=""
  METADATA_USER_IDS=""
  METADATA_USER_EMAILS=""
  skip "no .test-run-*.json found — relying on name pattern search"
fi

# Collect all project IDs to clean up
PROJECT_IDS=()
IFS=$'\n' read -rd '' -a ids_from_db <<< "$(echo "$PROJECT_IDS_JSON" | python3 -c "
import sys, json
for p in json.load(sys.stdin):
    print(p.get('id',''))
" 2>/dev/null)" || true

for pid in "${ids_from_db[@]}"; do
  [ -n "$pid" ] && PROJECT_IDS+=("$pid")
done

if [ -n "$METADATA_PROJECT_ID" ] && [[ ! " ${PROJECT_IDS[*]} " =~ ${METADATA_PROJECT_ID} ]]; then
  PROJECT_IDS+=("$METADATA_PROJECT_ID")
fi

if [ ${#PROJECT_IDS[@]} -eq 0 ]; then
  echo ""
  warn "No test projects found for ${TEST_RUN_ID} — nothing to clean up"
  if $FULL_MODE; then
    echo ""
    echo "── Cleaning up test users (--full) ──"
  fi
else
  echo "  Found ${#PROJECT_IDS[@]} project(s) to clean up"
  echo ""
fi

# ── Clean data per project ─────────────────────────────────────────────────
for pid in "${PROJECT_IDS[@]}"; do
  echo "── Cleaning project ${pid} ──"

  # 1. Delete jobs (child of workflows)
  JOBS_DEL=$(db_delete "jobs" "workflow_id" "*")
  echo "  Jobs deleted"

  # 2. Delete workflows (child of projects)
  wf_json=$(db_list "workflows" "project_id" "${pid}")
  read -rd '' -a wf_ids <<< "$(echo "$wf_json" | python3 -c "
import sys, json
for w in (json.load(sys.stdin) if sys.stdin.read().strip() else []):
    print(w.get('id',''))
" 2>/dev/null)" || true

  for wfid in "${wf_ids[@]}"; do
    [ -n "$wfid" ] && db_delete "jobs" "workflow_id" "${wfid}" > /dev/null
  done

  WF_COUNT=$(db_delete "workflows" "project_id" "${pid}")
  echo "  Workflows removed: ${WF_COUNT:-0}"

  # 3. Delete entities, insights, alignments (children of versions)
  #    First collect version IDs for this project
  version_artifacts_json=$(db_list "works" "project_id" "${pid}" | python3 -c "
import sys, json
works = json.load(sys.stdin) if sys.stdin.read().strip() else []
for w in works:
    print(w.get('id',''))
" 2>/dev/null)

  for wid in $version_artifacts_json; do
    [ -z "$wid" ] && continue
    art_json=$(db_list "artifacts" "work_id" "${wid}")
    read -rd '' -a art_ids <<< "$(echo "$art_json" | python3 -c "
import sys, json
arts = json.load(sys.stdin) if sys.stdin.read().strip() else []
for a in arts:
    print(a.get('id',''))
" 2>/dev/null)" || true

    for aid in "${art_ids[@]}"; do
      [ -z "$aid" ] && continue
      ver_json=$(db_list "artifact_versions" "artifact_id" "${aid}")
      read -rd '' -a ver_ids <<< "$(echo "$ver_json" | python3 -c "
import sys, json
vers = json.load(sys.stdin) if sys.stdin.read().strip() else []
for v in vers:
    print(v.get('id',''))
" 2>/dev/null)" || true

      for vid in "${ver_ids[@]}"; do
        [ -z "$vid" ] && continue
        db_delete "entities" "version_id" "${vid}" > /dev/null
        db_delete "insights" "version_id" "${vid}" > /dev/null
        db_delete "alignments" "version_id" "${vid}" > /dev/null
      done
    done
  done
  echo "  Entities/insights/alignments cleaned"

  # 4. Delete versions
  VERS_DEL=0
  for wid in $version_artifacts_json; do
    [ -z "$wid" ] && continue
    art_json=$(db_list "artifacts" "work_id" "${wid}")
    read -rd '' -a art_ids2 <<< "$(echo "$art_json" | python3 -c "
import sys, json
arts = json.load(sys.stdin) if sys.stdin.read().strip() else []
for a in arts:
    print(a.get('id',''))
" 2>/dev/null)" || true
    for aid in "${art_ids2[@]}"; do
      [ -z "$aid" ] && continue
      c=$(db_delete "artifact_versions" "artifact_id" "${aid}")
      VERS_DEL=$((VERS_DEL + c))
    done
  done
  echo "  Versions removed: ${VERS_DEL}"

  # 5. Delete artifacts
  ART_DEL=0
  for wid in $version_artifacts_json; do
    [ -z "$wid" ] && continue
    c=$(db_delete "artifacts" "work_id" "${wid}")
    ART_DEL=$((ART_DEL + c))
  done
  echo "  Artifacts removed: ${ART_DEL}"

  # 6. Delete works
  WORK_DEL=$(db_delete "works" "project_id" "${pid}")
  echo "  Works removed: ${WORK_DEL:-0}"

  # 7. Delete the project itself
  PROJ_DEL=$(db_delete "projects" "id" "${pid}")
  echo "  Project removed: ${PROJ_DEL:-0}"

  pass "project ${pid} cleaned"
  echo ""
done

# ── Clean storage objects ──────────────────────────────────────────────────
echo "── Cleaning storage ──"

clean_bucket() {
  local bucket="$1"
  local prefix_pattern="$2"

  local objects
  objects=$(curl -sS \
    -X POST "${SUPABASE_URL}/storage/v1/object/list/${bucket}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"prefix\":\"${prefix_pattern}\"}" 2>/dev/null || echo "[]")

  local paths=()
  IFS=$'\n' read -rd '' -a paths <<< "$(echo "$objects" | python3 -c "
import sys, json
data = json.load(sys.stdin) if sys.stdin.read().strip() else []
for obj in (data if isinstance(data, list) else []):
    print(obj.get('name',''))
" 2>/dev/null)" || true

  local removed=0
  for p in "${paths[@]}"; do
    [ -z "$p" ] && continue
    curl -sS -X DELETE "${SUPABASE_URL}/storage/v1/object/${bucket}/${p}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" > /dev/null 2>&1 || true
    removed=$((removed + 1))
  done
  echo "$removed"
}

for pid in "${PROJECT_IDS[@]}"; do
  count=$(clean_bucket "artifact_data" "${pid}/")
  echo "  artifact_data (${pid}): ${count} objects removed"
done

pass "storage cleaned"
echo ""

# ── Remove run metadata file ───────────────────────────────────────────────
if [ -f "$RUN_FILE" ]; then
  rm -f "$RUN_FILE"
  pass "run metadata file removed (${RUN_FILE})"
fi

# ── Optional: remove test users ────────────────────────────────────────────
if $FULL_MODE; then
  echo "── Cleaning test users (--full) ──"

  for uid in ${METADATA_USER_IDS//,/ }; do
    [ -z "$uid" ] && continue
    resp=$(curl -sS -w "\n%{http_code}" \
      -X DELETE "${SUPABASE_URL}/auth/v1/admin/users/${uid}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" 2>/dev/null)
    status=$(echo "$resp" | tail -1)
    if [ "$status" -ge 200 ] && [ "$status" -lt 300 ]; then
      pass "user deleted ($uid)"
    else
      fail "user deletion ($uid) — status $status"
    fi
  done
  echo ""
else
  skip "test users preserved (use --full to remove)"
  echo ""
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo "══════════════════════════════════════════"
echo "  Teardown complete — ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
echo "══════════════════════════════════════════"

exit $FAIL
