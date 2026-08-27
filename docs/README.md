# Documentation map

This directory is the durable source of truth for product, architecture, research, operations, and autonomous-agent behavior.

## Authority hierarchy

1. **`MASTER_SPEC.md`** — product north star, musical-understanding model, target architecture, roadmap, product/engineering principles.
2. **`CURRENT_STATE.md`** — fast snapshot of current `main`/capability state; verify deployed SHA for production claims.
3. **`ANALYSIS_V3_IMPLEMENTATION_PLAN.md`** — concrete Analysis V3 sequencing, bakeoff contracts, decision gates, and first implementation-agent task.
4. **`AGENT_EXECUTION_PLAYBOOK.md`** — required autonomous implementation and verification process.
5. **`RESEARCH_LANDSCAPE.md`** — current MIR / OSS / foundation-model / benchmark adoption reference.
6. **`AGENTS.md`** — compact agent entry point and repository map.
7. **ADRs (`adr/`)** — explicit architectural decisions; a newer accepted ADR may supersede a section of the master spec and must update it promptly.
8. **`ARCHITECTURE.md`** — current shipped runtime contract.
9. **`OPS.md`, `TEST_ENVIRONMENT.md`** — operational and testing procedures.
10. Historical/audit/evaluation docs — supporting evidence and context, not automatically current product direction.

## Machine/runtime sources of truth

Documentation never overrides the actual shipped system:

- `backend/config/capabilities.json` — analysis maturity/exposure.
- `supabase/migrations/` — database schema/RLS history.
- current engine registry/configuration — production engine routing.
- GitHub Actions workflows — actual CI/deploy gates.
- deployed readiness/release metadata — production release identity.

If docs and runtime disagree, treat the discrepancy as documentation/config drift and fix it explicitly rather than guessing.

## Current strategic work

- Analysis V3 research program: GitHub issue #327.
  - #332 — foundation representations / similarity / retrieval.
  - #333 — style, instrumentation, and semantic context evidence.
  - #334 — modern source separation and downstream-analysis value.
  - #335 — beat/downbeat/tempo/meter evidence.
  - #337 — optional generic multi-instrument transcription research.
  - #336 — Evidence Graph ERD/contracts after concrete evidence requirements emerge.
- UX V3 redesign: GitHub issue #328.
- Platform V3 architecture/DevEx review: GitHub issue #329.
- Structure remains separately evaluation-gated; consult the relevant issue/capability registry before exposure.

## Updating documentation

Significant product/architecture changes should update the master spec in the same PR or immediately follow with a docs PR. Update `CURRENT_STATE.md` when a capability or major product surface materially changes. Do not allow a long-running parallel set of contradictory “source of truth” documents.
