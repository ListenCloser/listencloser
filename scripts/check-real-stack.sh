#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SUPABASE_VERSION_REQUIRED="2.113.0"
RUN_ID="${REALSTACK_RUN_ID:-$$-$RANDOM}"
BACKEND_IMAGE="listencloser-real-stack-backend-check"
API_CONTAINER="listencloser-realstack-api-$RUN_ID"
WORKER_CONTAINER="listencloser-realstack-worker-$RUN_ID"
TMP_DIR="$(mktemp -d)"
SUPABASE_WORKDIR=""
STARTED_SUPABASE=false
FRONTEND_PID=""
OBSERVER_PID=""

API_LOG="$TMP_DIR/backend.log"
WORKER_LOG="$TMP_DIR/worker.log"
FRONTEND_LOG="$TMP_DIR/frontend.log"
OBSERVER_LOG="$TMP_DIR/musescore-observer.log"
ROUTING_JSON="$TMP_DIR/harmony-engine-routing.json"

SUPABASE_URL=""
SUPABASE_ANON_KEY=""
SUPABASE_SERVICE_ROLE_KEY=""
SUPABASE_JWT_SECRET=""
CONTAINER_SUPABASE_URL=""
SUPABASE_NETWORK=""
HARMONY_ENGINE=""

die() {
  echo "real-stack check: $*" >&2
  exit 2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required ($2)"
}

semver_from() {
  grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1
}

supabase_in_check() {
  (cd "$SUPABASE_WORKDIR" && supabase "$@")
}

capture_container_log() {
  local container="$1"
  local destination="$2"
  if docker inspect "$container" >/dev/null 2>&1; then
    docker logs "$container" > "$destination" 2>&1 || true
  fi
}

collect_failure_diagnostics() {
  local diagnostics="test-results/real-stack-diagnostics"
  mkdir -p "$diagnostics"
  capture_container_log "$API_CONTAINER" "$API_LOG"
  capture_container_log "$WORKER_CONTAINER" "$WORKER_LOG"
  cp "$API_LOG" "$diagnostics/backend.log" 2>/dev/null || true
  cp "$WORKER_LOG" "$diagnostics/worker.log" 2>/dev/null || true
  cp "$FRONTEND_LOG" "$diagnostics/frontend.log" 2>/dev/null || true
  cp "$OBSERVER_LOG" "$diagnostics/musescore-observer.log" 2>/dev/null || true
  echo "===== backend =====" >&2; tail -150 "$API_LOG" >&2 2>/dev/null || true
  echo "===== worker =====" >&2; tail -150 "$WORKER_LOG" >&2 2>/dev/null || true
  echo "===== frontend =====" >&2; tail -150 "$FRONTEND_LOG" >&2 2>/dev/null || true
  echo "===== MuseScore observer =====" >&2; cat "$OBSERVER_LOG" >&2 2>/dev/null || true
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  set +e
  if [ "$status" -ne 0 ]; then
    collect_failure_diagnostics
  fi
  if [ -n "$OBSERVER_PID" ] && kill -0 "$OBSERVER_PID" >/dev/null 2>&1; then
    kill "$OBSERVER_PID" >/dev/null 2>&1 || true
    wait "$OBSERVER_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  docker stop "$API_CONTAINER" >/dev/null 2>&1 || true
  docker stop "$WORKER_CONTAINER" >/dev/null 2>&1 || true
  if "$STARTED_SUPABASE" && [ -n "$SUPABASE_WORKDIR" ]; then
    supabase_in_check stop --no-backup >/dev/null 2>&1 || true
  fi
  [ -z "$SUPABASE_WORKDIR" ] || rm -rf "$SUPABASE_WORKDIR"
  rm -rf "$TMP_DIR"
  exit "$status"
}
trap cleanup EXIT INT TERM

require_command git "tracked Supabase isolation"
require_command docker "production-image API/worker"
require_command supabase "fresh local Supabase"
require_command node "frontend runtime"
require_command npm "locked frontend dependencies"
require_command npx "Playwright browser"
require_command python3 "real-stack assertions"
require_command curl "health/Auth assertions"
docker info >/dev/null 2>&1 || die "Docker daemon is not available"

supabase_version="$(supabase --version 2>/dev/null | semver_from || true)"
[ "$supabase_version" = "$SUPABASE_VERSION_REQUIRED" ] \
  || die "Supabase CLI $SUPABASE_VERSION_REQUIRED is required; found ${supabase_version:-unknown}"

if supabase status >/dev/null 2>&1; then
  die "a local Supabase stack is already running; stop it normally before this isolated check"
fi
[ -f tests/fixtures/real-piano.m4a ] || die "tests/fixtures/real-piano.m4a is required"
[ -f playwright.realstack.config.ts ] || die "playwright.realstack.config.ts is required"

rm -rf test-results/real-stack-diagnostics
rm -f performance-results/understand-stage-timing.jsonl

# A normal `supabase stop` preserves local data. Give this check a distinct
# project identity so its `--no-backup` cleanup can never delete stopped normal
# project volumes. Fixed local ports still require the normal stack to be down.
SUPABASE_WORKDIR="$(mktemp -d)"
while IFS= read -r -d '' source_path; do
  destination="$SUPABASE_WORKDIR/$source_path"
  mkdir -p "$(dirname "$destination")"
  cp "$source_path" "$destination"
done < <(git ls-files -z supabase)

isolated_project_id="listencloser-realstack-$RUN_ID"
awk -v project_id="$isolated_project_id" '
  /^project_id = / { print "project_id = \"" project_id "\""; next }
  { print }
' "$SUPABASE_WORKDIR/supabase/config.toml" > "$SUPABASE_WORKDIR/supabase/config.toml.tmp"
mv "$SUPABASE_WORKDIR/supabase/config.toml.tmp" "$SUPABASE_WORKDIR/supabase/config.toml"

echo "── Fresh isolated Supabase ($isolated_project_id) ──"
supabase_in_check start -x realtime,imgproxy,mailpit,postgres-meta,studio,edge-runtime,logflare,vector,supavisor
STARTED_SUPABASE=true

eval "$(supabase_in_check status -o env)"
SUPABASE_URL="${SUPABASE_URL:-${API_URL:-http://127.0.0.1:54321}}"
SUPABASE_ANON_KEY="${SUPABASE_ANON_KEY:-${ANON_KEY:-}}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${SERVICE_ROLE_KEY:-}}"
SUPABASE_JWT_SECRET="${SUPABASE_JWT_SECRET:-${JWT_SECRET:-}}"
[ -n "$SUPABASE_ANON_KEY" ] || die "Supabase status did not expose an anon key"
[ -n "$SUPABASE_SERVICE_ROLE_KEY" ] || die "Supabase status did not expose a service-role key"
[ -n "$SUPABASE_JWT_SECRET" ] || die "Supabase status did not expose a JWT secret"

# Put the production-image containers on the disposable Supabase Docker network
# rather than using Linux-only `--network host`. This is the same container-to-
# Supabase topology on GitHub runners and Docker Desktop.
KONG_CONTAINER="$(docker ps --filter "name=supabase_kong_${isolated_project_id}" --format '{{.Names}}' | head -n 1)"
[ -n "$KONG_CONTAINER" ] || die "could not identify the isolated Supabase Kong container"
SUPABASE_NETWORK="$(
  docker inspect "$KONG_CONTAINER" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' \
    | head -n 1
)"
[ -n "$SUPABASE_NETWORK" ] || die "could not identify the isolated Supabase Docker network"
CONTAINER_SUPABASE_URL="http://${KONG_CONTAINER}:8000"

echo "── Unsupported email Auth stays disabled ──"
assert_email_disabled() {
  local path="$1" payload="$2" body status code
  body="$(mktemp)"
  status="$(curl --silent --show-error --output "$body" --write-out '%{http_code}' \
    --request POST --header "apikey: ${SUPABASE_ANON_KEY}" \
    --header 'Content-Type: application/json' --data "$payload" "${SUPABASE_URL}${path}")"
  code="$(python3 - "$body" <<'PY'
import json, sys
try:
    payload = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    payload = {}
print(payload.get("error_code") or payload.get("code") or "")
PY
)"
  if [ "$status" -lt 400 ] || [ "$code" != "email_provider_disabled" ]; then
    echo "Expected ${path} to reject email auth with email_provider_disabled; status=${status} code=${code}" >&2
    cat "$body" >&2
    rm -f "$body"
    return 1
  fi
  rm -f "$body"
}
assert_email_disabled '/auth/v1/signup' '{"email":"disabled-signup@real-stack.test","password":"disabled-password-1234"}'
assert_email_disabled '/auth/v1/otp' '{"email":"disabled-otp@real-stack.test","create_user":true}'

echo "── Production harmony routing ──"
HARMONY_ENGINE="$(python3 - <<'PY'
import re
from pathlib import Path
compose = Path("backend/docker-compose.yml").read_text()
values = re.findall(r"^\s+HARMONY_ENGINE:\s*([A-Za-z0-9_.-]+)\s*$", compose, flags=re.MULTILINE)
if len(values) != 2 or len(set(values)) != 1:
    raise SystemExit(f"production Compose must declare one shared API/worker HARMONY_ENGINE, got {values}")
print(values[0])
PY
)"

echo "── Production backend image ──"
docker build --tag "$BACKEND_IMAGE" backend

echo "── Production-image API + worker ──"
docker run -d --rm --name "$API_CONTAINER" --network "$SUPABASE_NETWORK" \
  --publish 127.0.0.1:8000:8000 \
  -e "SUPABASE_URL=$CONTAINER_SUPABASE_URL" -e "SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" \
  -e "SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY" -e "HARMONY_ENGINE=$HARMONY_ENGINE" \
  "$BACKEND_IMAGE" >/dev/null

docker run -d --rm --name "$WORKER_CONTAINER" --network "$SUPABASE_NETWORK" \
  -e "SUPABASE_URL=$CONTAINER_SUPABASE_URL" -e "SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" \
  -e "SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY" -e "HARMONY_ENGINE=$HARMONY_ENGINE" \
  --entrypoint python "$BACKEND_IMAGE" worker.py >/dev/null

echo "── Locked frontend + browser runtime ──"
npm ci
if [ "${CI:-}" = "true" ]; then
  npx playwright install chromium --with-deps
else
  npx playwright install chromium
fi
NEXT_PUBLIC_SUPABASE_URL="$SUPABASE_URL" NEXT_PUBLIC_SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
NEXT_PUBLIC_MOCK_ENABLED=false npm run build

echo "── Frontend runtime ──"
MUSIC_BACKEND_URL=http://127.0.0.1:8000 npm run start > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo "── Wait for fresh stack ──"
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/health/live >/dev/null \
    && curl -sf http://127.0.0.1:8000/health/queue | grep -q '"status":"ready"' \
    && curl -sf http://localhost:3000 >/dev/null; then
    echo "stack and worker ready"
    break
  fi
  sleep 2
done
if ! curl -sf http://127.0.0.1:8000/health/live >/dev/null \
  || ! curl -sf http://127.0.0.1:8000/health/queue | grep -q '"status":"ready"' \
  || ! curl -sf http://localhost:3000 >/dev/null; then
  die "stack did not become ready"
fi

echo "── Verify production harmony engine routing ──"
routing_json="$(docker exec "$WORKER_CONTAINER" python -c \
  'import json, os; from engines.registry import get_harmony_engine; engine = get_harmony_engine(); print(json.dumps({"configured": os.environ.get("HARMONY_ENGINE"), "selected_engine": engine.provenance.engine, "selected_class": type(engine).__name__}, sort_keys=True))' | tail -1)"
python3 - "$routing_json" "$HARMONY_ENGINE" "$ROUTING_JSON" <<'PY'
import json, sys
from pathlib import Path
record = json.loads(sys.argv[1])
expected = sys.argv[2]
if record.get("configured") != expected:
    raise SystemExit(f"worker HARMONY_ENGINE mismatch: expected {expected!r}, got {record.get('configured')!r}")
if not record.get("selected_engine") or not record.get("selected_class"):
    raise SystemExit(f"worker harmony registry returned incomplete provenance: {record}")
record["source"] = "backend/docker-compose.yml"
path = Path(sys.argv[3]); path.write_text(json.dumps(record, sort_keys=True) + "\n")
print(path.read_text(), end="")
PY

echo "── Real-audio browser golden path ──"
export REAL_AUDIO_FILE="$ROOT/tests/fixtures/real-piano.m4a"
export SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY SUPABASE_JWT_SECRET
export BACKEND_URL="http://127.0.0.1:8000"
python3 - <<'PY' > "$OBSERVER_LOG" 2>&1 &
import json, os, time, urllib.error, urllib.request
base = os.environ["SUPABASE_URL"].rstrip("/")
service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
def get(path: str):
    request = urllib.request.Request(base + path, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)
deadline = time.monotonic() + 540
last_error = None
while time.monotonic() < deadline:
    try:
        kinds = {row.get("kind") for row in get("/rest/v1/artifacts?select=kind")}
        reports = []
        for row in get("/rest/v1/artifact_versions?select=metadata"):
            metadata = row.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("notation"), dict):
                reports.append(metadata["notation"])
        if {"musicxml_score", "rendered_score"}.issubset(kinds) and any(
            report.get("engine") == "musescore" for report in reports
        ):
            print("observed MuseScore MusicXML + rendered score before deletion")
            raise SystemExit(0)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        last_error = exc
    time.sleep(1)
raise SystemExit(f"MuseScore score artifacts/provenance were never observed: {last_error}")
PY
OBSERVER_PID=$!
npx playwright test --config=playwright.realstack.config.ts
wait "$OBSERVER_PID"
OBSERVER_PID=""
cat "$OBSERVER_LOG"

echo "── Understand performance evidence ──"
capture_container_log "$WORKER_CONTAINER" "$WORKER_LOG"
mkdir -p performance-results
python3 - "$WORKER_LOG" "$ROUTING_JSON" <<'PY'
import json, sys
from pathlib import Path
worker_log, routing_path = Path(sys.argv[1]), Path(sys.argv[2])
output = []
for line in worker_log.read_text().splitlines():
    try: record = json.loads(line)
    except json.JSONDecodeError: continue
    msg = record.get("msg")
    if msg in {"basic_pitch_prewarm_complete", "librosa_beat_prewarm_complete"}:
        output.append({"msg": msg, "duration_seconds": record.get("duration_s")})
    elif msg == "worker_queue_wait":
        output.append({"msg": msg, "capability": record.get("capability"), "duration_seconds": record.get("duration_seconds")})
    elif msg == "understand_stage_timing":
        output.append({"msg": msg, "stage": record.get("stage"), "outcome": record.get("outcome"), "duration_seconds": record.get("duration_seconds")})
    elif msg == "understand_operation_timing":
        output.append({"msg": msg, "operation": record.get("operation"), "outcome": record.get("outcome"), "duration_seconds": record.get("duration_seconds")})
if not output: raise SystemExit("no understand performance records found")
if not routing_path.exists(): raise SystemExit("missing verified harmony engine routing evidence")
output.insert(0, {"msg": "engine_routing", **json.loads(routing_path.read_text())})
path = Path("performance-results/understand-stage-timing.jsonl")
path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in output))
print(path.read_text(), end="")
PY

echo "real-stack check passed"
