# Evaluation artifacts

This directory stores **durable evaluation evidence**, not production runtime code and not a second evaluation framework.

## Ownership boundary

```text
backend/evaluation/
  executable Python evaluators, metrics, dataset/corpus adapters, manifests and engine wrappers

evaluation/
  checked-in result artifacts and focused non-runtime evaluation evidence

docs/ + backend/config/capabilities.json
  synthesized decisions and product exposure policy
```

A successful experiment does not become production behavior merely because its result is checked in here. Product exposure remains governed by the capability registry/current architecture and the relevant accepted decision.

## Result hygiene

Durable result artifacts should identify enough of the protocol to remain interpretable after the producing branch disappears, including as applicable:

- source commit/release;
- evaluator/protocol version;
- engine/model/checkpoint identity;
- dataset/split/fixture identity and provenance;
- metric definition;
- per-piece/failure information where the decision depends on it;
- runtime/resource/license evidence required by the owning gate.

Prefer structured results under `results/<track>/...` as the repository grows. Narrative synthesis belongs in the owning research/decision document rather than duplicated beside every JSON file.

## What not to add here

- Python modules imported by application or evaluator code;
- model weights, private/copyrighted corpus material, credentials or user content;
- a branch-specific Actions workflow preserved only to reproduce one historical run;
- a second copy of current capability maturity/exposure state;
- root-level `FINAL_REPORT` files that look authoritative after later evidence supersedes them.

Historical reports/results may remain as provenance when clearly scoped. Consolidate or archive them when they no longer answer a live question; do not silently rewrite old measured evidence to match a newer conclusion.

See GitHub issue #636 for the canonical evaluation evidence/decision authority. Historical platform/workflow cleanup issues #288 and #557 are closed and should not be treated as active owners.
