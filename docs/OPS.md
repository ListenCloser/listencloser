# Operations Runbook

This is the operational contract for the current production stack. If code and this file disagree, treat code/workflow definitions as authoritative and repair this document in the same PR.

## Production topology

```text
Browser
  ├── auth + signed object upload ──────────────► Supabase Auth / private Storage
  └── JSON/session API ─► Vercel Next.js ─────► Oracle FastAPI
                                                   │
Oracle worker ◄──────── durable Postgres jobs ─────┘
      │
      ├── music engines
      ├── Sentry / OpenTelemetry
      └── Supabase Postgres + Storage

GitHub Actions ─► GHCR exact-SHA images ─► Oracle API + worker
```

Production frontend: `https://hello-ai-wheat.vercel.app`.

Large imported audio does **not** normally transit through Vercel or Oracle. FastAPI authorizes a signed upload intent, the browser uploads directly to private Supabase Storage, and a small finalize API records durable metadata after verification. The legacy multipart proxy is a compatibility/fallback path only.

## Frontend deployment

Vercel Git integration deploys `main` only; automatic branch previews are disabled to preserve Hobby-plan capacity. PR validation belongs to GitHub Actions.

Build invariants:

- Node version comes from `package.json` (`engines.node`).
- Vercel installs with `npm ci`.
- the protected GitHub Build compiles a source tree with `.vercelignore` applied, so deploy-excluded imports fail before merge;
- every `main` push receives a non-mutating `Production Smoke`: it waits for Vercel success on that exact SHA, then checks the production alias and backend readiness.

Do not diagnose a release solely from a green preview or a local build. Confirm the `Vercel` status on the exact `main` SHA and the production alias.

## Backend deployment

Normal backend releases are **not built on Oracle**.

`deploy-backend.yml` is triggered by production backend/config/migration changes and executes:

1. native amd64 and arm64 image builds on GitHub-hosted runners;
2. publish exact-SHA architecture tags to GHCR;
3. apply pending Supabase migrations;
4. SSH to Oracle and reset the checkout to the exact triggering SHA;
5. `scripts/deploy.sh` detects Oracle architecture, pulls the exact GHCR image, resolves/logs the image digest, and starts API + worker with `--no-build`;
6. deployment waits for API readiness, worker health, queue health, and exact release SHA.

The source-build path in `scripts/deploy.sh` is retained as a recovery fallback. Seeing `Oracle build skipped` during a normal release is expected and desirable.

### Migration safety

Migrations run **before** the new application image is started. Application rollback can restore the previous image, but it does not automatically reverse a database migration. Therefore every production migration must be compatible with both the currently running release and the new release.

Use expand/contract for destructive changes:

1. add new schema while old readers/writers still work;
2. deploy code that can tolerate both shapes;
3. migrate/backfill data if needed;
4. remove old schema only in a later independently safe release.

A one-step DROP/rename that makes the old release invalid is not deployment-safe even if fresh-database CI passes.

## Backend environment

GitHub Actions writes `backend/.env` on Oracle. Important values include:

| Variable | Purpose |
|---|---|
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Postgres + private Storage service access |
| `SUPABASE_ANON_KEY` | publishable Supabase key used by backend helpers where needed |
| `SENTRY_DSN_BACKEND` / `SENTRY_ENV` | backend telemetry |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | optional Ask provider |
| `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS` | OpenTelemetry export |
| `RELEASE` | exact deployed Git SHA, written by `scripts/deploy.sh` |
| `BACKEND_IMAGE` | resolved exact image reference used by Compose |

The frontend BFF uses `MUSIC_BACKEND_URL`. Do not reintroduce the historical `BACKEND_URL` name into Vercel configuration.

## Health and release identity

User-facing health endpoints go through Vercel:

```bash
curl https://hello-ai-wheat.vercel.app/api/health/live
curl https://hello-ai-wheat.vercel.app/api/health/ready
curl https://hello-ai-wheat.vercel.app/api/health/queue
```

Expected properties:

- `live.status == "alive"` and includes backend release SHA;
- `ready.status == "ready"` with database/storage/Supabase true;
- `queue.status == "ready"` with a recent worker heartbeat and no unhealthy stale-lease state.

The backend container also exposes `/health/live` and `/health/ready` locally on Oracle. `scripts/deploy.sh` uses those local gates plus `/health/queue` before accepting a release.

## Rollback

`scripts/deploy.sh` records the previous release before replacement. If the new containers fail health/release gates, it attempts to restore the previous prebuilt image (or source fallback) and health-checks that rollback.

Manual rollback is a release operation, not a routine restart. Prefer redeploying a known-good exact SHA through the workflow. Remember that an already-applied migration remains in the database; verify schema compatibility before rolling code backward.

## CI / merge safety

The repository keeps one stable branch-protection context named `build`. It is an **aggregate gate**, not merely a frontend compile:

- compile + frontend tests run inside Build;
- the final `build` waits for the latest required workflows on the exact PR head SHA;
- non-doc code requires CI + mocked E2E;
- runtime boundary changes require fresh Real-stack E2E;
- database/domain changes require Database Integration;
- backend/deploy changes require native Backend Image validation;
- CodeQL, Dependency Review, and Gitleaks are always required for merge-ready PRs.

Argos remains visual evidence and is non-blocking by design. Draft PRs avoid heavyweight lanes where possible; make only the active merge candidate non-draft.

Evaluation-only `backend/evaluation/**` and backend test-only changes are intentionally excluded from native image and real-stack triggers unless another changed file crosses a production runtime boundary.

## Production verification levels

### Routine release smoke — automatic, non-mutating

`Production Smoke` runs after every `main` push. It verifies Vercel success for the exact SHA, the production HTML document, and live/ready/queue endpoints. This is the default release signal.

### Deep production browser verification — manual, mutating

`Production Verify` runs `tests/e2e/production-verify.spec.ts`, which creates a real authenticated session/import and therefore mutates production data. Run it deliberately for cross-stack incidents or high-risk releases, not on every merge. Its generated accounts/works are operational test data and should be periodically cleaned up.

### Fresh isolated real-stack — pre-merge

`Real-stack E2E` boots disposable local Supabase, real FastAPI + worker, a production Next.js build, and a licensed audio fixture. This is the pre-merge proof for critical cross-boundary behavior; it is not a substitute for production release smoke.

## Observability

- Frontend: Sentry via `NEXT_PUBLIC_SENTRY_DSN`; source-map upload is enabled when the Sentry build credentials are present.
- Backend: `SENTRY_DSN_BACKEND` plus OpenTelemetry OTLP export.
- Backend logs are structured stdout and include request IDs; `docker compose logs -f backend worker` is the direct Oracle fallback.
- `/api/health/queue` exposes aggregate worker/queue state without user payloads.

Do not put credentials, DSNs with secrets, provider tokens, or private audio into documentation or CI artifacts.

## Dependency / supply-chain maintenance

- GitHub Actions references are full-SHA pinned; `scripts/check_actions_pinned.py` enforces this.
- Dependabot covers GitHub Actions, npm, backend uv dependencies, and backend Docker base images.
- npm deploys use the committed lockfile; backend images use `uv sync --locked`.
- Deployed backend releases are immutable by image digest after publication. Upstream base images/apt repositories are not fully hermetic snapshots yet; treat digest/snapshot pinning as future supply-chain hardening rather than silently assuming bit-for-bit rebuild reproducibility.

## Known operational hygiene debt

- GitHub repository setting `delete_branch_on_merge` is currently disabled, so historical merged branches accumulate. Do not delete branches blindly while parallel agents may still be using them; enable automatic deletion in repository settings or prune only branches proven merged/closed and inactive.
- Several backend orchestration modules remain large. Prefer extracting cohesive services at natural change boundaries instead of adding unrelated responsibilities to `domain/capabilities.py`, `domain/api.py`, `domain/repositories.py`, `domain/job_worker.py`, or `analyze.py`.
