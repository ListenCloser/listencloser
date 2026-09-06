# Operations Runbook

How to run, observe, and recover the backend on the Oracle VM.

## Topology

```
Browser / Vercel (Next.js)
        │  /api/* proxy
        ▼
Oracle VM  ── docker compose ──► backend (FastAPI :8000)
        │                       └─────► worker (durable jobs)
        │                              │
        │                              ├── Sentry (errors + traces)
        │                              └── JSON stdout logs
        │
        └── observability stack (opt-in)
              Loki ◄── Promtail ◄── container logs
              Grafana (dashboards)
```

Backend deploys run via `deploy-backend.yml` (on push to `main` for `backend/**`) and
via `scripts/deploy.sh` on the VM. Changes are only live once the container is rebuilt on
the VM (see Deploy) — rebuild before concluding a BE change "didn't show up".

## Environment

GitHub Actions writes `backend/.env` on the VM from repository secrets:

| Var | Purpose |
|---|---|
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | DB + Storage access |
| `SENTRY_DSN_BACKEND` | Backend errors/traces |
| `SENTRY_ENV` | `production` on the VM, `development` locally |
| `RELEASE` | Exact deployed Git SHA; written by `scripts/deploy.sh` |

Frontend Sentry uses `NEXT_PUBLIC_SENTRY_DSN` (separate, in the Vercel build).

## Deploy (health-gated)

```bash
# on the VM, inside the repo
./scripts/deploy.sh
```

The workflow first resets the VM checkout to the exact triggering Git SHA. The
script rebuilds the backend and worker containers, polls
`GET /health/ready` and `GET /health/queue`, and **auto-rolls back to the
previous commit** if either service is not healthy within `HEALTH_TIMEOUT`
seconds (default 120). Readiness must report the same release SHA. Rollback is
also health/SHA-gated. Always tail logs after a deploy.

The production image installs Debian's `fluid-soundfont-gm`; readiness and smoke
testing should not accept the low-fidelity numpy fallback as normal production
rendering.

## Restart / rollback

```bash
docker compose up -d --build backend worker  # restart with latest code
docker compose restart backend worker        # restart without rebuild
git checkout <prev_commit> && ./scripts/deploy.sh   # manual rollback
```

# Monitoring & Status — where do I look?
All reachable by a human without touching code. Commands run from your machine unless marked 'on the VM'.

The semantic contract for trace continuity, metric cardinality, initial SLO formulas, and production baselines lives in [`OBSERVABILITY.md`](OBSERVABILITY.md) with the machine-readable companion [`observability_contract.json`](observability_contract.json). This runbook owns how to reach and operate the deployed systems.

## Sentry (errors + traces)
Two Sentry setups, both env-gated (silent if DSN empty):
- Frontend: `NEXT_PUBLIC_SENTRY_DSN` (Vercel project vars + `.env.local`).
- Backend: `SENTRY_DSN_BACKEND`; set in `.env.local` on the VM (`docker-compose.yml:83`).
Verify on VM: `docker compose exec backend printenv SENTRY_DSN_BACKEND` and `docker compose logs backend | grep sentry_initialized`.
A DSN looks like `https://<key>@<org>.<region>.ingest.sentry.io/<project_id>`. To reach the dashboard: open https://sentry.io/ → org switcher → your org → **Issues** (exceptions) and **Performance/Traces** (latency). The org slug + project names are NOT in the repo — derive from `.env.local` DSN or your Sentry account. Backend release identity comes from `RELEASE`, which deployment sets to the exact Git SHA.

## Logs (Loki / Promtail / Grafana)
Backend emits structured JSON to stdout (`{ts,level,logger,msg,req_id}` + `exc` on errors; per-request `{req_id,method,path,status,duration_ms}`). Every request gets `x-request-id` echoed in the response header — copy it to find the exact log line.
Live tail (always works, on VM): `docker compose logs -f backend`.
Grafana/Loki are opt-in: `docker compose -f docker-compose.observability.yml up -d` → Grafana on `:3001`, Loki `:3100`. If `3001` isn't reachable, `ssh -L 3001:localhost:3001 <vm-user>@<vm-ip>` then open http://localhost:3001 (admin / `$GRAFANA_PASSWORD`). Query Loki: `{container="music-ai-backend"} |= "request_failed"` or `|= "req_id=abc123"`.

## Health (is the backend up?)
`curl https://gricci-testing.duckdns.org/health/live` returns liveness plus the
release SHA; `/health/ready` verifies the database schema and private artifact
storage; `/health/queue` reports recent
worker heartbeats, queued/running jobs, and stale leases. The Vercel-facing queue
check is `/api/health/queue`.

Worker heartbeats require `20260811_worker_heartbeats.sql`. A heartbeat older
than 45 seconds is not counted as live.

Backend deploys apply pending migrations before touching the VM. Configure the
GitHub Actions secret `SUPABASE_DB_URL` with the pooler/session-mode Postgres
connection string from Supabase Database settings. Failed migrations block deployment.
PRs that touch migrations also boot a clean local Supabase instance and run the
full migration history plus an insert/claim/run/succeed lifecycle check.

## Deployed understanding smoke test

Use `.github/workflows/production-smoke.yml` as the maintained deployed verification contract. It verifies the production release and durable application path without requiring a repository-owned user token or a deleted local smoke helper. Use the required real-stack workflow for local Vercel-like → FastAPI → worker → Supabase verification before merge.

## CI (did my PR break anything?)
Repo → Actions tab. Workflows: `build.yml` (build+vitest, blocks), `ci.yml` (lint+typecheck+ruff+pytest, blocks), `e2e.yml` (Playwright vs mocks, blocks), `database-integration.yml` (real local Postgres/Supabase migrations), `argos.yml` (visual, NON-blocking), `codeql.yml`, `gitleaks.yml`, `dependency-review.yml`, `deploy-backend.yml` (push only).

## Vercel production ownership

`listen-closer.vercel.app` must be assigned to the v2 project built from this repo's
`main` branch. A green Vercel preview is not production. Required environment:
`BACKEND_URL`, `NEXT_PUBLIC_SUPABASE_URL`, and
`NEXT_PUBLIC_SUPABASE_ANON_KEY`. After aliasing, verify the root title is
`Listen Closer` and `/api/health/queue` is ready before smoke testing.

## Argos (visual diffs)
`https://app.argos-ci.com` (needs `ARGOS_TOKEN` repo secret); also comments a visual diff on each PR. Non-blocking by design.

## Supabase (storage/DB/auth/RLS)
Dashboard from `.env.local` `SUPABASE_URL` (`https://<ref>.supabase.co` → supabase.com/dashboard/project/<ref>). Check buckets, `jobs`/`models` tables, Auth users, RLS policies (`supabase/migrations/`).

## Links to add (owner-only — paste from your accounts, never commit tokens)
- [ ] Sentry org slug + frontend/backend project URLs
- [ ] Supabase project dashboard URL
- [ ] Grafana base URL / VM IP (and whether 3001 is exposed)
- [ ] Argos project URL
- [ ] Backend public URL for health curls
