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

### OSS-first for frontend primitives

Apply the same ownership discipline to commodity frontend behavior: **own the product; borrow the primitives.**

- Prefer maintained accessible OSS primitives for generic controls and browser interaction mechanics. The default direction is shadcn/ui backed by Base UI, styled with the repository's existing Tailwind/CSS-variable design system.
- Do not hand-roll dropdown/select/combobox, menu, dialog, tooltip, popover, tabs, switch, accordion, drawer/sheet, focus-trap, roving-tabindex, outside-click, or equivalent generic interaction machinery when the standard primitive satisfies the product contract.
- ListenCloser owns product composition, visual language, and music-specific behavior. Score, Piano Roll, musical selection, evidence overlays, cross-representation synchronization, immutable source/version semantics, and music-specific transport/compare behavior may remain bespoke.
- TanStack Query owns remote/server-state cache lifecycle. Do not build a second generic cache, retry, polling, or invalidation framework on top of it without measured justification.
- Prefer generated OpenAPI wire contracts/client plumbing over parallel handwritten transport schemas.
- Do not create new versioned global CSS override strata (for example `*-v7.css` or `*-polish-vN.css`). Extend the owning token/component/style layer instead.
- Before adding substantial bespoke audio-visualization mechanics, evaluate maintained OSS against the exact current product contract; do not adopt or reject a library solely because it exists.

For a new substantial frontend dependency, follow the dependency-policy evidence below and keep library-specific objects behind thin product-facing adapters/wrappers where domain boundaries matter. See ADR 0011 for the accepted frontend ownership boundary.

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

- One active implementation owner per focused responsibility is the default. Additional agents may work concurrently only when the responsibility is explicitly partitioned into independent slices or when they are validating/reviewing rather than creating competing implementation WIP.
- Discovery and evaluation may parallelize more freely when they do not create competing production/integration WIP. Shared semantic authority still serializes even when files are disjoint.
- Before substantial implementation, refresh live pull-request ownership for the focused responsibility and any shared authority it changes. File-level disjointness does not by itself prove semantic independence.
- Do not start new production work merely because an agent is idle. If review, merge integration, or a shared authority seam is saturated, help verify or drain existing WIP instead of spawning another competing implementation.
- Do not impose a repository-wide numeric WIP limit without measured evidence; bounded ownership and explicit independence are the control.
- Multiple production PRs may be non-draft and run CI concurrently when they own bounded, independent changes.
- Prefer small PRs with clear ownership domains. Direct same-file edits are an obvious overlap; shared contracts such as `lib/`, API/state layers, backend runtime/database surfaces, dependency/config files, CI, and cross-cutting tests are broader integration surfaces and should be treated more conservatively.
- Do not reserve broad areas of the repository preemptively. Two leaf UI components, two independent evaluation experiments, or other demonstrably disjoint changes may proceed in parallel.
- Do not rebase, replay, or restart work merely because `main` moved while development or PR CI is in progress. Finish the bounded branch and its relevant evidence first.
- The protected `Build` context is the single merge-facing CI contract. Risk-relevant reusable jobs run inside that gate; agents must not recreate merge admissibility by polling independent workflows.
- `main` requires GitHub's native merge queue. Once a PR's required evidence is green, enqueue it and let GitHub own merge order, current-base validation, and `merge_group` revalidation against preceding queued changes.
- Do not manually merge/rebase current `main` into an otherwise-ready PR solely because another PR landed. A queued PR may be automatically revalidated or requeued; intervene only when GitHub reports a real conflict, failed required check, or semantic incompatibility that needs code changes.
- Never use admin bypass, direct protected-branch pushes, or a custom merge bot to skip the queue for routine work.
- Worktree isolation and overlap discovery remain useful for local Git safety; they are not a second merge scheduler.
- Never add an Actions workflow that merges or updates PRs using only the repository `GITHUB_TOKEN`: workflow-created updates require approval-gated CI, and workflow-created merges suppress normal push-triggered workflows. Use GitHub's native merge queue rather than inventing another coordinator.
- Use the smallest evidence tier that proves the diff. Real-stack E2E is required for critical cross-boundary product/runtime changes, not automatically for static docs, dead-code deletion, or tooling-only edits whose behavior is already covered by build/typecheck/unit/browser checks.
- A heavyweight optional check may continue after a low-risk PR merges when the required and risk-relevant gates already prove the change; never skip a check that is required by repository rules or materially relevant to the changed behavior.
