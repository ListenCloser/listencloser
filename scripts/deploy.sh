#!/usr/bin/env bash
set -euo pipefail

# Health-gated backend deploy for the Oracle VM.
#
# Self-healing: handles any repo state (missing, partial, wrong branch, stale).
# Flow: ensure repo -> pull -> rebuild backend -> wait for /health/ready -> rollback on failure.

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

  # fetch and fast-forward
  git fetch -q origin
  local behind
  behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
  if [ "$behind" -gt 0 ]; then
    echo "[deploy] behind by $behind commit(s) — hard reset to origin/main"
    git reset --hard origin/main
  else
    echo "[deploy] up to date"
  fi
}

# --- main ---
echo "[deploy] starting deploy at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
ensure_repo

PREV_HEAD="$(git rev-parse --short HEAD)"

# --- write .env from environment (deploy workflow passes these) ---
if [ -n "${SUPABASE_URL:-}" ] || [ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]; then
  echo "[deploy] writing .env from environment"
  cat > "$REPO_DIR/backend/.env" <<ENVEOF
SUPABASE_URL=${SUPABASE_URL:-}
SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-}
SENTRY_DSN_BACKEND=${SENTRY_DSN_BACKEND:-}
SENTRY_ENV=${SENTRY_ENV:-production}
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

echo "[deploy] stopping old containers"
docker compose -f "$COMPOSE" down --remove-orphans 2>/dev/null || true
docker rm -f music-ai-backend 2>/dev/null || true
docker rm -f music-ai-worker 2>/dev/null || true

echo "[deploy] rebuilding backend"
docker compose -f "$COMPOSE" up -d --build backend worker

echo "[deploy] waiting for ${HEALTH_URL} (max ${MAX_WAIT}s)"
elapsed=0
until curl -fsS "$HEALTH_URL" >/dev/null 2>&1; do
  elapsed=$((elapsed + 2))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "[deploy] health check failed after ${MAX_WAIT}s; rolling back to ${PREV_HEAD}" >&2
    echo "[deploy] container logs:" >&2
    docker compose -f "$COMPOSE" logs --tail=30 backend 2>&1 >&2 || true
    git checkout -q "$PREV_HEAD"
    docker compose -f "$COMPOSE" up -d --build backend worker
    exit 1
  fi
  sleep 2
done

echo "[deploy] waiting for a live worker at ${QUEUE_HEALTH_URL}"
elapsed=0
until curl -fsS "$QUEUE_HEALTH_URL" 2>/dev/null | grep -q '"status":"ready"'; do
  elapsed=$((elapsed + 2))
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "[deploy] worker health check failed after ${MAX_WAIT}s; rolling back to ${PREV_HEAD}" >&2
    echo "[deploy] container logs:" >&2
    docker compose -f "$COMPOSE" logs --tail=30 backend worker 2>&1 >&2 || true
    git checkout -q "$PREV_HEAD"
    docker compose -f "$COMPOSE" up -d --build backend worker
    exit 1
  fi
  sleep 2
done

echo "[deploy] healthy: ${PREV_HEAD} -> $(git rev-parse --short HEAD)"
