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

## Format

Create `NNNN-short-title.md` with:

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
