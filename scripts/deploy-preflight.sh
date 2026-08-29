#!/usr/bin/env bash
set -euo pipefail

# Keep the small Oracle VM deploy host from accumulating enough Docker state to
# prevent extraction of the next exact-SHA image. Only disposable build cache
# and images unused by any container are removed. Running/stopped containers,
# volumes, and their referenced images are deliberately preserved.

echo "[deploy] Docker disk usage before preflight cleanup"
docker system df || true

# Build cache is safe to regenerate and is especially expensive when the
# compatibility VM-build path has run in the past.
docker builder prune --all --force || true

# `image prune -a` never removes an image referenced by a container, so the
# currently running release remains available. A prior exact-SHA rollback image
# can be pulled again from GHCR if it is no longer referenced locally.
docker image prune --all --force || true

echo "[deploy] Docker disk usage after preflight cleanup"
docker system df || true
