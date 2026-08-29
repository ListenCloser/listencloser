#!/usr/bin/env bash
set -euo pipefail

# Health-gated backend deploy for the Oracle VM.
#
# Preferred path: pull the exact-SHA image built by GitHub Actions, resolve it
# to a registry digest, and recreate API + worker without building on Oracle.
# The legacy VM-build path remains as a safe transition/rollback fallback.

REPO_DIR="${DEPLOY_DIR:-$HOME/hello-ai}"
REPO_URL="https://github.com/gr-rr/hello-ai.git"
COMPOSE="${DOCKER_COMPOSE_FILE:-backend/docker-compose.yml}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
HEALTH_URL="${BACKEND_URL}/health/ready"
QUEUE_HEALTH_URL="${BACKEND_URL}/health/queue"
MAX_WAIT="${HEALTH_TIMEOUT:-120}"
BACKEND_IMAGE_REPOSITORY="${BACKEND_IMAGE_REPOSITORY:-}"
GHCR_USERNAME="${GHCR_USERNAME:-}"
GHCR_TOKEN="${GHCR_TOKEN:-}"

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
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$REPO_URL"
  else
    git remote set-url origin "$REPO_URL"
  fi

  local current_branch
  current_branch=$(git branch --show-current 2>/dev/null || echo "")
  if [ "$current_branch" = "master" ]; then
    echo "[deploy] renaming master -> main"
    git branch -m master main
  fi

  if [ "$(git branch --show-current 2>/dev/null)" != "main" ]; then
    echo "[deploy] switching to main"
    git checkout main 2>/dev/null || git checkout -b main origin/main
  fi

  if ! git rev-parse --abbrev-ref @{upstream} >/dev/null 2>&1; then
    echo "[deploy] setting upstream to origin/main"
    git branch --set-upstream-to=origin/main main
  fi

  if [ "${DEPLOY_PREVIOUS_SHA+x}" = "x" ]; then
    PREV_HEAD="${DEPLOY_PREVIOUS_SHA}"
  else
    PREV_HEAD="$(git rev-parse HEAD)"
  fi

  git fetch -q origin
  local target_revision="${DEPLOY_SHA:-origin/main}"
  git cat-file -e "${target_revision}^{commit}"
  git reset --hard "$target_revision"
  echo "[deploy] selected exact revision $(git rev-parse HEAD)"
}

detect_image_arch() {
  case "$(uname -m)" in
    x86_64|amd64)
      printf '%s\n' "amd64"
      ;;
    aarch64|arm64)
      printf '%s\n' "arm64"
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_prebuilt_image() {
  local revision="$1"
  local arch candidate resolved logged_in=0

  if [ -z "$BACKEND_IMAGE_REPOSITORY" ]; then
    return 1
  fi

  if ! arch="$(detect_image_arch)"; then
    echo "[deploy] unsupported host architecture $(uname -m); using VM build fallback" >&2
    return 1
  fi

  candidate="${BACKEND_IMAGE_REPOSITORY}:${revision}-${arch}"

  if [ -n "$GHCR_USERNAME" ] && [ -n "$GHCR_TOKEN" ]; then
    if printf '%s' "$GHCR_TOKEN" | docker login ghcr.io --username "$GHCR_USERNAME" --password-stdin >/dev/null; then
      logged_in=1
    else
      echo "[deploy] GHCR login failed; trying anonymous pull" >&2
    fi
  fi

  if ! docker pull "$candidate"; then
    if [ "$logged_in" -eq 1 ]; then
      docker logout ghcr.io >/dev/null 2>&1 || true
    fi
    echo "[deploy] prebuilt image unavailable: $candidate" >&2
    return 1
  fi

  resolved="$(docker image inspect --format '{{index .RepoDigests 0}}' "$candidate" 2>/dev/null || true)"
  if [ -z "$resolved" ] || [ "$resolved" = "<no value>" ]; then
    resolved="$candidate"
  fi

  if [ "$logged_in" -eq 1 ]; then
    docker logout ghcr.io >/dev/null 2>&1 || true
  fi

  export BACKEND_IMAGE="$resolved"
  echo "[deploy] resolved ${revision} (${arch}) to ${BACKEND_IMAGE}"
  return 0
}

write_runtime_env() {
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
OTEL_EXPORTER_OTLP_ENDPOINT=${OTEL_EXPORTER_OTLP_ENDPOINT:-}
OTEL_EXPORTER_OTLP_HEADERS=${OTEL_EXPORTER_OTLP_HEADERS:-}
HARMONY_ENGINE=lv_chordia
RELEASE=${TARGET_HEAD}
BACKEND_IMAGE=${BACKEND_IMAGE:-hello-ai-backend:local}
NUMBA_CACHE_DIR=${TARGET_NUMBA_CACHE_DIR}
ENVEOF
  fi
}

set_runtime_env_value() {
  local key="$1"
  local value="$2"
  local env_file="$REPO_DIR/backend/.env"
  [ -f "$env_file" ] || return 0
  if grep -q "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

use_numba_cache_for_release() {
  local revision="$1"
  export NUMBA_CACHE_DIR="/app/runtime/numba-cache/${revision}"
  set_runtime_env_value NUMBA_CACHE_DIR "$NUMBA_CACHE_DIR"
}

preseed_librosa_numba_cache() {
  echo "[deploy] preseeding target worker Numba cache while current release stays online"

  if ! docker compose -f "$COMPOSE" run --rm --no-deps --user root --entrypoint sh worker \
    -c 'mkdir -p "$NUMBA_CACHE_DIR" && chown 1001:1001 /app/runtime && chown -R 1001:1001 "$NUMBA_CACHE_DIR"'; then
    echo "[deploy] warning: could not initialize Numba cache directory; replacement worker will warm it itself" >&2
    return 0
  fi

  local started=$SECONDS
  if docker compose -f "$COMPOSE" run --rm --no-deps --entrypoint python worker \
    -c 'from domain.worker_warmup import prewarm_librosa_beat_tracking; prewarm_librosa_beat_tracking()'; then
    echo "[deploy] target Numba cache preseeded in $((SECONDS - started))s"
  else
    echo "[deploy] warning: Numba cache preseed failed; replacement worker will retry before readiness" >&2
  fi
}

echo "[deploy] starting deploy at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
ensure_repo
TARGET_HEAD="$(git rev-parse HEAD)"
TARGET_NUMBA_CACHE_DIR="/app/runtime/numba-cache/${TARGET_HEAD}"
export BACKEND_IMAGE="${BACKEND_IMAGE:-hello-ai-backend:local}"
USE_PREBUILT_IMAGE=0
if resolve_prebuilt_image "$TARGET_HEAD"; then
  USE_PREBUILT_IMAGE=1
else
  echo "[deploy] using compatibility VM-build path"
fi
write_runtime_env
use_numba_cache_for_release "$TARGET_HEAD"

echo "[deploy] running pytest gate"
cd "$REPO_DIR/backend"
if python3 -m pytest --version >/dev/null 2>&1; then
  python3 -m pytest tests/ -x -q 2>&1 || { echo "[deploy] pytest failed — aborting"; exit 1; }
else
  echo "[deploy] pytest not installed — skipping (tests ran in CI)"
fi
cd "$REPO_DIR"

if [ "$USE_PREBUILT_IMAGE" -eq 1 ]; then
  echo "[deploy] prebuilt image is ready; Oracle build skipped"
else
  echo "[deploy] building replacement images while the current release stays online"
  docker compose -f "$COMPOSE" build backend worker
fi

preseed_librosa_numba_cache

echo "[deploy] switching API and worker to $(git rev-parse --short HEAD)"
docker compose -f "$COMPOSE" run --rm --no-deps --user root --entrypoint sh worker \
  -c 'rm -f /app/runtime/worker-heartbeat.json && chown 1001:1001 /app/runtime'
if [ "$USE_PREBUILT_IMAGE" -eq 1 ]; then
  docker compose -f "$COMPOSE" up -d --force-recreate --remove-orphans --no-build backend worker
else
  docker compose -f "$COMPOSE" up -d --force-recreate --remove-orphans backend worker
fi

rollback() {
  local reason="$1"
  local rollback_prebuilt=0
  echo "[deploy] ${reason}; rolling back to ${PREV_HEAD:-no previous revision}" >&2
  docker compose -f "$COMPOSE" logs --tail=60 backend worker 2>&1 >&2 || true
  if [ -z "${PREV_HEAD:-}" ]; then
    echo "[deploy] first deployment has no previous revision" >&2
    return 1
  fi

  use_numba_cache_for_release "$PREV_HEAD"

  # Prefer the prior CI-built artifact while the current image-aware Compose
  # file is still checked out. Older releases without a registry artifact fall
  # back to the original source-build rollback below.
  if resolve_prebuilt_image "$PREV_HEAD"; then
    rollback_prebuilt=1
    set_runtime_env_value RELEASE "$PREV_HEAD"
    set_runtime_env_value BACKEND_IMAGE "$BACKEND_IMAGE"
    docker compose -f "$COMPOSE" up -d --force-recreate --remove-orphans --no-build backend worker
  else
    git reset --hard "$PREV_HEAD"
    if [ -f "$REPO_DIR/backend/.env" ]; then
      sed -i "s/^RELEASE=.*/RELEASE=${PREV_HEAD}/" "$REPO_DIR/backend/.env"
    fi
    docker compose -f "$COMPOSE" build backend worker
    docker compose -f "$COMPOSE" up -d --force-recreate --remove-orphans backend worker
  fi

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

  if [ "$rollback_prebuilt" -eq 1 ]; then
    git reset --hard "$PREV_HEAD"
  fi
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
