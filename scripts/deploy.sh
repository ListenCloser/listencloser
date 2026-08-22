#!/usr/bin/env bash
set -euo pipefail

# Health-gated backend deploy for the Oracle VM.
#
# Build-first, health-gated deployment for both the API and durable worker.
# The currently running release stays online while replacement images build.

REPO_DIR="${DEPLOY_DIR:-$HOME/hello-ai}"
REPO_URL="https://github.com/gr-rr/hello-ai.git"
COMPOSE="${DOCKER_COMPOSE_FILE:-backend/docker-compose.yml}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
HEALTH_URL="${BACKEND_URL}/health/ready"
QUEUE_HEALTH_URL="${BACKEND_URL}/health/queue"
MAX_WAIT="${HEALTH_TIMEOUT:-120}"

# --- ensure repo exists and is usable ---
ensure_repo() {
  if [ ! -d "$REPO_DIR/.git" ]; then
    echo "[deploy] no .git found — cloning fresh"
    rm -rf "$REPO_DIR" 2>/dev/null || true
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
    PREV_HEAD=""
    return
  fi

  cd "$REPO_DIR"

  # ensure remote exists and points to the right URL
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$REPO_URL"
  else
    git remote set-url origin "$REPO_URL"
  fi

  # rename master -> main if needed
  local current_branch
  current_branch=$(git branch --show-current 2>/dev/null || echo "")
  if [ "$current_branch" = "master" ]; then
    echo "[deploy] renaming master -> main"
    git branch -m master main
  fi

  # ensure we're on main
  if [ "$(git branch --show-current 2>/dev/null)" != "main" ]; then
    echo "[deploy] switching to main"
    git checkout main 2>/dev/null || git checkout -b main origin/main
  fi

  # ensure upstream tracking exists
  if ! git rev-parse --abbrev-ref @{upstream} >/dev/null 2>&1; then
    echo "[deploy] setting upstream to origin/main"
    git branch --set-upstream-to=origin/main main
  fi

  if [ "${DEPLOY_PREVIOUS_SHA+x}" = "x" ]; then
    # An explicitly empty value means this is a first deployment, so there is
    # no valid release to roll back to.
    PREV_HEAD="${DEPLOY_PREVIOUS_SHA}"
  else
    PREV_HEAD="$(git rev-parse HEAD)"
  fi

  # Fetch and select the exact release requested by CI. Falling back to
  # origin/main keeps manual recovery usable without weakening CI deploys.
  git fetch -q origin
  local target_revision="${DEPLOY_SHA:-origin/main}"
  git cat-file -e "${target_revision}^{commit}"
  git reset --hard "$target_revision"
  echo "[deploy] selected exact revision $(git rev-parse HEAD)"
}

# --- main ---
echo "[deploy] starting deploy at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
ensure_repo
TARGET_HEAD="$(git rev-parse HEAD)"

# --- write .env from environment (deploy workflow passes these) ---
if [ -n "${SUPABASE_URL:-}" ] || [ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "[deploy] writing .env from environment"
  cat > "$REPO_DIR/backend/.env" <<ENVEOF
SUPABASE_URL=${SUPABASE_URL:-}
SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}
SENTRY_DSN_BACKEND=${SENTRY_DSN_BACKEND:-}
SENTRY_ENV=${SENTRY_ENV:-production}
LLM_BASE_URL=${LLM_BASE_URL:-}
LLM_API_KEY=${LLM_API_KEY:-}
LLM_MODEL=${LLM_MODEL:-}
HARMONY_ENGINE=lv_chordia
RELEASE=${TARGET_HEAD}
ENVEOF
fi

echo "[deploy] running pytest gate"
cd "$REPO_DIR/backend"
if python3 -m pytest --version >/dev/null 2>&1; then
  python3 -m pytest tests/ -x -q 2>&1 || { echo "[deploy] pytest failed — aborting"; exit 1; }
else
  echo "[deploy] pytest not installed — skipping (tests ran in CI)"
fi
cd "$REPO_DIR"

echo "[deploy] building replacement images while the current release stays online"
docker compose -f "$COMPOSE" build backend worker

echo "[deploy] switching API and worker to $(git rev-parse --short HEAD)"
docker compose -f "$COMPOSE" run --rm --no-deps --user root --entrypoint sh worker \
  -c 'rm -f /app/runtime/worker-heartbeat.json && chown 1001:1001 /app/runtime'
docker compose -f "$COMPOSE" up -d --force-recreate --remove-orphans backend worker

rollback() {
  local reason="$1"
  echo "[deploy] ${reason}; rolling back to ${PREV_HEAD:-no previous revision}" >&2
  docker compose -f "$COMPOSE" logs --tail=60 backend worker 2>&1 >&2 || true
  if [ -z "${PREV_HEAD:-}" ]; then
    echo "[deploy] first deployment has no previous revision" >&2
    return 1
  fi
  git reset --hard "$PREV_HEAD"
  if [ -f "$REPO_DIR/backend/.env" ]; then
    sed -i "s/^RELEASE=.*/RELEASE=${PREV_HEAD}/" "$REPO_DIR/backend/.env"
  fi
  docker compose -f "$COMPOSE" build backend worker
  docker compose -f "$COMPOSE" up -d --force-recreate --remove-orphans backend worker
  local rollback_elapsed=0
  until rollback_body="$(curl -fsS "$HEALTH_URL" 2>/dev/null)" \
    && grep -q '"status":"ready"' <<<"$rollback_body" \
    && { ! grep -q '"release":' <<<"$rollback_body" \
      || grep -q "\"release\":\"${PREV_HEAD}\"" <<<"$rollback_body"; }; do
    rollback_elapsed=$((rollback_elapsed + 2))
    if [ "$rollback_elapsed" -ge "$MAX_WAIT" ]; then
      echo "[deploy] rollback failed its health/SHA gate" >&2
      return 2
    fi
    sleep 2
  done
  curl -fsS "$QUEUE_HEALTH_URL" | grep -q '"status":"ready"' \
    || { echo "[deploy] rollback API recovered but queue is not ready" >&2; return 2; }
  echo "[deploy] rollback restored and verified $(git rev-parse --short HEAD)" >&2
  return 1
}

echo "[deploy] waiting for ${HEALTH_URL} (max ${MAX_WAIT}s)"
elapsed=0
until ready_body="$(curl -fsS "$HEALTH_URL" 2>/dev/null)" \
  && grep -q '"status":"ready"' <<<"$ready_body" \
  && grep -q "\"release\":\"${TARGET_HEAD}\"" <<<"$ready_body"; do
  elapsed=$((elapsed + 2))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    rollback "API health check failed after ${MAX_WAIT}s"
  fi
  sleep 2
done

echo "[deploy] waiting for the replacement worker container"
elapsed=0
until [ "$(docker inspect --format '{{.State.Health.Status}}' music-ai-worker 2>/dev/null)" = "healthy" ]; do
  elapsed=$((elapsed + 2))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    rollback "worker container health check failed after ${MAX_WAIT}s"
  fi
  sleep 2
done

echo "[deploy] waiting for a live worker at ${QUEUE_HEALTH_URL}"
elapsed=0
until curl -fsS "$QUEUE_HEALTH_URL" 2>/dev/null | grep -q '"status":"ready"'; do
  elapsed=$((elapsed + 2))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    rollback "worker health check failed after ${MAX_WAIT}s"
  fi
  sleep 2
done

echo "[deploy] healthy: ${PREV_HEAD:-first deploy} -> ${TARGET_HEAD}"
