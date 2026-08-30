# Architecture Decision Records

Use ADRs for decisions that future contributors or agents could reasonably undo, rediscover, or misinterpret.

Examples:
- choosing or replacing a production music/ML engine,
- changing artifact lineage or persistence semantics,
- changing deployment/runtime architecture,
- introducing a major dependency or framework,
- changing trust/withholding policy for analysis capabilities,
- adopting a new cross-cutting frontend or observability architecture.

Do not write ADRs for ordinary local refactors.

## Decision index

The numeric identifier is permanent once an ADR is accepted. Historical ADR-001 through ADR-009 retain their original filenames; new ADRs use the `NNNN-short-title.md` convention. The next unused identifier is **0014**. Never restart the sequence or reuse an identifier from an older naming style.

| ID | Decision | Status | Date |
| --- | --- | --- | --- |
| [ADR-001](ADR-001.md) | One Persistent Project Workspace | accepted | 2026-07-28 |
| [ADR-002](ADR-002.md) | Global Timeline, Transport, and Selection | accepted | 2026-07-28 |
| [ADR-003](ADR-003.md) | Immutable Artifact Versions with Lineage | accepted | 2026-07-28 |
| [ADR-004](ADR-004.md) | Structured Entities and Insights | accepted | 2026-07-28 |
| [ADR-005](ADR-005.md) | Workflows Depend on Capabilities, Not Implementations | accepted | 2026-07-28 |
| [ADR-006](ADR-006.md) | Current App is Reference Implementation, Not Architectural Truth | accepted | 2026-07-28 |
| [ADR-007](ADR-007.md) | Migration: Reference Model to Domain Model | accepted | 2026-07-28 |
| [ADR-008](ADR-008.md) | Canonical Route is Root, Old Shell Must Be Replaced | accepted | 2026-07-29 |
| [ADR-009](ADR-009.md) | Free Three-Plane Runtime with One Release Contract | accepted | 2026-08-11 |
| [0010](0010-oss-first-evidence-gated-music-engines.md) | OSS-first, evidence-gated music engines | accepted | 2026-08-22 |
| [0011](0011-client-cache-before-redis.md) | Prefer client cache boundaries before Redis | accepted | 2026-08-27 |
| [0012](0012-oss-first-frontend-primitives.md) | OSS-first frontend primitives | accepted | 2026-08-30 |
| [0013](0013-architecture-docs-as-code.md) | Architecture documentation as code | accepted | 2026-08-30 |

## Format

Create `NNNN-short-title.md` with the next unused numeric identifier and:

```md
# NNNN: Title

Status: proposed | accepted | superseded | deprecated
Date: YYYY-MM-DD

## Context
What problem/constraint forced the decision?

## Decision
What are we doing?

## Evidence
Benchmarks, operational evidence, alternatives considered, licensing/runtime facts.

## Consequences
What becomes easier/harder? What assumptions must future changes preserve?

## Revisit when
Concrete conditions that justify reconsidering the decision.
```

ADRs describe decisions, not implementation plans. If a decision is superseded, preserve the old ADR and link to the replacement rather than rewriting history.
