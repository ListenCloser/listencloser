# 0013: Architecture documentation as code

Status: accepted
Date: 2026-08-30

## Context

The repository already stores architecture, product direction, evaluation results, operations guidance, and ADRs in Markdown, but the architecture itself is only partially visualized and some relationships are described repeatedly in prose. Parallel development increases the cost of stale diagrams: a manually maintained dependency graph or database ERD can look authoritative long after the code has changed.

The repository should keep architecture understandable to humans without introducing a separate proprietary documentation system or relying on an AI-generated picture as the source of truth.

## Decision

Use a small OSS-first docs-as-code stack with clear ownership boundaries.

1. **C4 vocabulary for software architecture.** Human-authored architecture views should distinguish system context, logical containers, deployment topology, and dynamic workflows. Component/code diagrams are added only when they answer a concrete design question.
2. **Mermaid as the default hand-authored diagram source.** Diagrams live beside Markdown and render directly in GitHub. Do not commit hand-maintained binary diagrams when the same information can be expressed as text.
3. **Generated views for facts derivable from code or schema.** Dependency and database diagrams should be generated from their authoritative source rather than redrawn manually. The preferred follow-up tools are dependency-cruiser for TypeScript/JavaScript imports, Import Linter/Grimp for Python architecture contracts, and tbls for PostgreSQL/Supabase schema documentation.
4. **ADRs record durable architectural choices.** Diagrams show structure and flow; ADRs explain why a choice exists, what evidence supports it, and when it should be reconsidered.
5. **Evaluation methodology is documented separately from evaluation outcomes.** `EVALUATION_METHODOLOGY.md` defines the reusable decision protocol. `EVALUATION_DECISIONS.md` remains the ledger of concrete results and next decision-changing evidence.
6. **Plain Markdown remains the storage format.** A searchable static docs renderer may be added later; if a site is needed, MkDocs Material is the preferred first option because it preserves Markdown/Mermaid sources instead of introducing another content database.
7. **Do not introduce experiment-platform infrastructure as part of documentation cleanup.** DVC may be piloted on one result-bearing evaluation track only if it replaces meaningful bespoke provenance/pipeline machinery. MLflow or a developer portal is not justified by documentation needs alone.

## Evidence

- GitHub natively renders Mermaid in Markdown, keeping diagrams reviewable in the same PR as code/docs changes.
- C4 provides a small shared vocabulary that prevents one diagram from mixing user context, logical services, deployment hosts, and code-level details.
- dependency-cruiser and Import Linter can turn intended dependency rules into executable CI contracts instead of documentation-only guidance.
- tbls derives PostgreSQL documentation/ER relationships from the actual schema, avoiding hand-maintained database diagrams.
- The repository already has an ADR process and a decision-oriented evaluation ledger, so this decision extends existing conventions instead of creating a competing documentation system.

## Consequences

- `docs/ARCHITECTURE.md` becomes a set of named architecture views rather than one catch-all topology picture.
- Human diagrams describe intended boundaries; generated diagrams describe actual import/schema relationships. A generated view must not be hand-edited to hide an architectural violation.
- Architecture enforcement tooling should be introduced in bounded follow-up changes so package/lockfile churn does not compete with active frontend/backend migrations.
- Documentation remains easy to read in GitHub without a deployed docs service.
- Contributors must update the relevant architecture view when a change materially alters a depicted boundary or flow.

## Revisit when

- maintaining the same nodes/relationships across several Mermaid diagrams creates material duplication, at which point Structurizr DSL should be considered as a single architecture model with multiple exported views;
- the repository contains enough maintained documentation that navigation/search in GitHub becomes a meaningful bottleneck, at which point MkDocs Material should be added;
- a DVC pilot demonstrably removes bespoke evaluation machinery and improves reproducibility without increasing operational burden.
