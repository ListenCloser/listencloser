# Analysis V3E report — generic multi-instrument transcription

**Status:** measured small-subset stage. No production integration.

## Decision

**Keep Basic Pitch as the production baseline for now. Keep MR-MT3 at `RESEARCH` as a leading optional multi-instrument evidence path; do not adopt it yet.**

The decisive finding is two-part:

1. MR-MT3's **decoded model events** materially outperform the production Basic Pitch baseline on this five-excerpt Slakh2100-redux subset.
2. The pinned `mt3-infer 0.2.0` stock MIDI serializer corrupts that evidence by collapsing all pitched programs onto one channel, so stock-CLI MIDI scores dramatically understate MR-MT3 quality.

Candidate decisions:

| candidate | decision | reason |
| --- | --- | --- |
| hello-ai Basic Pitch | **ADOPT (existing baseline)** | deployed, fast after cold start, simple flat-note evidence; no instrument attribution |
| MR-MT3 | **RESEARCH** | strong decoder-level onset/program evidence on this small subset, but sample too small, duration/program-note quality weaker, and current CPU wrapper is operationally poor |
| Magenta MT3 | **REVISIT** | Apache-2.0 code, but legacy T5X/JAX stack and external checkpoint-license ambiguity add friction |
| YourMT3+ | **RESEARCH reference** | quality/reference candidate, but official code is GPL-3.0 |
| MuScriptor | **research reference only** | released weights are CC BY-NC 4.0 |

No candidate changes production routing in this PR.

## Measured protocol

Dataset: **Slakh2100-redux**, test split, CC BY 4.0.

Fixed subset: `Track01876`, `Track01877`, `Track01878`, `Track01880`, `Track01881`, first 30 seconds of each. Ground truth is active per-source `MIDI/SXX.mid` marked `midi_saved: true`, not `all_src.mid`.

The run used a selective Hugging Face acquisition mirror pinned to immutable revision `bb320faf307f5d24aeced0e60f9445ff0abce205`. Upstream identity/license remain Zenodo 4599666 / CC BY 4.0. Cropped mixes and reference MIDIs are SHA-256 recorded in `results/slakh_redux_subset_results.json`.

Hello-ai measurement SHA: `7057c1c247fb2770fee5f5e418479cbf69bd4619`.

MR-MT3 provenance:

- `mt3-infer 0.2.0`
- runner revision `2d20ee5bb6ca727968bd23c6100fd2a35154166b`
- CPU `torch 2.6.0+cpu` in an isolated environment
- checkpoint SHA-256 `b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f`
- checkpoint bytes `183672643`
- code license MIT
- weight repository metadata MIT

The production hello-ai environment remained independently pinned during candidate execution.

## Metrics

Canonical note matching uses `mir_eval 0.8.2` maximum bipartite assignment:

- onset tolerance: 50 ms
- pitch tolerance: 50 cents
- offset tolerance: `max(50 ms, 20% of reference-note duration)`
- drums: reserved label `128`

No weighted composite is used.

### Canonical macro result

MR-MT3 values below come from decoded `NoteSequence` events captured **before MIDI serialization**.

| metric | Basic Pitch | MR-MT3 decoder evidence |
| --- | ---: | ---: |
| flat onset F1 | 0.3871 | **0.7898** |
| flat onset+offset F1 | 0.1397 | **0.2415** |
| GM-family onset F1 | N/A | **0.7550** |
| exact-program onset F1 | N/A | **0.4999** |
| exact-program onset+offset F1 | N/A | 0.1211 |
| exact-program detection F1 | N/A | 0.3875 |
| GM-family detection F1 | N/A | **0.9113** |

Basic Pitch has no program/drum attribution. Default MIDI program values are not interpreted as evidence.

### Flat onset F1 by excerpt

| track | Basic Pitch | MR-MT3 decoder |
| --- | ---: | ---: |
| Track01876 | 0.2988 | **0.6804** |
| Track01877 | 0.6883 | **0.9582** |
| Track01878 | 0.2701 | **0.7603** |
| Track01880 | 0.2363 | **0.6700** |
| Track01881 | 0.4419 | **0.8801** |

MR-MT3 wins flat onset F1 on all five excerpts at the decoder boundary. That is a much stronger and more consistent signal than the stock serialized MIDI suggested.

### MR-MT3 instrument-aware result by excerpt

| track | GM-family onset F1 | exact-program onset F1 | exact-program note F1 | family detection F1 |
| --- | ---: | ---: | ---: | ---: |
| Track01876 | 0.6068 | 0.3741 | 0.1473 | 1.0000 |
| Track01877 | 0.9582 | 0.8517 | 0.2890 | 0.8000 |
| Track01878 | 0.7397 | 0.3288 | 0.0411 | 0.8333 |
| Track01880 | 0.6042 | 0.4996 | 0.0489 | 0.9231 |
| Track01881 | 0.8663 | 0.4452 | 0.0794 | 1.0000 |

Interpretation: broad-family and program-attributed **onset** evidence is promising. Exact program-attributed note-with-offset F1 remains much weaker, so this does not justify a trusted instrument-aware notation path yet.

## Upstream serializer validity finding

Pinned `mt3-infer 0.2.0` decodes MR-MT3 token streams into a `NoteSequence` containing `Note.program` and `is_drum`. Its final `mido.MidiFile` serializer then:

- emits every pitched note on channel 0;
- emits no `program_change` messages;
- reserves only channel 9 for drums.

This does not merely erase instrument labels. Overlapping same-pitch notes from different decoded programs become ambiguous on the same MIDI channel, so downstream MIDI parsing can merge/truncate note identities and corrupt even instrument-agnostic onset/offset evidence.

### Diagnostic stock serializer

Stock workflow run `33213511319`, head `4f380d51fa74e67e9c67bb8e5952a749083621f5`:

- onset F1 `0.3366`
- onset+offset F1 `0.0905`
- family onset F1 `0.2561`
- exact-program onset F1 `0.2091`

These values describe the **wrapper's MIDI artifact**, not canonical MR-MT3 model quality.

### Intermediate program-channel patch

A throwaway run changed only final MIDI channel/program serialization. It proved that program information exists in the decoder and improved detection, but still forced decoded notes through MIDI channel semantics. It is retained as diagnostic provenance, not the canonical measurement.

Patched workflow run `33215520514`, head `cf100d2dd1338dbe3819994fa9a695d63bd79320`:

- onset F1 `0.3366`
- onset+offset F1 `0.0977`
- family onset F1 `0.3147`
- exact-program onset F1 `0.2286`

### Decoder-sidecar calibration — canonical

A final controlled run instrumented the pinned adapter immediately after `decode_and_combine_predictions` and before stock MIDI serialization. It writes only a JSON sidecar containing each decoded pitch, start/end time, velocity, program, drum flag, and decoder invalid/dropped counts; the stock serializer itself is left unchanged.

Provenance:

- workflow run `33218294887`
- head `edfc29a01334db61ceaf6d7dfcde0080cbfd185b`
- artifact SHA-256 `484581f59d444cfbbc1333da128f8ecb663aa4d0bc0d819a64b72ce8d0818dc8`
- adapter SHA-256 before instrumentation `5b376389c1f1794862b2704237cd01e20b1c2c32f474a429cf52afd20b2122ef`
- instrumented adapter SHA-256 `c395b4895e4f4da721c6494beb289962f787d19c443b76ef07dead4e0634d1fd`
- stock MIDI serializer unchanged

The locked hello-ai environment serialized sidecar events into one stream per decoded program solely for the frozen scorer. Independent verification found:

- decoded/persisted note counts are one-to-one on every track;
- pitch/program/drum identity is one-to-one;
- maximum sidecar→evaluator-MIDI start/end quantization is ~1.1 ms, well below the 50 ms tolerance.

Therefore the decoder-sidecar result is the canonical MR-MT3 model-quality evidence for this PR.

## Operational result

Basic Pitch on GitHub CPU:

- first excerpt ~25 s including cold/model-load cost;
- remaining excerpts ~1.5–1.8 s each.

MR-MT3 through the stock process-per-track CLI:

- roughly 26–155 s per excerpt;
- ~817–863 MB RSS;
- checkpoint prefetch separated from per-track wall time in the controlled runs.

This is wrapper execution cost, not a warm/batched model latency claim. A persistent service could be substantially different, but that must be measured rather than assumed.

## Product/architecture interpretation

The corrected evidence changes the product hypothesis:

- Basic Pitch remains the production default because it is already integrated and operationally cheap after load.
- MR-MT3 is now a **leading research candidate** for optional instrument-aware symbolic evidence; it is not merely a tagging aid.
- Decoder-level onset/program evidence may be useful for arrangement, instrument-aware piano roll, bass/melody extraction, comparison, and selective downstream analysis.
- Weak exact-program duration quality still cautions against treating its output as authoritative notation.
- A production adapter must consume/persist decoded events losslessly; the current stock `mt3-infer` MIDI output is unsuitable.
- Symbolic transcription remains one evidence family, not the universal substrate.

Proposed payload remains under the #336 evidence envelope:

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
```

An evaluated neural detector without calibrated probabilities must not invent `confidence`.

## Limitations / promotion gate

No new engine is adopted because:

- only five fixed 30-second Slakh excerpts were scored;
- synthetic-mixture performance may not generalize to recorded/produced music;
- published MR-MT3 scores use different preprocessing/evaluation and are not directly comparable;
- no local YourMT3 or legacy MT3 quality run was completed;
- warm/batched MR-MT3 runtime is unmeasured;
- downstream harmony/bass/melody/arrangement improvements were not separately scored;
- production would require a validated lossless decoder-level adapter.

Promotion requires broader quality evidence, realistic operational measurements, and downstream product value—not just this strong small-subset F1.

## Verification

The original evaluator head `7057c1c247fb2770fee5f5e418479cbf69bd4619` passed Ruff/format, generated API-contract verification, 17 dedicated tests, the required Python suite (`756 passed, 13 skipped, 37 deselected`), Build, E2E, Real-stack E2E, Backend Image, CodeQL, Dependency Review, and Gitleaks.

The measured stage adds machine-readable evidence, decoder/serializer provenance, documentation, and deterministic result-fixture tests. Fresh CI on the final synchronized PR head is required before merge.

Part of #337. Parent #327. Schema consumer #336. Product consumer #340.
