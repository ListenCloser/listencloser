# Agent documentation entry point

The canonical engineering and autonomous-agent contract is the repository-root [`AGENTS.md`](../AGENTS.md). This file is intentionally a small navigation aid; it must not grow into a second copy of process, testing, merge, or safety rules.

Read [`README.md`](README.md) for the documentation authority map.

## Normal implementation read path

1. root `AGENTS.md` — mandatory engineering/agent rules;
2. `docs/README.md` — which document owns which kind of fact;
3. `docs/ARCHITECTURE.md` — current shipped runtime boundaries;
4. relevant GitHub issue and ADR;
5. relevant code/tests;
6. `backend/config/capabilities.json` for analysis maturity/exposure changes.

Add `MASTER_SPEC.md` for product or target-architecture direction, research/evaluation docs for music-engine work, and `OPS.md` for deployment/production operations.

## Source-of-truth rule

Do not infer authority from file age, length, a `V2`/`V3` suffix, or the phrase “source of truth” inside an older document. For shipped behavior, code/config/migrations and deployed-release evidence win. For analysis exposure, the capability registry wins. For engineering process, root `AGENTS.md` wins. For future product direction, `MASTER_SPEC.md` and newer accepted decisions apply.

Historical audit/roadmap/design documents may explain how the repository arrived here, but they are not implementation instructions unless the documentation map explicitly says otherwise.
