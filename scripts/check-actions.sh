#!/usr/bin/env bash
set -euo pipefail

ACTIONLINT_VERSION="1.7.12"
ACTIONLINT_DIGEST="sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667"
ZIZMOR_VERSION="1.29.0"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run actionlint ${ACTIONLINT_VERSION}" >&2
  exit 1
fi
if ! command -v uvx >/dev/null 2>&1; then
  echo "uvx is required to run zizmor ${ZIZMOR_VERSION}" >&2
  exit 1
fi

# actionlint's official Docker image includes shellcheck and pyflakes. Pin both
# the human-readable release tag and its observed image digest for reproducible
# local/CI workflow/schema/expression/shell checks.
docker run --rm \
  -v "$PWD:/repo" \
  --workdir /repo \
  "docker.io/rhysd/actionlint:${ACTIONLINT_VERSION}@${ACTIONLINT_DIGEST}" \
  -color

# Keep the permanent security ratchet intentionally narrow: regular-persona,
# medium-or-higher, medium-confidence-or-higher workflow findings only. Offline
# mode makes the result independent of GitHub API availability or token scope.
ZIZMOR_OFFLINE=true uvx "zizmor@${ZIZMOR_VERSION}" \
  --persona=regular \
  --min-severity=medium \
  --min-confidence=medium \
  --collect=workflows \
  .
