# Analysis V3E report — generic multi-instrument transcription

**Status:** measured small-subset stage. No production integration.

## Decision

**Keep the current Basic Pitch path as the production flat-note baseline. Keep MR-MT3 at `RESEARCH` as a possible optional multi-instrument evidence path; do not adopt it as a default or replacement.**

The five-excerpt result does not show a general note-transcription win for MR-MT3, and its exact program-attributed note quality is still weak. It does show a potentially useful coarse instrument-family presence signal worth retaining for future research.

Candidate decisions:

| candidate | decision | reason |
| --- | --- | --- |
| hello-ai Basic Pitch | **ADOPT (existing baseline)** | already deployed, much cheaper, stronger macro flat-note recovery on this subset; program attribution unsupported |
| MR-MT3 | **RESEARCH** | meaningful instrument-family detection signal, but weaker flat/note recovery, low exact program-attributed note F1, high current CPU wrapper cost |
| Magenta MT3 | **REVISIT** | Apache-2.0 code, but external checkpoint licensing remains unresolved and legacy T5X/JAX stack adds friction |
| YourMT3+ | **RESEARCH reference** | potentially stronger quality reference, but official code is GPL-3.0 and is not the clean permissive production-candidate slot |
| MuScriptor | **research reference only** | released weights are CC BY-NC 4.0 |

No candidate changes production routing in this PR.

## Measured protocol

Dataset: **Slakh2100-redux**, test split, CC BY 4.0.

Measured fixed subset:

- `Track01876`
- `Track01877`
- `Track01878`
- `Track01880`
- `Track01881`

Each excerpt is the first 30 seconds. Ground truth is assembled from active per-source `MIDI/SXX.mid` files marked `midi_saved: true` in `metadata.yaml`, not `all_src.mid`.

The full Redux release is a large monolithic archive, so the run used a selective Hugging Face acquisition mirror pinned to immutable revision `bb320faf307f5d24aeced0e60f9445ff0abce205`. The mirror preserves the Redux directory/metadata contract; upstream identity/license remain Zenodo 4599666 / CC BY 4.0. Every cropped mix and reference MIDI is checksummed in `results/slakh_redux_subset_results.json`.

Hello-ai measurement/code SHA: `7057c1c247fb2770fee5f5e418479cbf69bd4619`.

MR-MT3 runner/checkpoint:

- `mt3-infer 0.2.0`
- runner revision `2d20ee5bb6ca727968bd23c6100fd2a35154166b`
- isolated CPU `torch 2.6.0+cpu`
- checkpoint SHA-256 `b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f`
- checkpoint bytes `183672643`
- runner/code license MIT
- weight repository metadata MIT

The hello-ai backend environment remained independently pinned to `torch 2.6.0+cpu` throughout the clean runs.

## Metrics

Canonical note matching uses `mir_eval 0.8.2` maximum bipartite assignment:

- onset tolerance: 50 ms
- pitch tolerance: 50 cents
- offset-aware tolerance: `max(50 ms, 20% of reference-note duration)`
- explicit drum label: `128`

No weighted composite is used.

### Macro result

| metric | Basic Pitch | MR-MT3 |
| --- | ---: | ---: |
| flat onset F1 | **0.3871** | 0.3366 |
| flat onset+offset F1 | **0.1397** | 0.0977* |
| GM-family onset F1 | N/A | 0.3147 |
| exact-program onset F1 | N/A | 0.2286 |
| exact-program onset+offset F1 | N/A | 0.0512 |
| exact-program detection F1 | N/A | 0.3875 |
| GM-family detection F1 | N/A | **0.9113** |

`*` Program-preserving serialization; see the validity section below.

Basic Pitch does not provide instrument-program or drum attribution. Its generated MIDI may contain default program values required by the file format, but those are **not evidence** and are therefore not interpreted in the comparison.

### Flat onset F1 by excerpt

| track | Basic Pitch | MR-MT3 |
| --- | ---: | ---: |
| Track01876 | **0.2988** | 0.1473 |
| Track01877 | **0.6883** | 0.4867 |
| Track01878 | 0.2701 | **0.5411** |
| Track01880 | **0.2363** | 0.1992 |
| Track01881 | **0.4419** | 0.3089 |

The distribution matters: MR-MT3 has a real win on one excerpt but is not consistently stronger.

### MR-MT3 instrument-aware result by excerpt

| track | GM-family onset F1 | exact-program onset F1 | exact-program note F1 | family detection F1 |
| --- | ---: | ---: | ---: | ---: |
| Track01876 | 0.1060 | 0.0383 | 0.0236 | 1.0000 |
| Track01877 | 0.4867 | 0.4791 | 0.1369 | 0.8000 |
| Track01878 | 0.5137 | 0.2740 | 0.0342 | 0.8333 |
| Track01880 | 0.1857 | 0.1772 | 0.0371 | 0.9231 |
| Track01881 | 0.2813 | 0.1743 | 0.0242 | 1.0000 |

Interpretation: MR-MT3 often identifies the **presence of broad instrument families**, but assigning the correct notes to exact programs remains far less reliable. That is not strong enough for a trustworthy instrument-aware score/piano-roll representation today.

## Serializer validity finding

The evaluation discovered an upstream runner issue that materially affects any naïve instrument benchmark.

In pinned `mt3-infer 0.2.0`, the MR-MT3 codec/state decoder retains `Note.program` and `is_drum`. The stock adapter's final `mido.MidiFile` serialization then discards `Note.program`: all pitched notes are emitted on channel 0 and no `program_change` messages are written. Stock-CLI exact-program/family results are therefore **not valid model-attribution scores**.

A throwaway research run patched **only that final serializer**:

- same model/checkpoint
- same preprocessing
- same forward generation
- same codec and event decoder
- same note event ordering
- same pitch/velocity/timing conversion
- each already-decoded pitched program assigned a unique non-drum MIDI channel
- channel 9 reserved for drums
- `program_change` messages emitted at time zero

Patch provenance:

- upstream adapter SHA-256 before patch: `5b376389c1f1794862b2704237cd01e20b1c2c32f474a429cf52afd20b2122ef`
- patched adapter SHA-256: `c024fc59dbacbf61d8bf15fc4886beba353b345f4f04592f8c5cbc3fb24ccb05`
- stock workflow run: `33213511319`, head `4f380d51fa74e67e9c67bb8e5952a749083621f5`
- patched workflow run: `33215520514`, head `cf100d2dd1338dbe3819994fa9a695d63bd79320`

Independent artifact comparison established, for **all five tracks**:

1. identical manifest bytes;
2. identical predicted note counts;
3. identical flat onset F1;
4. identical complete raw note-on/note-off event sequence when channel is ignored;
5. identical normalized note-event SHA-256 when channel/program assignment is omitted.

Offset-aware flat F1 changes on `Track01878` and `Track01881`. This is expected: separate channels disambiguate overlapping same-pitch notes that the stock channel-0 serializer makes ambiguous to MIDI parsers. Because the raw note-event sequence is otherwise identical, the patched program-aware metrics are accepted as evidence of the already-decoded MR-MT3 output. Stock program-aware metrics are quarantined.

The patch is **not** proposed as production code. It exists only as evaluation provenance.

## Operational result

Basic Pitch on the GitHub CPU runner:

- first excerpt: ~25 s including cold/model-load cost
- remaining four: ~1.5–1.8 s each

MR-MT3 through the stock process-per-track CLI:

- per-excerpt wall time: ~26–155 s
- median: ~101 s in the patched run
- peak RSS: ~817–863 MB
- checkpoint download excluded from per-track wall times after prefetch in the patched run

This strongly overstates what a persistent warm MR-MT3 service might cost because the CLI reloads the model for each track. It nevertheless demonstrates that the current wrapper shape is not suitable for the Oracle CPU production path as-is. Warm/batched runtime would need separate evaluation before any integration.

## Product/architecture interpretation

The useful signal is narrower than "multi-track transcription works":

- Basic Pitch remains better as the cheap generic note-recovery baseline on this small mixed-music subset.
- MR-MT3 may add coarse **instrument-family presence** evidence.
- Exact program-attributed note quality is too low for a trusted instrument-aware notation/piano-roll layer.
- The result does not justify making symbolic transcription central to all analysis.
- If revisited, multi-track AMT should remain an optional evidence producer attached to a Work/version and consumed selectively by arrangement, bass/melody, comparison, or representation features.

A future payload should remain under the #336 canonical evidence envelope:

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

An evaluated neural detector without calibrated probabilities should not invent `confidence`; #336 trust semantics remain authoritative.

## Limitations

- only five fixed 30-second excerpts;
- deterministic subset, not a representative production benchmark;
- published MR-MT3 Slakh results use a different grouped-stem/bass-correction protocol and are not directly comparable;
- no local YourMT3 or legacy MT3 quality run;
- no downstream harmony/bass/melody task was separately rescored using the multi-track output;
- MR-MT3 warm/batched CPU runtime was not measured;
- selective mirror is pinned and file-hashed, but the authoritative dataset remains the upstream Redux release.

These limitations prevent an `ADOPT` decision for a new engine. They do not invalidate the narrower conclusion that the currently practical permissive candidate is **research-only**, not a default replacement.

## Verification

The original harness code head `7057c1c247fb2770fee5f5e418479cbf69bd4619` passed Ruff/format, generated API-contract verification, 17/17 dedicated tests, the required Python suite (`756 passed, 13 skipped, 37 deselected`), Build, E2E, Real-stack E2E, Backend Image, CodeQL, Dependency Review, and Gitleaks.

The measured stage adds:

- `results/slakh_redux_subset_results.json`
- deterministic result-fixture trust-boundary tests
- documentation only otherwise

Fresh CI on the final measured PR head is required before merge.

Part of #337. Parent #327. Schema consumer #336. Product consumer #340.
