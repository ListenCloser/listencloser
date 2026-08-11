# Agent source of truth

Read `PRODUCT_VISION.md`, `ROADMAP.md`, `ARCHITECTURE.md`, and `AUDIT.md` before
changing product behavior.

## Current system

| Concern | Location |
|---|---|
| Canonical workspace | `app/page.tsx` |
| Workspace panels | `components/workspace/` |
| Persistent frontend state | `lib/stores/` |
| Browser API client | `lib/api-client.ts` |
| Vercel proxy routes | `app/api/v1/` |
| FastAPI domain API | `backend/domain/api.py` |
| Domain contracts | `backend/domain/models.py`, `lib/domain.types.ts` |
| Durable worker | `backend/worker.py`, `backend/domain/job_worker.py` |
| Music capabilities | `backend/domain/capabilities.py` |
| Database and storage | `supabase/migrations/` |

There is one product architecture. Do not reintroduce the deleted browser-only
library, tabbed studio, `/music/*` API, or browser-owned workflow orchestration.

## Product rules

- Show only persisted artifacts, entities, and insights. Never fabricate musical
  output to fill an empty state.
- A state-changing route requires Supabase authentication and owner checks.
- A workflow's input versions must belong to the supplied project.
- User uploads must enforce type and size limits before processing.
- Storage stays private; expose individual objects with short-lived signed URLs.
- Long-running work belongs to the durable worker. The browser may start a job,
  poll it, reconnect to it, and display its outcome.
- New generation, correction, or analysis claims require an implementation,
  provenance, evaluation, and failure UI before becoming a visible feature.

## Code conventions

- Use the design tokens in `app/globals.css`; do not add arbitrary visual values
  when a token exists.
- Proxy backend calls through `lib/backend.ts`; never expose the VM credential to
  browser code.
- Keep Python and TypeScript domain shapes aligned.
- Preserve immutable artifact versions and record producing jobs and lineage.
- Add deterministic tests for new behavior and regression tests for defects.

## Required verification

```bash
npm run lint
npm run typecheck
npm test
npm run build
ruff check backend
ruff format backend --check
python -m pytest backend/tests -q
npx playwright test tests/e2e
```

Playwright requires its pinned Chromium binary. CI installs it. A real deployed
audio smoke test is also required before release because mocked E2E cannot prove
model, worker, storage, or network availability.

## Git and safety

- Work on a feature/fix branch and use Conventional Commits.
- Preserve unrelated user changes and stage reviewed paths explicitly.
- Never commit credentials, generated caches, recordings without clear rights,
  or private user artifacts.
- Do not weaken CI or authentication to make a test pass.
