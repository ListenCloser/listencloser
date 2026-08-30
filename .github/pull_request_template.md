## Problem / user impact

What is broken, missing, misleading, or unnecessarily complex?

## Root cause

What evidence shows the underlying cause rather than only the symptom?

## Approach

What changed and why is this the smallest clean solution?

## OSS / existing solutions considered

Required for substantial algorithmic/domain logic. If not applicable, say why.

## Deliberately out of scope

What did this PR intentionally not change?

## Integration metadata

- **Kind:** production / evaluation / refactor / docs-research / control-plane
- **Depends on:** none or PR/issue number
- **Supersedes:** none or PR number; close the superseded PR promptly
- **Known overlap:** none or the overlapping files/contracts + coordination plan
- **Shared contracts/control-plane touched:** none or list API/schema/state/provenance/capability/CI/deploy surfaces

PRs are mergeable integration units, not permanent coordination documents. Put living direction in issues/docs. For stacked work, describe only the child delta relative to the declared parent.

## Parallelism / ownership

What files, contracts, or product domain does this PR own? Note any known overlap with another open PR. Independent work should remain non-draft and validate concurrently rather than waiting for unrelated PRs.

Before opening a competing implementation, search the open PR/issue set for the same problem, files, or shared contract and reconcile material overlap.

## Verification

Check the applicable evidence tiers and provide concrete results.

- [ ] Unit/component tests
- [ ] Backend/API integration
- [ ] Mocked browser E2E
- [ ] Fresh real-stack E2E
- [ ] Deployed production verification
- [ ] Visual review
- [ ] Algorithm benchmark/evaluation
- [ ] Evidence artifacts explicitly fail if missing/empty

Include exact commands, counts/metrics, and fixture names where useful. If this PR changes CI/merge/deploy enforcement, explain how the change was also checked against the previously protected policy on `main` or by an independent owner/ruleset.

## Algorithm / evaluation delta

For algorithmic changes, include:
- dataset/corpus + version,
- before/after metrics,
- failure analysis,
- runtime/resource impact,
- known domains not validated,
- whether the score follows the actual production path or an explicitly labeled oracle/ceiling path,
- standard metric/protocol used; justify any bespoke scorer.

Otherwise: N/A.

## Truthfulness / provenance

- Are any new claims exposed to users or Ask?
- What source/engine/provenance backs them?
- Are confidence values calibrated? If not, are they `null`/explicitly uncalibrated?
- Are unsupported/withheld/failure states handled honestly?

## Deployment / configuration impact

List new environment variables, dependencies, migrations, model/checkpoint requirements, or deployment changes. Confirm configuration reaches the actual runtime/container where applicable.

For dependency updates, call out major framework/language/runtime/toolchain migrations explicitly; do not hide them inside a routine rollup.

## Remaining limitations / rollback

What remains imperfect, and how can this change be disabled or rolled back if needed?
