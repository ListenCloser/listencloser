# Documentation map and authority

Listen Closer has accumulated product, architecture, research, evaluation, operational, and historical documents through many parallel development threads. This page defines which source answers which question so contributors do not accidentally treat the longest or newest-looking Markdown file as universal truth.

## Authority by question

There is intentionally no single document that owns every kind of fact.

| Question | Authority |
| --- | --- |
| What engineering rules must an agent follow? | root [`AGENTS.md`](../AGENTS.md) |
| What code/config is shipped on `main`? | runtime code, migrations, dependency manifests, deployment config |
| What analysis capability may the product expose? | `backend/config/capabilities.json` + its policy/tests |
| What architecture is currently shipped? | [`ARCHITECTURE.md`](ARCHITECTURE.md), verified against code |
| How should an evaluation be designed? | [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md) |
| What did current evaluation tracks conclude? | [`EVALUATION_DECISIONS.md`](EVALUATION_DECISIONS.md) + owning result/report |
| What evidence is sufficient for a downstream claim? | [`evaluation/evidence-sufficiency.md`](evaluation/evidence-sufficiency.md) + executable claim-sufficiency contract |
| What product/architecture direction are we moving toward? | [`MASTER_SPEC.md`](MASTER_SPEC.md) + newer accepted ADRs |
| Why was an architectural choice made? | relevant ADR in [`adr/`](adr/) |
| How is production operated or verified? | [`OPS.md`](OPS.md) + deployment workflows/config |
| How are production traces, metrics, and initial SLO formulas defined? | [`OBSERVABILITY.md`](OBSERVABILITY.md) + [`observability_contract.json`](observability_contract.json) |
| How do we recover from a production failure? | [`RECOVERY.md`](RECOVERY.md) + the relevant operational/deployment contract |
| What work remains? | GitHub issues/roadmap issues, not a frozen PR inventory in Markdown |

For production claims, the deployed release SHA and live configuration matter. A document describing intended `main` behavior cannot prove what is currently deployed.

## Minimal read paths

### Normal implementation

1. root `AGENTS.md`;
2. this documentation map;
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) for current boundaries;
4. the relevant issue/ADR/code;
5. capability registry for analysis/product-exposure changes.

### Architecture or cross-cutting refactor

1. [`ARCHITECTURE.md`](ARCHITECTURE.md) for current C4-style views;
2. relevant accepted ADRs;
3. actual dependency/schema contracts in code;
4. [`MASTER_SPEC.md`](MASTER_SPEC.md) only when target/future architecture is relevant.

The architecture diagrams are deliberately not exhaustive code maps. Human-authored Mermaid views describe stable intended boundaries; import graphs and database relationships that can be derived from code/schema are generated mechanically rather than redrawn by hand. See [`adr/0013-architecture-docs-as-code.md`](adr/0013-architecture-docs-as-code.md), [`generated/frontend-dependencies.md`](generated/frontend-dependencies.md), and [`generated/database/README.md`](generated/database/README.md).

### Evaluation / research

1. [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md) for the decision protocol;
2. [`EVALUATION_DECISIONS.md`](EVALUATION_DECISIONS.md) to avoid reopening already-settled questions;
3. [`evaluation/evidence-sufficiency.md`](evaluation/evidence-sufficiency.md) when the question is whether evidence is strong enough for a downstream claim;
4. the owning evaluation result/report and machine-readable artifacts;
5. relevant production adapters/config when evaluating a production-shaped contract;
6. [`MASTER_SPEC.md`](MASTER_SPEC.md) only for the product capability the evaluation is intended to support.

A runnable harness is not itself a benchmark result. Once a necessary harness exists, prefer a legitimate result-bearing run over another abstraction/refactor.

Discovery references under [`research/`](research/) help find candidate techniques, datasets, and upstream work. They are not implementation or adoption authority; verify current upstream status/license and use the evaluation protocol when a concrete decision reopens.

### Production operations

Read [`OPS.md`](OPS.md) for normal operation/release procedures, [`OBSERVABILITY.md`](OBSERVABILITY.md) for trace/metric/SLO semantics, and [`RECOVERY.md`](RECOVERY.md) for failure recovery, then verify the deployed release identity and live configuration. Historical deployment prose is not runtime evidence.

## Architecture documentation convention

Architecture docs use a small OSS-first docs-as-code convention:

- **C4 vocabulary** for system context, logical containers, deployment, and dynamic flows;
- **Mermaid** as the default human-authored diagram source because it is text-native and rendered by GitHub;
- **ADRs** for the rationale and revisit conditions behind durable decisions;
- **generated views** for facts that can be derived from imports or the PostgreSQL schema rather than hand-maintained copies.

The live generated-truth contracts are dependency-cruiser for TypeScript/JavaScript imports, Import Linter/Grimp for Python import boundaries, and tbls for the PostgreSQL/Supabase application schema. Their generated views and checks are part of required CI. deptry has been characterized for shipped Python dependency declarations, but its permanent manifest cleanup/gate remains a follow-up after the repository-identity migration so the canonical lockfile is edited once.

Do not add a binary architecture image or a second diagram DSL when Mermaid expresses the same maintained view adequately. If repeated Mermaid diagrams eventually duplicate one architecture model enough to cause drift, evaluate Structurizr DSL as the single model rather than layering on another independent diagram source.

## Precedence rules

When sources disagree, resolve the disagreement according to the type of claim:

1. **Shipped behavior:** executable code/config/migrations and current deployed-release evidence win.
2. **Analysis exposure/truthfulness:** the capability registry and policy tests win.
3. **Accepted architecture decisions:** a newer accepted ADR may supersede older design prose.
4. **Engineering process:** root `AGENTS.md` wins over duplicated or historical guidance.
5. **Future direction:** `MASTER_SPEC.md` wins over older product-roadmap prose unless a newer accepted decision supersedes it.

Do not use a future-looking spec to claim a capability is implemented. Do not use a stale runtime snapshot to veto a newer accepted product direction.

## Document classes

### Canonical / maintained

- `../AGENTS.md` — engineering guardrails and autonomous-agent contract.
- `ARCHITECTURE.md` — current runtime architecture and canonical architecture views.
- `EVALUATION_METHODOLOGY.md` — reusable evaluation decision protocol.
- `EVALUATION_DECISIONS.md` — cross-track evaluation decision ledger.
- `evaluation/evidence-sufficiency.md` — evidence-readiness/abstention semantics paired with the executable claim contract.
- `MASTER_SPEC.md` — product and target-architecture direction.
- `OPS.md` — normal operations/release procedures.
- `OBSERVABILITY.md` + `observability_contract.json` — production trace/metric semantics, bounded initial SLO formulas, and baseline requirements.
- `RECOVERY.md` — production recovery procedure and failure-handling contract.
- `analysis/` — maintained analysis/evidence domain contracts whose semantics outlive one implementation plan.
- `design/` — maintained design specializations plus explicitly non-authoritative references; root `DESIGN.md` remains the broad visual/product UI contract.
- `adr/` — accepted durable decisions.
- `generated/` — mechanically derived architecture/schema views; regenerate from their source rather than hand-editing.
- machine-readable registries/contracts in source control.

These should be updated when their owned contract changes.

### Research / evaluation evidence

Research discovery references under `research/`, benchmark reports, and experiment results are evidence for a defined question and protocol. They do not become production architecture merely because an experiment succeeded.

Keep durable measured results; retire one-shot workflow scaffolding and stale branch-specific instructions after the result is captured. The methodology document owns reusable protocol rules; the decision ledger owns current cross-track conclusions; detailed measurements stay with the owning result.

### Historical / superseded

Historical prose may remain in the maintained tree only when it carries durable provenance or rationale that is still useful to a contributor. If retained, it must carry an explicit historical/superseded banner and point to the current replacement authority. Otherwise delete it and rely on git/PR history for archaeology.

Historical prose never overrides current code, canonical docs, registry policy, or ADRs.

## Documentation hygiene rules

When changing docs:

- Prefer linking to an authoritative source over copying volatile values into several files.
- Do not maintain a hand-written list of “recent PRs” as current-state architecture.
- Put exact dependency versions in manifests/lockfiles, not prose unless the version is itself part of a compatibility decision.
- Put benchmark metrics in the owning evaluation result, not every product overview.
- Put reusable evaluation rules in `EVALUATION_METHODOLOGY.md`; put current decisions in `EVALUATION_DECISIONS.md`.
- Put unresolved work in GitHub issues; close/supersede duplicates instead of growing parallel roadmaps.
- Prefer Mermaid for maintained human diagrams; generate dependency/schema views from their source when possible.
- Do not create an `archive/` or snapshot directory merely to avoid deletion; git/PR history already preserves removed prose.
- If historical prose has continuing provenance value, retain it only with an explicit historical/superseded banner and a pointer to the current authority.
- Delete documentation that has neither current authority nor durable historical/evaluation value.
