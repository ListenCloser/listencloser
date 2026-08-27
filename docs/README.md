# Documentation map

This directory is the durable source of truth for product, architecture, research, operations, and autonomous-agent behavior.

## Authority hierarchy

1. **`MASTER_SPEC.md`** — product north star, musical-understanding model, target architecture, roadmap, product/engineering principles.
2. **`AGENT_EXECUTION_PLAYBOOK.md`** — required autonomous implementation and verification process.
3. **`RESEARCH_LANDSCAPE.md`** — current MIR / OSS / foundation-model / benchmark adoption reference.
4. **`AGENTS.md`** — compact agent entry point and repository map.
5. **ADRs (`adr/`)** — explicit architectural decisions; a newer accepted ADR may supersede a section of the master spec and must update it promptly.
6. **`ARCHITECTURE.md`** — current shipped runtime contract.
7. **`OPS.md`, `TEST_ENVIRONMENT.md`** — operational and testing procedures.
8. Historical/audit/evaluation docs — supporting evidence and context, not automatically current product direction.

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
- UX V3 redesign: GitHub issue #328.
- Platform V3 architecture/DevEx review: GitHub issue #329.
- Structure remains separately evaluation-gated; consult the relevant issue/capability registry before exposure.

## Updating documentation

Significant product/architecture changes should update the master spec in the same PR or immediately follow with a docs PR. Do not allow a long-running parallel set of contradictory “source of truth” documents.
