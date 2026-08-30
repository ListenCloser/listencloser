# Documentation map and authority

hello-ai has accumulated product, architecture, research, evaluation, operational, and historical documents through many parallel development threads. This page defines which source answers which question so contributors do not accidentally treat the longest or newest-looking Markdown file as universal truth.

## Authority by question

There is intentionally no single document that owns every kind of fact.

| Question | Authority |
|---|---|
| What engineering rules must an agent follow? | root [`AGENTS.md`](../AGENTS.md) |
| What code/config is shipped on `main`? | runtime code, migrations, dependency manifests, deployment config |
| What analysis capability may the product expose? | `backend/config/capabilities.json` + its policy/tests |
| What architecture is currently shipped? | [`ARCHITECTURE.md`](ARCHITECTURE.md), verified against code |
| What product/architecture direction are we moving toward? | [`MASTER_SPEC.md`](MASTER_SPEC.md) + newer accepted ADRs |
| Why was an architectural choice made? | relevant ADR in `adr/` |
| How is production operated or verified? | [`OPS.md`](OPS.md) + deployment workflows/config |
| What did an evaluation conclude? | the durable result/report for that exact protocol |
| What work remains? | GitHub issues/roadmap issues, not a frozen PR inventory in Markdown |

For production claims, the deployed release SHA and live configuration matter. A document describing intended `main` behavior cannot prove what is currently deployed.

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
- `ARCHITECTURE.md` — current runtime architecture.
- `MASTER_SPEC.md` — product and target-architecture direction.
- `OPS.md` — operations/release procedures.
- `adr/` — accepted durable decisions.
- machine-readable registries/contracts in source control.

These should be updated when their owned contract changes.

### Operational snapshots

Files such as `CURRENT_STATE.md` are orientation aids. They should summarize stable current invariants and point to machine-readable/runtime authorities rather than duplicate engine versions, benchmark numbers, or recent PR inventories that rapidly go stale.

### Research / evaluation evidence

Research landscape, evaluation decisions, benchmark reports, and experiment results are evidence for a defined question and protocol. They do not become production architecture merely because an experiment succeeded.

Keep durable measured results; retire one-shot workflow scaffolding and stale branch-specific instructions after the result is captured.

### Historical / superseded

Audit documents, old product visions, old roadmaps, deployment experiments, and superseded design notes may be useful provenance. They must carry an explicit historical/superseded banner if retained. Historical prose never overrides current code, canonical docs, registry policy, or ADRs.

## Documentation hygiene rules

When changing docs:

- Prefer linking to an authoritative source over copying volatile values into several files.
- Do not maintain a hand-written list of “recent PRs” as current-state architecture.
- Put exact dependency versions in manifests/lockfiles, not prose unless the version is itself part of a compatibility decision.
- Put benchmark metrics in the owning evaluation result, not every product overview.
- Put unresolved work in GitHub issues; close/supersede duplicates instead of growing parallel roadmaps.
- If a file is no longer authoritative but has useful history, label it historical or move it under an archive boundary rather than quietly leaving contradictory instructions.
- Delete documentation that has neither current authority nor durable historical/evaluation value.

## Minimal read paths

For a normal implementation task:

1. root `AGENTS.md`;
2. this documentation map;
3. `ARCHITECTURE.md` for current boundaries;
4. the relevant issue/ADR/code;
5. capability registry for analysis/product-exposure changes.

For product/research direction, add `MASTER_SPEC.md` and the relevant evaluation/research documents. For production operations, add `OPS.md` and verify the deployed release.
