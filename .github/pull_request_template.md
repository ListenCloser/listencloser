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

## Verification

Check the applicable evidence tiers and provide concrete results.

- [ ] Unit/component tests
- [ ] Backend/API integration
- [ ] Mocked browser E2E
- [ ] Fresh real-stack E2E
- [ ] Deployed production verification
- [ ] Visual review
- [ ] Algorithm benchmark/evaluation

Include exact commands, counts/metrics, and fixture names where useful.

## Algorithm / evaluation delta

For algorithmic changes, include:
- dataset/corpus + version,
- before/after metrics,
- failure analysis,
- runtime/resource impact,
- known domains not validated.

Otherwise: N/A.

## Truthfulness / provenance

- Are any new claims exposed to users or Ask?
- What source/engine/provenance backs them?
- Are confidence values calibrated? If not, are they `null`/explicitly uncalibrated?
- Are unsupported/withheld/failure states handled honestly?

## Deployment / configuration impact

List new environment variables, dependencies, migrations, model/checkpoint requirements, or deployment changes. Confirm configuration reaches the actual runtime/container where applicable.

## Merge policy

- [ ] Merge automatically when green

Check this only for a production merge-intended PR. The repository merge coordinator will re-check the current `main` at merge time: disjoint leaf work may merge without a redundant rebase, while overlapping/shared integration surfaces are refreshed automatically and re-run through CI.

Leave it unchecked for research, design/reference, experiment, or intentionally held PRs.

## Remaining limitations / rollback

What remains imperfect, and how can this change be disabled or rolled back if needed?
