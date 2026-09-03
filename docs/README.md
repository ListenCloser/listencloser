# Documentation map and authority

Listen Closer has product, architecture, research, evaluation, operational, and historical documentation produced by many parallel development threads. This page is the routing map for those sources; it does not own the facts behind them.

There is intentionally no universal specification. Each durable fact has one authority, and volatile execution state stays in the system that owns it.

## Authority by question

| Question | Authority |
| --- | --- |
| What engineering rules must an agent follow? | root [`AGENTS.md`](../AGENTS.md) |
| What code/config is shipped on `main`? | runtime code, migrations, dependency manifests, deployment config |
| What analysis capability may the product expose? | `backend/config/capabilities.json` + its policy/tests |
| What architecture is currently shipped? | [`ARCHITECTURE.md`](ARCHITECTURE.md), verified against code |
| What accepted architecture decision constrains future changes? | relevant accepted ADR in [`adr/`](adr/) |
| What is Listen Closer, who is it for, and what durable product principles constrain it? | [`product/PRODUCT.md`](product/PRODUCT.md) |
| What product bets / portfolio posture are current? | [`product/ROADMAP.md`](product/ROADMAP.md) |
| What technical simplification / rearchitecture work is currently sequenced where? | [GitHub #634](https://github.com/ListenCloser/listencloser/issues/634) |
| What agent/work-control authority migration is current? | [GitHub #1139](https://github.com/ListenCloser/listencloser/issues/1139) |
| How should an evaluation be designed? | [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md) |
| What did current evaluation tracks conclude? | [`EVALUATION_DECISIONS.md`](EVALUATION_DECISIONS.md) + owning result/report |
| What evidence is sufficient for a downstream claim? | [`evaluation/evidence-sufficiency.md`](evaluation/evidence-sufficiency.md) + executable claim-sufficiency contract |
| Why was an architectural choice made? | relevant ADR in [`adr/`](adr/) |
| How is production operated or verified? | [`OPS.md`](OPS.md) + deployment workflows/config |
| How are production traces, metrics, and initial SLO formulas defined? | [`OBSERVABILITY.md`](OBSERVABILITY.md) + [`observability_contract.json`](observability_contract.json) |
| How do we recover from a production failure? | [`RECOVERY.md`](RECOVERY.md) + the relevant operational/deployment contract |
| What implementation is active right now? | live GitHub issues, pull requests, checks, and merge state — not a copied Markdown inventory |

For production claims, the deployed release SHA and live configuration matter. A document describing intended `main` behavior cannot prove what is currently deployed.

`product/PRODUCT.md` owns durable product constitution; `product/ROADMAP.md` owns current product portfolio/posture/sequencing; #634 owns technical simplification/rearchitecture sequencing; #1139 owns the bounded agent/work-control authority migration. Historical #458 preserves product-strategy rationale but no longer authorizes current work or defines portfolio posture. Live focused issues, pull requests, checks, and merge state own active execution.

## Minimal read paths

### Normal implementation

1. root [`AGENTS.md`](../AGENTS.md);
2. this documentation map;
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) for current boundaries;
4. the focused issue plus relevant ADR/code;
5. `backend/config/capabilities.json` when analysis/product exposure changes.

Do not read a broad roadmap or historical program merely because it mentions the subsystem. Start with the focused responsibility and follow only its canonical dependency/context references.

### Architecture or cross-cutting refactor

1. [`ARCHITECTURE.md`](ARCHITECTURE.md) for the shipped C4-style views;
2. relevant accepted ADRs;
3. actual dependency/schema/runtime contracts in code;
4. the focused issue for an unresolved target change.

A future-looking issue or research note is a hypothesis until an accepted decision owns it. Do not maintain a second target-architecture mega-document alongside ADRs and focused decisions.

The architecture diagrams are deliberately not exhaustive code maps. Human-authored Mermaid views describe stable intended boundaries; import graphs and database relationships that can be derived from code/schema are generated mechanically rather than redrawn by hand. See [`adr/0013-architecture-docs-as-code.md`](adr/0013-architecture-docs-as-code.md), [`generated/frontend-dependencies.md`](generated/frontend-dependencies.md), and [`generated/database/README.md`](generated/database/README.md).

### Product / UX

Read [`product/PRODUCT.md`](product/PRODUCT.md) for durable product identity, target circumstances, JTBD, strategic arena, mental model, and product principles. Read [`product/ROADMAP.md`](product/ROADMAP.md) only when current portfolio posture, gates, or product sequencing are relevant, then read the focused product issue for bounded scope. Root [`DESIGN.md`](../DESIGN.md) owns concrete visual/product-UI guidance; focused UX issues own bounded interaction decisions until durable rules are incorporated into their canonical product/design authority.

### Evaluation / research

1. [`EVALUATION_METHODOLOGY.md`](EVALUATION_METHODOLOGY.md) for the decision protocol;
2. [`EVALUATION_DECISIONS.md`](EVALUATION_DECISIONS.md) to avoid reopening settled evaluation questions;
3. [`evaluation/evidence-sufficiency.md`](evaluation/evidence-sufficiency.md) when the question is whether evidence is strong enough for a downstream claim;
4. the owning evaluation result/report and machine-readable artifacts;
5. relevant production adapters/config when evaluating a production-shaped contract;
6. only the focused product context needed to explain which customer claim the evaluation is meant to support.

A runnable harness is not itself a benchmark result. Once a necessary harness exists, prefer a legitimate result-bearing run over another abstraction/refactor.

Discovery references under [`research/`](research/) help find candidate techniques, datasets, and upstream work. They are not implementation or adoption authority; verify current upstream status/license and use the evaluation protocol when a concrete decision reopens.

### Production operations

Read [`OPS.md`](OPS.md) for normal operation/release procedures, [`OBSERVABILITY.md`](OBSERVABILITY.md) for trace/metric/SLO semantics, and [`RECOVERY.md`](RECOVERY.md) for failure recovery, then verify the deployed release identity and live configuration. Historical deployment prose is not runtime evidence.

## Architecture documentation convention

Architecture docs use a small OSS-first docs-as-code convention:

- **C4 vocabulary** for system context, logical containers, deployment, and dynamic flows;
- **Mermaid** as the default human-authored diagram source because it is text-native and rendered by GitHub;
- **ADRs** for rationale and revisit conditions behind durable architecture decisions;
- **generated views** for facts derived from imports or the PostgreSQL schema rather than hand-maintained copies.

The live generated-truth contracts are dependency-cruiser for TypeScript/JavaScript imports, Import Linter/Grimp for Python import boundaries, and tbls for the PostgreSQL/Supabase application schema. Their generated views and checks are part of required CI. deptry has been characterized for shipped Python dependency declarations, but its permanent manifest cleanup/gate remains a follow-up after repository dependency ownership is stable.

Do not add a binary architecture image or a second diagram DSL when Mermaid expresses the same maintained view adequately. If repeated Mermaid diagrams eventually duplicate one architecture model enough to cause drift, evaluate Structurizr DSL as the single model rather than layering on another independent diagram source.

## Precedence by fact type

When sources disagree, resolve the disagreement according to the kind of fact instead of treating one long document as globally authoritative:

1. **Shipped/deployed behavior:** executable code/config/migrations and current deployed-release evidence.
2. **Analysis exposure/truthfulness:** the capability registry and policy tests.
3. **Accepted architecture decisions:** the newest applicable accepted ADR.
4. **Engineering/agent process:** root `AGENTS.md`.
5. **Durable product constitution:** `product/PRODUCT.md`.
6. **Current roadmap/portfolio:** `product/ROADMAP.md`.
7. **Technical simplification/rearchitecture sequencing:** #634.
8. **Agent/work-control governance migration:** #1139.
9. **Focused execution scope/acceptance:** the focused issue body; comments are evidence/history unless incorporated into current authority.
10. **Active execution state:** live issues, pull requests, checks, and merge state.

Do not use a future-looking plan to claim a capability is implemented. Do not use stale runtime prose to veto a newer accepted decision.

## Document classes

### Canonical / maintained

- `../AGENTS.md` — engineering guardrails and autonomous-agent contract.
- `product/PRODUCT.md` — durable product constitution: identity, target circumstances, JTBD, strategic arena, mental model, and product principles.
- `product/ROADMAP.md` — current product portfolio posture, gates, horizons, and decision-relevant sequencing.
- `ARCHITECTURE.md` — current runtime architecture and canonical architecture views.
- `EVALUATION_METHODOLOGY.md` — reusable evaluation decision protocol.
- `EVALUATION_DECISIONS.md` — cross-track evaluation decision ledger.
- `evaluation/evidence-sufficiency.md` — evidence-readiness/abstention semantics paired with the executable claim contract.
- `OPS.md` — normal operations/release procedures.
- `OBSERVABILITY.md` + `observability_contract.json` — production trace/metric semantics, bounded initial SLO formulas, and baseline requirements.
- `RECOVERY.md` — production recovery procedure and failure-handling contract.
- `analysis/` — maintained analysis/evidence domain contracts whose semantics outlive one implementation plan.
- `design/` — maintained design specializations plus explicitly non-authoritative references; root `DESIGN.md` remains the broad visual/product UI contract.
- `adr/` — accepted durable architecture decisions.
- `generated/` — mechanically derived architecture/schema views; regenerate from their source rather than hand-editing.
- machine-readable registries/contracts in source control.

Current product portfolio posture is repo-owned by `product/ROADMAP.md`. #634 owns technical simplification/rearchitecture sequencing, #1139 owns agent/work-control governance migration, and active execution remains in live focused issues/PR state. Do not duplicate those responsibilities into another maintained Markdown source.

### Research / evaluation evidence

Research discovery references under `research/`, benchmark reports, and experiment results are evidence for a defined question and protocol. They do not become production architecture merely because an experiment succeeded.

Keep durable measured results; retire one-shot workflow scaffolding and stale branch-specific instructions after the result is captured. The methodology document owns reusable protocol rules; the decision ledger owns current cross-track conclusions; detailed measurements stay with the owning result.

### Historical / superseded

Historical prose may remain in the maintained tree only when it carries durable provenance or rationale that is still useful to a contributor. If retained, it must carry an explicit historical/superseded banner and point to the current replacement authority. Otherwise delete it and rely on git/PR history for archaeology.

Historical prose never overrides current code, canonical docs, registry policy, ADRs, or current issue-owned authorities.

## Documentation hygiene rules

When changing docs:

- Prefer linking to an authoritative source over copying volatile values into several files.
- Do not maintain a hand-written list of recent PRs as current-state architecture.
- Put exact dependency versions in manifests/lockfiles, not prose unless the version is itself part of a compatibility decision.
- Put benchmark metrics in the owning evaluation result, not every product overview.
- Put reusable evaluation rules in `EVALUATION_METHODOLOGY.md`; put current decisions in `EVALUATION_DECISIONS.md`.
- Put unresolved work in GitHub issues; close/supersede duplicates instead of growing parallel roadmaps.
- Prefer Mermaid for maintained human diagrams; generate dependency/schema views from their source when possible.
- Do not create an `archive/` or snapshot directory merely to avoid deletion; git/PR history already preserves removed prose.
- If historical prose has continuing provenance value, retain it only with an explicit historical/superseded banner and a pointer to the current authority.
- Delete documentation that has neither current authority nor durable historical/evaluation value.
