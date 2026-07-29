# Phase 0 Review — Baseline and Safeguards

## Phase
0

## Completed Outcomes

### Reproducible Setup
- `npm run dev` starts Next.js on :3000
- `docker compose up backend` starts FastAPI on :8000
- `.env.example` documents all required variables
- `docs/LOCAL_DEV.md` and `DEVELOPMENT.md` cover Docker + native setups

### Baseline Evidence

| Evidence | Status | Artifact |
|---|---|---|
| TypeScript typecheck | ✅ Pass | `tsc --noEmit` — clean |
| Vitest component tests | ✅ Pass | 2 files, 5 tests (PianoRoll, Home) |
| Python pytest | ✅ Pass | 30 tests (health, security, contract, transcribe, observability, root) |
| Playwright E2E | ✅ Pass | 8 specs (auth, journey, landing, library, signed-in-flow, transcribe, user-paths, ux-validation) |
| Next.js build | ✅ Pass | Clean production build |
| User flow screenshots | ✅ Complete | Transcribe, Library, Analyze tabs captured |
| Schema/storage inventory | ✅ Complete | `docs/SCHEMA_INVENTORY.md` |
| Risk register | ✅ Complete | `docs/RISK_REGISTER.md` (12 risks identified) |
| Orchestration plan | ✅ Complete | `docs/ORCHESTRATION.md` |

### Production Deployment Path
- Frontend: Vercel (automatic on push to main)
- Backend: Oracle VM via `scripts/deploy.sh` + `deploy-backend.yml` (manual trigger or push to main for `backend/**`)
- Auto-rollback on backend deploy failure

### Backup and Rollback
- Backend: auto-rollback to previous commit if health check fails
- Frontend: Vercel instant rollback
- Database: Supabase managed backups, point-in-time recovery
- Storage: No automated backup — files in Supabase Storage

### Known Flaky Tests
None — all test suites pass consistently.

## Gate Evidence

### Universal Gate Checklist

| Criterion | Status | Notes |
|---|---|---|
| Acceptance criteria demonstrated | ✅ | All baseline tests pass |
| Required tests pass in CI | ✅ | 8 CI workflows configured, all blocking checks green |
| User-visible work has screenshots | ✅ | 3 tab screenshots captured |
| Migrations have rollback and validation | ⚠️ | No domain model migrations yet; existing RLS migrations are idempotent |
| Failures are observable and recoverable | ⚠️ | Sentry configured; no structured job recovery yet |
| Documentation is updated | ✅ | ORCHESTRATION.md, RISK_REGISTER.md, SCHEMA_INVENTORY.md, PHASE_0_REVIEW.md created |
| No unresolved blocker violates SOT | ✅ | No SOT violations in current code (it's a pre-SOT implementation) |
| Temporary compatibility code has owner | N/A | No compatibility code yet |

### Phase 0 Specific Evidence

| Requirement | Status |
|---|---|
| Reproducible setup | ✅ |
| Baseline user-flow recording | ✅ |
| Test report | ✅ |
| Schema/storage inventory | ✅ |
| Risk register | ✅ |

## Test and CI Status

```
TypeScript typecheck  → PASS (0 errors)
Vitest component      → PASS (2 files, 5 tests)
Python pytest         → PASS (30 tests)
Next.js build         → PASS
Playwright E2E        → PASS (8 specs)
```

## Migration Status

No domain model migrations exist yet. Current schema (4 migrations) is stable and all deployable. The `tracks`, `jobs`, and `trained_models` tables are vestigial from earlier MusicGen feature and have no current read/write paths.

## Risks and Unresolved Issues

1. **Request-bound ML** (R09): Basic Pitch times out on large files. Phase 2 addresses this.
2. **Host proxy body limit** (R12): 1MB limit on Oracle VM proxy. Browser signed-upload path exists but not yet integrated.
3. **Public storage reads** (R04): Playback relies on `getPublicUrl()`. Phase 2 migration to signed URLs needed.
4. **No domain model** (Gap): Current `LibFile`-centric model violates ADR-001 through ADR-006. Phase 1 starts this work.
5. **E2E tests are MSW-mocked**: Real backend regressions (like 413 proxy limit) are not caught in CI.

## Documentation Synchronization

| Document | Status |
|---|---|
| `docs/ORCHESTRATION.md` | ✅ Created — bundle-to-repository gap analysis |
| `docs/RISK_REGISTER.md` | ✅ Created — 12 items from bundle adapted to repo |
| `docs/SCHEMA_INVENTORY.md` | ✅ Created — complete database + storage map |
| `docs/PHASE_0_REVIEW.md` | ✅ Created — this document |
| `04_REFERENCE_IMPLEMENTATION/` (bundle) | ⬜ Needs update with current repo state |

## Compatibility Paths and Removal Dates

No compatibility code exists yet. The `tracks` table (from MusicGen prototype) may be dropped in a future cleanup migration.

## Decision

**Conditional Pass** — Phase 0 gates are substantially met. Two items need non-blocking follow-up:

1. Update `04_REFERENCE_IMPLEMENTATION/` docs in the bundle to reflect the audited repository state
2. The proxy body limit (R12) is a known production issue that should be addressed in Phase 2 alongside the job system

**Phase 1 may begin.** Domain contracts are the highest-value unblocked work.
