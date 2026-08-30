# Engineering Guardrails for Autonomous Agents

This repository is developed heavily with autonomous coding agents. Treat this file as a contract, not optional guidance.

## 1. Evidence before implementation

- Do not declare a capability working because code exists or unit tests pass.
- Distinguish evidence tiers explicitly:
  1. unit/component tests,
  2. mocked browser E2E,
  3. integration tests,
  4. fresh real-stack E2E,
  5. deployed production verification.
- Mocked E2E proves a frontend contract, not that the backend actually produces that contract.
- A successful backend response does not prove persistence or UI exposure.
- One qualitative fixture does not establish algorithm quality.
- Oracle evaluation does not establish end-to-end product accuracy.
- A "pre-existing failure" must be reproduced on current `main` or otherwise demonstrated, not asserted.

## 2. OSS-first for music/ML algorithms

Before adding substantial custom algorithmic logic, survey credible OSS/research implementations and document why they are unsuitable.

Prefer:
- maintained or stable open-source implementations,
- permissive licenses where possible,
- reproducible pretrained checkpoints,
- CPU-feasible inference for production,
- adapter-based integration so engines remain replaceable.

Custom algorithms are appropriate for product glue, trivial transformations, or where benchmark evidence demonstrates an unmet need. New research algorithms should normally begin under evaluation tooling before becoming production engines.

Do not copy, vendor, or reimplement unlicensed source code.

## 3. Truthfulness rules

- Never fabricate confidence. Use `None` when confidence is not calibrated.
- Do not convert missing evidence into a default musical claim.
- Do not expose a downstream theory claim when its required upstream evidence is untrusted.
- Withhold unvalidated capabilities rather than displaying plausible-looking output.
- `unknown`, `unsupported`, `withheld`, and `failed` are different states; preserve that distinction.
- Global key is not a local key region. A chord is not a cadence. A staff is not a voice. A voice is not automatically a melody.
- `backend/config/capabilities.json` is the machine-readable source of truth for capability maturity and product exposure. Any PR that changes a capability from production/experimental/evaluation-only/withheld, changes its engine, or changes Inspector/annotation/Ask exposure must update that registry and its tests in the same PR.

## 4. Provenance and lineage

Every generated artifact or analysis insight must be traceable to its source.

Where applicable preserve:
- work/version IDs,
- parent artifact/version,
- engine and engine version,
- model/checkpoint or profile,
- relevant parameters,
- source input modality,
- release/commit provenance.

Every temporal insight intended for timeline UI must have valid `start_seconds` / `end_seconds` spans at the persistence/API boundary.

## 5. Architecture boundaries

Keep vendor/library-specific behavior inside adapters. Product/domain code should consume normalized contracts.

Conceptually separate:
- perception/detection from theory interpretation,
- engines from persistence,
- persistence from presentation,
- frontend state from backend implementation details.

Do not create a new abstraction when an existing one can be extended cleanly. Do not preserve dead compatibility paths without evidence that they are still needed.

Avoid large orchestration modules becoming homes for unrelated behavior; coordinators should delegate to typed services/adapters.

## 6. Evaluation lifecycle

Algorithmic capabilities follow this lifecycle:

`DISCOVERY -> EVALUATION -> CANDIDATE -> PRODUCTION -> MONITORED`

A production recommendation requires, where relevant:
- a named dataset/corpus and version,
- reproducible evaluation command,
- machine-readable metrics,
- comparison to the current baseline,
- licensing and model-weight review,
- runtime/memory feasibility,
- product gating/withholding behavior,
- integration/real-stack verification.

Do not tune against the final evaluation set. Keep oracle/component evaluation separate from end-to-end evaluation.

## 7. Testing expectations

Choose the smallest test that proves the behavior, then add higher-level coverage for cross-boundary behavior.

- Pure logic -> unit tests.
- API/persistence boundaries -> integration tests.
- UI contracts -> mocked browser E2E.
- Critical product workflows -> real-stack E2E.
- Algorithm changes -> benchmark/evaluation delta.
- Visual changes -> visual evidence/review where useful.

Do not weaken assertions merely to make CI green. Fix stale selectors/races without removing meaningful product guarantees.

Before pushing a branch, automatically apply deterministic safe fixes instead of waiting for CI to discover them:

- Python changes: `bash scripts/fix.sh python` (Ruff safe fixes + formatting; never `--unsafe-fixes`).
- Frontend changes: `bash scripts/fix.sh frontend` after `npm ci` when ESLint-fixable files changed.
- Mixed changes: `bash scripts/fix.sh all` when both toolchains are already installed.

A format-only or safely fixable lint failure is routine agent work: apply the fixer and push the corrected head immediately. Do not escalate it as a blocker. Type errors, test failures, migrations, benchmark/result failures, generated-contract semantics, and lint requiring unsafe/behavioral edits still require reasoning and remain fail-closed.

## 8. Deployment and operations

- CI/deploy must operate on an explicit commit/release SHA.
- A deployed service should expose enough release metadata to prove which revision is running.
- Configuration added to `.env` is not complete until it reaches the actual container/process.
- New production engines must be verified inside the production-shaped container/runtime, not only a developer shell.
- Health/readiness checks should verify both API and durable worker dependencies where relevant.

## 9. Dependency policy

For substantial new dependencies record:
- purpose,
- license,
- model/data license if applicable,
- maintenance status,
- version strategy,
- runtime/platform compatibility,
- size/memory implications.

Keep test/development dependencies out of runtime dependency sets when practical. Production-critical engine versions should not float unintentionally.

## 10. Pull request standard

Every meaningful PR should explain:
- Problem / user impact
- Root cause
- Approach
- OSS considered (for substantial algorithmic work)
- Deliberate scope exclusions
- Tests and evidence tier
- Evaluation delta for algorithmic changes
- Deployment/configuration impact
- Remaining limitations

Screenshots/videos belong in PR evidence, not committed to the repository unless they are intentional test fixtures.

## 11. Autonomous behavior

Do not stop for routine implementation decisions. Fix bounded issues autonomously, run the relevant gates, inspect failures, and continue until the requested outcome is actually proven.

Escalate only for genuine blockers such as:
- product behavior requiring owner judgment,
- licensing/permission ambiguity that affects shipping,
- destructive migrations or irreversible data operations,
- substantial new paid infrastructure,
- major architecture changes with broad consequences,
- required secrets/credentials unavailable to the agent.

## 12. Parallel work and merge integration

Parallel implementation and validation are the default. Unrelated autonomous agents should not wait for each other merely because another PR is open.

- Multiple production PRs may be non-draft and run CI concurrently when they own bounded, independent changes.
- Prefer small PRs with clear ownership domains. Direct same-file edits are an obvious overlap; shared contracts such as `lib/`, API/state layers, backend runtime/database surfaces, dependency/config files, CI, and cross-cutting tests are broader integration surfaces and should be treated more conservatively.
- Do not reserve broad areas of the repository preemptively. Two leaf UI components, two independent evaluation experiments, or other demonstrably disjoint changes may proceed in parallel.
- Do not rebase or restart work merely because `main` moved while development or CI is in progress. Finish the branch and its relevant evidence first.
- The protected `Build` context remains the merge gate. The repository currently requires an up-to-date base before final merge, so when another PR lands GitHub may require the stale-but-ready branch to refresh and run a final check cycle. Perform that refresh mechanically; it is an integration constraint, not a reason to serialize development beforehand.
- Enable native GitHub auto-merge for ordinary production PRs once their required evidence is green. If GitHub invalidates the required check after `main` advances, update the branch and let the checks rerun; do not ask another agent to stop unrelated work.
- Never add an Actions workflow that merges or updates PRs using only the repository `GITHUB_TOKEN`: workflow-created updates require approval-gated CI, and workflow-created merges suppress normal push-triggered workflows. A future automated merge coordinator must use a dedicated GitHub App/PAT or GitHub's native merge queue and must preserve production deploy/smoke triggers.
- Use the smallest evidence tier that proves the diff. Real-stack E2E is required for critical cross-boundary product/runtime changes, not automatically for static docs, dead-code deletion, or tooling-only edits whose behavior is already covered by build/typecheck/unit/browser checks.
- A heavyweight optional check may continue after a low-risk PR merges when the required and risk-relevant gates already prove the change; never skip a check that is required by branch protection or materially relevant to the changed behavior.
