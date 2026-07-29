# Orchestration — Phase 0 Baseline & Implementation Plan

Generated from `hello-ai-autonomous-handoff` bundle v1.0.

## 1. Baseline Audit Plan

### Audit checklist (per `10_REPOSITORY_DOCS/STARTUP_AUDIT_CHECKLIST.md`)

| Check | Result |
|---|---|
| Local startup works | ✅ `npm run dev` starts, `npm run build` passes |
| Frontend connectivity | ✅ Next.js 15 on Vercel with Supabase anon key |
| API connectivity | ✅ Proxy via `lib/backend.ts` → Oracle VM FastAPI |
| Backend connectivity | ✅ uvicorn on :8000, 13 endpoints |
| Database connectivity | ✅ Supabase Postgres, RLS hardened |
| Storage connectivity | ✅ 9 Supabase buckets (library, midi, transcriptions, enhanced, analysis, audio, datasets, adapters, soundfonts) |
| Auth connectivity | ✅ Supabase Auth with Google OAuth, email confirmation |
| Environment inventory | `.env.example` has all required vars |
| CI status | ✅ 8 workflows, all blocking checks pass |
| Current schema | 4 migrations: tracks, jobs/models, library storage, RLS hardening |
| Critical user journey | ✅ Audio upload → transcribe → score → analyze → library |
| Processing endpoints | Synchronous Basic Pitch, music21, FluidSynth, ffmpeg |
| Active/dead code paths | Tab-based Studio shell, no workspace domain model |
| TS/Python contract drift | Manual duplication — no generated types |
| Production deployment | Vercel (frontend) + Oracle VM (backend) via `deploy.sh` |
| Backup/rollback | Auto-rollback on backend deploy failure |
| Screenshots | `screenshots/` directory with Argos baselines |
| Flaky tests | None — all 5 Vitest + 30 pytest + 8 E2E pass consistently |

### Commands to reproduce baseline

```bash
npm run typecheck        # Clean
npm run build            # Clean
npx vitest run           # 2 files, 5 tests pass
cd backend && .venv/bin/python -m pytest tests/ -q  # 30 pass
npx playwright test      # 8 E2E specs pass (via MSW mocks)
```

---

## 2. Repository-to-SOT Gap Map

Gaps between current repository and handoff bundle target architecture, organized by bundle SOT layer.

### Domain / Data Model (ADRs 001-006 violated)

| Gap | Severity | Bundle Reference |
|---|---|---|
| No `Project` entity — session-scoped state only | Critical | `02_DOMAIN_AND_DATA_MODEL.md` |
| No `Work` entity — musical identity missing | Critical | `02_DOMAIN_AND_DATA_MODEL.md` |
| No `Artifact` abstraction — storage path IS identity | Critical | `06_ARCHITECTURAL_PROHIBITIONS.md` line 9 |
| No `Version` immutability — `LibFile` fields mutated in place | Critical | `02_PRODUCT_PRINCIPLES.md` #5 |
| No `Entity` model — notes are raw JSON objects | High | `02_DOMAIN_AND_DATA_MODEL.md` |
| No `Insight` model — analysis is inline fields | High | `02_PRODUCT_PRINCIPLES.md` #9 |
| No `Alignment` mapping — timeline is implicit | High | `04_TIMELINE_SELECTION_AND_TRANSPORT.md` |
| No `Job` system — processing is synchronous HTTP | Critical | `03_PROCESSING_AND_CAPABILITIES.md` |
| No capability contracts — ffmpeg/Basic Pitch/music21 called directly | High | `03_PROCESSING_AND_CAPABILITIES.md` |

### Frontend / Workspace

| Gap | Severity | Bundle Reference |
|---|---|---|
| Tab-based navigation, not workspace shell | Critical | `03_WORKSPACE_BLUEPRINT.md`, `06_ARCHITECTURAL_PROHIBITIONS.md` line 1 |
| No shared transport — per-component playback state | Critical | `04_TIMELINE_SELECTION_AND_TRANSPORT.md` |
| No shared selection — no cross-representation sync | Critical | `06_INTERACTION_RULES.md` items 1-2,6 |
| No piano roll as primary representation | High | `00_DESIGN_SOT_INDEX.md` line 8 |
| No representation registry — components ad-hoc | High | `04_COMPONENT_ATLAS.md` |
| No inspector panel | Medium | `03_WORKSPACE_BLUEPRINT.md` |
| Processing state uses booleans (`isTranscribing`), not job state | High | `05_STATE_GALLERY.md` |
| Page-per-feature pattern (Library / Transform / Analyze / Chat tabs) | Critical | `06_ARCHITECTURAL_PROHIBITIONS.md` line 1 |

### Infrastructure

| Gap | Severity | Bundle Reference |
|---|---|---|
| No durable async processing | Critical | `03_PROCESSING_AND_CAPABILITIES.md` |
| Storage is partially public | Medium | `03_REFERENCE_IMPLEMENTATION.md` |
| No versioned API | Medium | `engineering/api-contracts.md` |
| Python/TypeScript contracts manually duplicated | Medium | `06_KNOWN_GAPS.md` |

---

## 3. Current Phase Assessment

The repository is at **Phase 0** of the handoff bundle's roadmap.

- Phase 0 gates partially met: tests pass, CI green, basic screenshots exist, schema inventory exists
- Phase 0 gaps: no complete risk register, no explicit user-flow recording, no schema/storage inventory as a single artifact
- The existing `docs/ROADMAP.md` describes a different sequencing (analysis-first), but the bundle's roadmap (domain contracts → durable data → workspace foundation → vertical slices) is the authoritative plan per `01_MASTER_ROADMAP.md`

### Parallelization opportunity

The existing `REDESIGN.md` infrastructure work (in-repo Caddy, browser signed uploads, `--workers 2`, Redis/RQ) addresses the bundle's Phase 2 (durable jobs) infrastructure component and can be scoped accordingly.

---

## 4. Dependency Graph (Adjusted to Repository Reality)

```
                          ┌─────────────────┐
                          │  Phase 0: Base   │
                          │  (complete gaps) │
                          └────────┬────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            ┌───────────┐  ┌───────────┐  ┌───────────┐
            │Domain     │  │Timeline/  │  │Job        │
            │Contracts  │  │Selection  │  │Contracts  │
            │(Pydantic) │  │Contracts  │  │(spec)     │
            └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                  │              │              │
      ┌───────────┼──────┐       │      ┌───────┼───────┐
      ▼           ▼      ▼       │      ▼       ▼       ▼
  ┌───────┐ ┌───────┐ ┌─────┐   │  ┌───────┐ ┌───────┐ ┌───────┐
  │TS     │ │DB     │ │API  │   │  │Worker │ │Repo   │ │RLS    │
  │Types  │ │Migrations│Shim │   │  │Loop   │ │Layer  │ │Tests  │
  └───┬───┘ └───┬───┘ └──┬──┘   │  └───┬───┘ └───┬───┘ └───┬───┘
      │         │       │       │      │         │         │
      └────┬────┴───────┘       │      └────┬────┴────┬────┘
           │                    │           │         │
           ▼                    │           ▼         ▼
    ┌────────────┐              │    ┌─────────────────────┐
    │Type-valid  │              │    │ Phase 2: Durable    │
    │contracts   │              │    │ Data & Jobs (gate)  │
    └──────┬─────┘              │    └──────────┬──────────┘
           │                    │               │
           └────────────┬───────┘               │
                        │                       │
                        ▼                       │
              ┌─────────────────┐               │
              │ Phase 3:        │◄──────────────┘
              │ Workspace Shell │
              │ Gate: shared    │
              │ transport/      │
              │ timeline/       │
              │ selection       │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Phase 4:        │
              │ Understand Slice│
              └─────────────────┘
```

---

## 5. First Implementation-Ready Task Packages

### Task P0-01: Complete Phase 0 Baseline Evidence

| Field | Value |
|---|---|
| **Task ID** | P0-01 |
| **Title** | Complete Phase 0 baseline evidence |
| **Owner** | Orchestrator |
| **Phase** | 0 |
| **Goal** | Close remaining Phase 0 gate gaps so we can advance |
| **In scope** | Run startup audit checklist, record user journey (screenshots/capture), inventory schema/storage as artifacts, compile risk register against bundle `05_RISK_REGISTER.md`, verify all checks pass |
| **Out of scope** | Any code changes, domain model introduction |
| **Acceptance criteria** | All 13 startup audit items verified; screenshots of Library, Transcribe, Analyze, Piano Roll, Sheet Music; risk register written to `docs/RISK_REGISTER.md`; Phase 0 gate review written |
| **Required tests** | All existing tests pass (typecheck, vitest, pytest, playwright) |
| **Required evidence** | Screenshots at 1180×1000 of each tab; risk register |
| **Documentation updates** | `04_REFERENCE_IMPLEMENTATION/` files updated with current state |

### Task P1-01: Define Python Domain Contracts

| Field | Value |
|---|---|
| **Task ID** | P1-01 |
| **Title** | Define Pydantic domain contracts for core entities |
| **Owner** | Domain/Data agent |
| **Phase** | 1 |
| **Goal** | Introduce Project, Work, Artifact, Version, Entity, Insight, Alignment, Job as versioned Pydantic models with contract tests |
| **Dependencies** | P0-01 (Phase 0 gate) |
| **In scope** | `backend/domain/models.py` with canonical contracts; `backend/domain/__init__.py`; contract validation tests; JSON schema exports |
| **Out of scope** | Database tables, API endpoints, frontend types, existing code migration |
| **SOT references** | `03_ARCHITECTURE_SOT/02_DOMAIN_AND_DATA_MODEL.md`, `01_PRODUCT_SOT/03_CANONICAL_LANGUAGE.md` |
| **Ownership boundaries** | Domain/Data agent owns `backend/domain/`; no frontend changes |
| **Required contracts** | Each model must declare: id, ownership, lineage, provenance, metadata |
| **Acceptance criteria** | All entities from canonical language defined; Pydantic v2 models with validators; contract tests pass; JSON schema export round-trips |
| **Required tests** | Unit tests for each model; serialization/deserialization round-trip; validation of required fields |
| **ADR required** | ADR-007: Domain model adoption plan (how old `LibFile` maps to new entities) |

### Task P1-02: Generate TypeScript Domain Types

| Field | Value |
|---|---|
| **Task ID** | P1-02 |
| **Title** | Generate TypeScript types from Python domain contracts |
| **Owner** | Domain/Data agent |
| **Phase** | 1 |
| **Goal** | TypeScript types for domain contracts, eliminating manual duplication |
| **Dependencies** | P1-01 |
| **In scope** | `lib/domain.types.ts` generated from Pydantic JSON schema; zod schemas for runtime validation; contract test verifying TS ↔ Python alignment |
| **Out of scope** | Database migration, frontend refactoring, API changes |
| **SOT references** | `05_EXECUTION/02_PHASE_GATES.md` Phase 1 evidence; `engineering/api-contracts.md` |
| **Ownership boundaries** | Domain/Data agent; no frontend code changes yet |
| **Required contracts** | Generated types must match Pydantic schema exactly |
| **Acceptance criteria** | `lib/domain.types.ts` exists; zod schemas validate; contract test proves TS matches Python JSON schema |
| **Required tests** | Contract test: Python exports JSON schema → TypeScript validates against it |

### Task P1-03: Add Canonical ADRs

| Field | Value |
|---|---|
| **Task ID** | P1-03 |
| **Title** | Author accepted ADRs for bundle architectural decisions |
| **Owner** | Orchestrator |
| **Phase** | 1 |
| **Goal** | Formalize ADR-001 through ADR-006 as accepted decisions in the repository |
| **Dependencies** | P0-01 |
| **In scope** | `docs/adr/` directory with ADR-001 through ADR-006 using bundle template |
| **Out of scope** | New decisions, implementation |
| **SOT references** | `03_ARCHITECTURE_SOT/08_DECISION_LOG.md`, `08_TEMPLATES/ADR.md` |
| **Acceptance criteria** | 6 ADRs filed with status=accepted; each references bundle SOT |
| **Documentation updates** | `docs/adr/README.md` index |

---

## Phase 0 Gate Checklist

Before advancing to Phase 1, the following must be completed:

- [x] Reproducible setup documented (`docs/LOCAL_DEV.md`)
- [x] TypeScript typecheck passes
- [x] Vitest component tests pass (5/5)
- [x] Python pytest tests pass (30/30)
- [x] Playwright E2E tests pass (8 specs)
- [x] Next.js build passes
- [ ] Baseline user-flow recording (screenshots of each tab)
- [ ] Schema/storage inventory artifact
- [ ] Risk register written (`docs/RISK_REGISTER.md`)
- [ ] Phase 0 gate review document
- [ ] Current repository docs updated to match reality

---

## Bundle SOT Invariants (Must Not Violate)

These are read-only during implementation:

1. **Piano roll is primary** — default representation when notes exist
2. **One transport** — single global playback state
3. **One selection** — synchronized across all representations
4. **Immutable versions** — originals never overwritten
5. **No page-per-feature** — workspace modes, not tabs
6. **No AI-owned canonical state** — AI produces insights, not ground truth
7. **Workflows depend on capabilities, not implementations** — no direct library imports in domain logic
8. **Storage paths are not identity** — use UUIDs, not paths

## Operating Rules (Per Bundle)

- Implement in small deployable vertical slices
- Preserve existing working behavior until replacement verified
- Require proof: tests, screenshots, traces, fixtures, or benchmarks
- Keep Reference Implementation documentation synchronized with code
- Record material decisions as ADRs
- Prefer deletion after migration complete
