# Architecture

How Music AI Studio is put together: the frontend, the backend, the proxy path,
and the delivery/CI loop. This describes the ACTUAL system today, including its
known gaps — not an aspirational design (that lives in `docs/REDESIGN.md`).

## 1. Product

**Music AI Studio** does three things:

- **Transcribe** — audio → MIDI via `basic-pitch`.
- **Analyze** — key / tempo / chords via `librosa`.

## 2. System at a glance

```
┌───────────────────────────────────────────────────────────────────────┐
│  Browser (Next.js 15 / React 19 / Tailwind v4, hosted on Vercel)       │
│    app/page.tsx → app/HomeClient.tsx → <Studio>                        │
│    Studio is a TAB shell: Library | Transcribe | Analyze              │
│                                                                        │
│    Talks to:                                                           │
│      (a) Supabase  — directly from the browser (anon key) for storage │
│      (b) /api/*    — Next.js route handlers that proxy to the backend │
└───────────────┬───────────────────────────┬──────────────────────────┘
                │ (a) anon key              │ (b) server-side fetch
                ▼                            ▼
        ┌───────────────┐          ┌─────────────────────────────────────┐
        │  Supabase     │          │  Oracle Cloud VM (single host)       │
        │  storage +    │          │  gricci-testing.duckdns.org          │
        │  DB + auth    │          │    host reverse proxy (Caddy/nginx)  │
        │               │          │    ~1MB body limit ── HTTP 413 on    │
        │  buckets:     │          │    large uploads to /api/music/*     │
        │   library     │          │      │                              │
        │   midi        │          │      ▼                              │
        │   transcriptions         │    uvicorn (FastAPI :8000)          │
        │   soundfonts  │          │      basic-pitch / librosa                                        │
        │  RLS: owner   │          │    Uses Supabase SERVICE-ROLE key    │
        └───────────────┘          └─────────────────────────────────────┘
```

**Key rule: the browser never talks to the VM directly.** Every backend call goes
`app/api/**/route.ts` → `lib/backend.ts` (`proxyToBackend`) → `MUSIC_BACKEND_URL`
(default `https://gricci-testing.duckdns.org`) → a host-level reverse proxy
(Caddy/nginx) → uvicorn. This keeps the VM URL and service-role key off the client
and makes Vercel the only public web edge.

> The reverse proxy currently enforces a **~1MB request body limit**. This is why
> large audio uploads to `/api/music/analyze` come back as **HTTP 413**. There is
> no proxy config in the repo — it lives on the VM. See `docs/REDESIGN.md`.

## 3. Frontend

- Next.js 15 App Router, React 19, Tailwind v4, OpenSheetMusicDisplay for score rendering.
- Entry: `app/page.tsx` → `app/HomeClient.tsx` → `Studio`.
- `Studio` is a **tabbed shell** with three tabs: **Library**, **Transcribe**,
  **Analyze**. It is NOT a two-column grid and NOT a stepper. The old
  `.stepper` / `.app-grid` CSS is dead and should not be reintroduced.
- Storage access from the browser uses the Supabase **anon** key via `lib/storage.ts`.
- Dev mocks: MSW (`mocks/handlers.ts`) fakes `/api/*` so the frontend can run with
  no backend. See `docs/TESTING.md`.

## 4. Backend

- FastAPI (Python) served by **uvicorn** on a **single Oracle VM**.
- Run via `docker-compose.yml` service `backend`:
  `uvicorn backend.main:app --port 8000 --reload`.
- Uses the Supabase **service-role** key for server-side storage/DB access.
- `backend/main.py` has structured JSON logging + an `x-request-id` middleware
  (echoed on every response so a user-facing error maps to an exact log line).

### Deploy

`scripts/deploy.sh` (run on the VM):

1. `git pull`
2. `docker compose up --build backend`
3. polls `GET /health/ready`
4. **auto-rolls back** to the previous commit if the backend is not healthy in time.

There is also a `deploy-backend.yml` GitHub Actions workflow that runs on push to
`main` for `backend/**` changes. See `docs/OPS.md` for the runbook.

## 5. Storage / DB / auth (Supabase)

- Buckets: `library`, `midi`, `transcriptions`, `soundfonts`.
- RLS is **owner-scoped**.
- Browser: anon key (`lib/storage.ts`). Backend: service-role key.
- Migrations live in `supabase/migrations/`.

## 6. Error tracking (Sentry)

- **Frontend** — `@sentry/nextjs`: `instrumentation.ts`, `sentry.server.config.ts`,
  `sentry.edge.config.ts`, `app/global-error.tsx`. DSN from `NEXT_PUBLIC_SENTRY_DSN`.
- **Backend** — `sentry-sdk`, env-gated on `SENTRY_DSN_BACKEND` (falls back to
  `SENTRY_DSN`). Silent if the DSN is empty.

## 7. Observability

- Structured JSON logs to stdout + `x-request-id` middleware in `backend/main.py`.
- Opt-in Loki / Promtail / Grafana stack via `docker-compose.observability.yml`.
- Runbook: `docs/OPS.md`.

## 8. CI / delivery

GitHub Actions in `.github/workflows/`:

| Workflow | What it does | Blocks merge? |
|---|---|---|
| `build.yml` | `npm run build` + Vitest | ✅ |
| `ci.yml` | lint + typecheck + ruff + backend pytest | ✅ |
| `e2e.yml` | Playwright vs MSW mocks | ✅ |
| `argos.yml` | visual diff | ❌ (informational) |
| `codeql.yml` | SAST (js + python) | ✅ |
| `gitleaks.yml` | secret scan | ✅ |
| `dependency-review.yml` | dependency CVE review | ✅ |
| `deploy-backend.yml` | deploy on push to `main` for `backend/**` | n/a (push) |

Review automation: **CodeRabbit** + **Semgrep** on PRs. The agent uses the
**Sentry MCP** to self-diagnose failures.

## 9. Where things live

| Concern | Path |
|---|---|
| Page shell | `app/page.tsx`, `app/HomeClient.tsx`, `components/Studio.tsx` |
| Transcribe | `components/transcribe/`, `components/SheetMusic.tsx`, `components/PianoRoll.tsx` |
| Analyze | `components/analyze/` |
| Library | `components/library/`, `lib/storage.ts` |
| Backend proxy | `lib/backend.ts`, `app/api/**/route.ts` |
| Supabase client | `lib/supabase.ts` (browser, anon) |
| Backend (VM) | `backend/` (FastAPI) |
| Dev mocks | `mocks/handlers.ts`, `components/MSWInit.tsx` |
| E2E / visual | `tests/e2e/`, `tests/visual/` |
| Ops | `docker-compose.yml`, `docker-compose.observability.yml`, `scripts/deploy.sh` |

## 10. Known gaps (documented honestly)

### Domain / data model gaps (bundle SOT)

- **No durable project/work/artifact model** — CLOSED (Phase 2). Domain tables and
  contracts exist; migration from `LibFile` is in progress per ADR-007.
- **No immutable version graph** — CLOSED (Phase 2). `versions` table with
  lineage tracking; originals are never overwritten.
- **No capability registry in code** — CLOSED (Phase 4). Capability contracts
  with typed inputs/outputs; no direct library imports in domain logic.
- **No processing job system** — CLOSED (Phase 2). Async job queue with status
  polling; processing is no longer synchronous in the request path.
- **No universal alignment representation** — CLOSED (Phase 2). Alignment
  entities map entities to timeline positions for synchronized transport.

### Frontend / workspace gaps (bundle SOT)

- **Representations are not fully synchronized** — IN PROGRESS (Phase 3).
  Shared transport and selection exist; cross-representation sync is being
  wired per vertical slice.
- **Transcription correction is limited** — CLOSED (Phase 5). Piano roll
  editing with versioned correction workflow.
- **Compare and create workflows are not implemented** — CLOSED (Phases 6-7).
  Version diff view and structural composition tools.

### Infrastructure gaps

- **Single VM = SPOF.** No redundancy; one host down = backend down.
- **Prod runs uvicorn `--reload`** — a dev flag. Should be `--workers 2`.
- **No metrics / tracing / alerting yet** — only logs + Sentry.
- **E2E runs against MSW mocks**, so real-API regressions (the 413 / 422 class
  of bugs) are NOT caught by the E2E suite. See `docs/TESTING.md`.
- **`next lint` is deprecated** (removed in Next 16) but still used.

Infrastructure roadmap: `docs/REDESIGN.md`.

## 11. New domain architecture

The domain model, capability contracts, workspace shell, and phased migration
plan are defined in `docs/ORCHESTRATION.md`. This is the SOT for the target
architecture, superseding the reference implementation patterns described
in section 2. See also `docs/adr/ADR-001.md` through `docs/adr/ADR-007.md`.
