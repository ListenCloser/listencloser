# Analysis V3E report — generic multi-instrument transcription

**Status:** harness/reference stage; no new multi-track checkpoint has been run locally in this PR yet.

## Decision being tested

Does hello-ai gain enough product value from an optional multi-instrument AMT path to justify carrying a second symbolic transcription engine beyond the existing Basic Pitch / Transkun routing?

The relevant product value is not "more MIDI." It is reliable **instrument-aware** evidence for piano-roll/score grouping, bass-line analysis, harmony by source, melody/vocal analysis, arrangement understanding, and cross-representation comparison.

## Current reference assessment

| candidate | role | code license | weight license | current decision |
| --- | --- | --- | --- | --- |
| hello-ai Basic Pitch | production flat-note baseline | Apache-2.0 | Apache-2.0 per upstream metadata | ADOPT (existing baseline) |
| Magenta MT3 | legacy research baseline | Apache-2.0 | unresolved for externally hosted multi-instrument checkpoint | REVISIT |
| YourMT3+ | quality/reference candidate | GPL-3.0 official GitHub repo | Apache-2.0 checkpoint-repo metadata | RESEARCH |
| MR-MT3 | preferred newer practical candidate | MIT | MIT checkpoint-repo metadata | RESEARCH |

MuScriptor is tracked as a useful 2026 research reference but is not the permissive production-candidate slot because its released weights are CC BY-NC 4.0.

## Dataset contract

Use **Slakh2100-redux** (CC BY 4.0), preferably the official test split or a deterministic subset. The corpus is large (~104 GB compressed), so acquisition remains external/manual.

For each track, ground truth is assembled from `MIDI/SXX.mid`. Slakh's own utilities document that these per-source MIDI files are the exact MIDI used to synthesize each stem, while `all_src.mid` can differ after instrument-specific rendering heuristics. The redux release is preferred because the original release had replicated MIDI that could leak across splits.

The decisive benchmark therefore does not substitute the repository's existing BabySlakh/Slakh `all_src.mid` adapters for the per-source protocol. BabySlakh can be used only as a clearly labeled exploratory smoke corpus.

## Metric contract

Basic Pitch is intentionally instrument-agnostic. Scoring only an exact-program metric would make the production baseline look artificially useless; scoring only flat note F1 would hide the primary value proposition of multi-track AMT.

The harness reports complementary metrics with **no weighted composite**:

1. flat onset F1
2. flat onset+offset note F1
3. GM-family onset F1
4. exact-program onset F1
5. exact-program onset+offset F1
6. exact-program and GM-family instrument-detection F1
7. per-program/per-family onset breakdowns for failure analysis

Canonical note matching uses `mir_eval 0.8.2` maximum bipartite assignment, not a bespoke greedy matcher:

- onset tolerance: 50 ms
- pitch tolerance: 50 cents
- offset-aware metric: `max(50 ms, 20% of reference-note duration)`
- drums: explicit reserved label `128`

The maximum-matching behavior has a deterministic regression test, so candidate scores cannot depend on prediction ordering. A model cannot hide severe instrument-attribution regressions behind a higher flat note score.

## Reproducibility and operational gate

Every runnable model record requires:

- hello-ai measurement SHA
- immutable code/checkpoint revision
- checkpoint checksum when obtainable
- code license and weight license separately
- exact dataset-manifest path + SHA-256
- CPU/GPU/hardware/environment
- runtime per track
- process high-water RSS / GPU memory where measurable
- raw prediction MIDI paths
- install friction and runtime downloads
- per-piece and per-instrument failure distribution, not only mean F1

Before scoring, the evaluator verifies the model-run manifest SHA-256 against the actual manifest and fails closed on mismatches, unknown IDs, duplicate IDs, or missing prediction/reference files.

Required CI stays checkpoint- and dataset-free.

## Verified harness result

The final measurement/code head for the harness is:

`7057c1c247fb2770fee5f5e418479cbf69bd4619`

It was rebuilt on then-current `main` (`399ad131563e7741fe12019cc749f5e82e3ba451`) after the base advanced, yielding exactly one feature commit ahead and zero behind with only 12 evaluation/test files changed.

On that exact head:

- frontend lint: pass
- frontend typecheck: pass
- Ruff check + format: pass (`239 files already formatted`)
- generated API contract: pass
- **17/17 new multi-track evaluator/provenance tests: pass**
- required Python suite: **756 passed, 13 skipped, 37 deselected**
- Build: pass
- E2E: pass
- CodeQL: pass
- Dependency Review: pass
- Gitleaks: pass

At the time this report was finalized, Backend Image and Real-stack E2E were still running; they do not exercise a production change from this PR, but their final status should still be checked before any merge-readiness decision.

This is a validation of the **benchmark harness**, not evidence that MR-MT3 or another new multi-track engine should be adopted.

## Evidence Graph V3 compatibility

Issue #336 has landed a design-only `Evidence<TPayload>` envelope with authoritative version-local locators, explicit maturity, provenance, and separate code/weight licensing. A future multi-track note payload should fit inside that envelope rather than create a parallel persistence concept.

#337 exposes one trust-semantics question that #336 should resolve before productionization: an evaluated task-specific neural detector can emit useful localized note events without providing a calibrated probability. That output should **not** be mislabeled `confidence`, but it also does not fit cleanly under `heuristic_candidate`. The architecture should either clarify that `measured` includes evaluated detector outputs or add an explicit task-model estimate class. This PR leaves `trustClass` unset rather than inventing semantics.

## Proposed evidence contract

Schema ownership remains #336. Conceptually, the payload should be wrapped by the canonical evidence envelope:

```ts
type MultiTrackNotePayload = {
  tracks: Array<{
    program?: number
    programFamily?: string
    isDrum: boolean
    notes: Array<{
      pitch: number
      startSeconds: number
      endSeconds: number
      velocity?: number
    }>
  }>
}

type MultiTrackNoteEvidence = Evidence<MultiTrackNotePayload>
// kind: "multitrack_notes"
// sourceVersionIds + authoritative locator come from the Evidence envelope
// maturity + code/weight/checkpoint provenance come from canonical #336 fields
```

This is evidence attached to a Work/version, not the universal substrate for all analysis.

## Next measured step

1. Acquire a small deterministic **per-source Slakh2100-redux** test subset externally.
2. Run the exact hello-ai `BasicPitchEngine` and retain raw prediction MIDI plus runtime/RSS/provenance metadata.
3. Run MR-MT3 in an isolated research environment pinned to an immutable checkpoint revision/checksum. A modern wrapper may be used only as the runner if it preserves the same underlying checkpoint and its own revision is recorded.
4. Score both through this exact manifest/metric contract.
5. Inspect macro results together with per-piece/per-program failure distributions and operational cost.
6. Only then decide whether a new multi-track path is ADOPT / RESEARCH / REJECT / REVISIT and whether MT3/YourMT3 need local execution.

No ADOPT claim for a new multi-track model is made by this harness-only stage.

Part of #337. Parent #327. Schema consumer #336. Product consumer #340.
