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

## Why multiple metrics

Basic Pitch is intentionally instrument-agnostic. Scoring only an exact-program metric would make the production baseline look artificially useless; scoring only flat note F1 would hide the primary value proposition of multi-track AMT.

The harness therefore reports both:

1. **flat note quality** — can the system recover note events at all?
2. **program-family / exact-program note quality** — are those notes assigned to useful source identities?
3. **instrument detection** — does the set of active instruments make sense?

No weighted composite is used. A model cannot hide severe instrument-attribution regressions behind a higher flat note score.

## Operational gate

For every runnable model record:

- immutable code/checkpoint revision
- checkpoint checksum when obtainable
- code license and weight license separately
- CPU/GPU/hardware
- runtime per track
- process high-water RSS / GPU memory where measurable
- install friction and runtime downloads
- failure distribution, not only mean F1

Required CI must stay checkpoint- and dataset-free.

## Evidence Graph V3 compatibility

Issue #336 has now landed a design-only `Evidence<TPayload>` envelope with authoritative version-local locators, explicit maturity, provenance, and separate code/weight licensing. A future multi-track note payload should fit inside that envelope rather than create a parallel persistence concept.

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

1. Acquire a small deterministic Slakh2100-redux test subset externally.
2. Run the exact hello-ai `BasicPitchEngine` and retain raw prediction MIDI plus runtime metadata.
3. Attempt MR-MT3 in an isolated research environment pinned to an immutable checkpoint revision.
4. Score both through the same manifest and metrics.
5. Only then decide whether MT3/YourMT3 need local execution or remain references.

No ADOPT claim for a new multi-track model is made by this harness-only stage.

Part of #337. Parent #327. Schema consumer #336. Product consumer #340.
