# Agent source of truth

This repository is intentionally documented so implementation agents can work autonomously without inventing product direction.

## Read order

Before changing product behavior, analysis, architecture, or infrastructure, read:

1. **`MASTER_SPEC.md`** — authoritative product + architecture + roadmap source of truth.
2. **`AGENT_EXECUTION_PLAYBOOK.md`** — required implementation, verification, PR, CI, and escalation behavior.
3. **`RESEARCH_LANDSCAPE.md`** — MIR / foundation-model / OSS / benchmark reference for music-engine work.
4. Relevant ADR(s) in `docs/adr/`.
5. Relevant GitHub issue and recent PRs.
6. **`backend/config/capabilities.json`** before exposing or changing analysis claims.

Older `PRODUCT_VISION.md`, `ROADMAP.md`, `ARCHITECTURE.md`, analysis reports, and audit documents remain useful historical/runtime context, but `MASTER_SPEC.md` wins when product direction conflicts unless a newer ADR explicitly supersedes it.

Runtime code, database migrations, deployed configuration, and the capability registry remain authoritative for what is actually shipped today. Documentation must not claim that an unmerged or unevaluated feature is production behavior.

## Current system map

| Concern | Location |
|---|---|
| Canonical workspace | `app/page.tsx`, `components/workspace/` |
| Persistent frontend state | `lib/stores/` |
| Browser API client | `lib/api-client.ts` |
| Generated API contracts | `lib/api-types.ts` and generation scripts |
| Vercel proxy routes | `app/api/v1/` |
| FastAPI domain API | `backend/domain/api.py` |
| Domain contracts | `backend/domain/models.py` |
| Durable worker | `backend/worker.py`, `backend/domain/job_worker.py` |
| Music capabilities | `backend/domain/capabilities.py`, `backend/engines/` |
| Capability maturity / exposure | `backend/config/capabilities.json`, `backend/domain/capability_policy.py` |
| Database and storage | `supabase/migrations/` |
| Evaluation | `backend/evaluation/`, test fixtures, evaluation docs |
| Observability | OpenTelemetry instrumentation + Grafana configuration/docs |

## Non-negotiable product rules

- The product is organized around one persistent musical **Work** with synchronized representations, playback, selection, and evidence.
- **Representation != playback source.** Do not couple them accidentally.
- Show only real persisted/evaluated evidence. Never fabricate musical facts to fill empty states.
- `capabilities.json` gates user-visible analysis maturity. Backend policy is authoritative; do not create a second frontend truthfulness registry.
- Unknown / unavailable is a valid result.
- Hard MIR inference should use evaluated OSS/research systems before bespoke heuristics.
- The LLM explains and orchestrates evidence; it is not the sole detector for exact musical facts.
- Long-running work belongs to the durable worker. Browser code may start, poll, reconnect, and render outcomes.
- Storage remains private; expose objects through authenticated/signed paths.
- Preserve immutable artifact/version lineage and provenance.
- State-changing routes require authentication and owner checks.

## Scope discipline

Do not reintroduce deleted browser-only workflow orchestration, disconnected mini-app tabs, fake generation/correction surfaces, or duplicated source-of-truth state.

Do not add enterprise infrastructure (Kubernetes, Kafka, service mesh, Backstage, Jenkins alongside GitHub Actions, self-hosted Grafana, heavyweight feature flags) without a demonstrated requirement and ADR.

## Code conventions

- Use existing design tokens/components before inventing new visual primitives.
- Proxy backend calls through the established authenticated API path; never expose VM/service credentials to browser code.
- Prefer generated OpenAPI transport types over duplicated handwritten API schemas.
- Keep model/library-specific structures inside engine adapters; product/domain code consumes canonical result contracts.
- Add deterministic tests for derived logic and regression tests for defects.
- Preserve unrelated user changes and use isolated branches/worktrees for parallel agents.

## Verification

Do **not** mechanically run every command for every tiny PR. Use the test ladder in `AGENT_EXECUTION_PLAYBOOK.md` and run the strongest tests needed to prove the claim.

Common commands include:

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

For core music/workflow changes, mocked tests are insufficient. Verify the relevant real-stack or production path with a licensed fixture and inspect persisted output / browser behavior.

## Git and safety

- Work on feature/fix/eval/docs branches and use clear commits.
- Reconcile open PRs before creating duplicates.
- Close superseded PRs with an explanation.
- Never commit credentials, private user artifacts, unlicensed recordings, generated caches, or secret-bearing logs.
- Do not weaken CI, RLS, authentication, truthfulness gates, or tests simply to obtain green checks.
- Routine safe PRs may be merged autonomously when the task instructions authorize it; destructive data changes, paid services, material licensing ambiguity, or major product forks require owner escalation.
