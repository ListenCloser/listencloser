# Analysis V3 Pulse / Beat / Meter Bakeoff

## Executive decision

**Beat This `single_final0` is the leading MetricGrid candidate, but it should not replace the global production default yet.**

The earlier GuitarSet probe showed a large quality advantage over the exact production librosa baseline. This branch adds a split-aware evaluation gate and scores five Candombe performances from the Beat This v1.0 published `single.split` validation partition on identical audio for both candidates.

On that validation partition, Beat This is nearly perfect: mean beat F1 **0.9989**, mean downbeat F1 **1.0000**, **100% reference-beat coverage**, median absolute beat localization error **10.9 ms**, and median absolute downbeat localization error **11.4 ms**. The production librosa path reaches mean beat F1 **0.3847**, matches only **33.46%** of reference beats, and exposes no downbeats. Both candidates estimate global tempo accurately on these files, which demonstrates that BPM accuracy alone is not a sufficient quality gate for groove-, phase-, or bar-relative reasoning.

This is strong promotion evidence for the Beat This model family, but it is **not an independent-corpus generalization result**: the five tracks are the published validation split associated with `single_final0`. Before changing the global default, evaluate at least one genuinely independent annotated corpus/split and make an explicit latency/deployment decision.

## Product question

Which OSS system should provide beat positions, downbeat positions, tempo, and eventually meter evidence for hello-ai's rhythm, groove, structure, notation, and style-aware analysis?

## Existing production baseline

- **Engine**: librosa via the production beat path.
- **Function**: `music_features.estimate_beat_grid(wav_bytes)` / librosa beat tracking.
- **Preprocessing**: decoded mono audio; the evaluation runner canonicalizes to 22.05 kHz for identical candidate input.
- **Output**: beat positions and tempo.
- **Downbeats**: unsupported.
- **Meter**: unsupported.
- **Production default**: remains librosa on this research branch.

## Candidate matrix

| Candidate | Code / checkpoint license | Beats | Downbeats | Tempo | Meter | Current decision |
| --- | --- | --- | --- | --- | --- | --- |
| current | librosa ISC / N/A | yes | no | yes | no | retain production default until promotion gate closes |
| Beat This `single_final0` | MIT / MIT | yes | yes | derived | no | leading promotion candidate |
| BeatNet | MIT / MIT | yes | yes | yes | no | REVISIT; compatibility friction |

## Evaluation validity

The evaluation code records checkpoint training datasets and held-out datasets and rejects silent scoring on a declared training corpus unless `--allow-training-overlap` is supplied explicitly.

For Beat This `single_final0`:

- dataset id: `candombe_single_split_val`;
- checkpoint: `single_final0`;
- declared training overlap: none;
- declared held-out/validation match: `candombe_single_split_val`;
- five exact validation recordings acquired from the public Candombe site;
- each audio file is MD5-verified before scoring;
- Beat This and the production baseline receive the same decoded/canonicalized audio;
- the workflow stores machine-readable results as an Actions artifact.

The term **held-out** here means held out from the checkpoint's training rows according to the published split metadata. It does not mean an unrelated dataset. This distinction is why another independent corpus remains a promotion requirement.

See `VALIDITY.md` for the provenance contract and `.github/workflows/eval-pulse-candombe-heldout.yml` for the exact acquisition/scoring path.

## Canonical metrics

Beat and downbeat F1 use `mir_eval.beat.f_measure` with a 70 ms threshold. Diagnostic precision/recall, match counts, and localization errors use `mir_eval.util.match_events` with the same 70 ms one-to-one matching window, so the displayed diagnostics do not rely on a separate greedy matcher.

Localization reporting always includes match coverage. Timing error over matched events alone is misleading when a tracker misses or mis-phases most events.

## Candombe validation result

Five published `single.split` validation performances were scored with zero candidate failures.

| Metric | production librosa | Beat This `single_final0` |
| --- | ---: | ---: |
| Mean beat F1 | 0.3847 | **0.9989** |
| Median beat F1 | 0.1710 | **0.9993** |
| Minimum beat F1 | 0.0379 | **0.9971** |
| Reference beats matched | 1,122 / 3,353 | **3,353 / 3,353** |
| Reference-beat coverage | 33.46% | **100.00%** |
| Predicted-beat coverage | 33.27% | **99.82%** |
| Median absolute beat error | 40.6 ms | **10.9 ms** |
| p95 absolute beat error | 56.6 ms | **44.9 ms** |
| Mean downbeat F1 | unsupported | **1.0000** |
| Reference downbeats matched | unsupported | **842 / 842** |
| Median absolute downbeat error | unsupported | **11.4 ms** |
| p95 absolute downbeat error | unsupported | **47.4 ms** |
| Tempo accuracy at 4% | 100% | 100% |
| Mean relative tempo error | 1.47% | 1.44% |

### Why tempo is not the decision metric

Both systems estimate the global tempo rate correctly on these recordings, yet the production tracker often places beats at the wrong local phase. That difference is decisive for downstream claims such as:

- an onset anticipates a beat or downbeat;
- a drum pattern emphasizes beat 2 or beat 4;
- a fill leads into the next bar;
- two rhythmic events align or offset;
- a groove changes within a section.

A correct BPM scalar cannot support those claims without a trustworthy localized metric grid.

## CPU latency

The candidate is materially more expensive than librosa on CPU. Recent GitHub-hosted Ubuntu runs place Beat This inference on these roughly 3–5 minute recordings around the low tens of seconds per track, while the warm-state librosa path is sub-second on most files. Earlier runs varied materially with runner state, checkpoint/cache state, and host load.

Therefore latency is recorded as **operational evidence, not a stable universal benchmark**. The quality result is clear; production promotion still needs a deliberate deployment choice such as worker-side asynchronous analysis, model reuse, or a faster execution target. There is no evidence here that a synchronous request path should block on the model.

## Earlier GuitarSet probe

The initial five-clip GuitarSet probe remains useful as a separate repertoire signal:

| Candidate | Mean beat F1 | Mean downbeat F1 | Mean tempo error |
| --- | ---: | ---: | ---: |
| production librosa | 0.30 | unsupported | 17.19 BPM |
| Beat This | **0.94** | **0.86** | **1.87 BPM** |

The result should not be treated as a broad genre benchmark; it contains only a handful of guitar comping/solo examples. Its value is that it independently showed the same large direction-of-effect before the split-aware Candombe gate was added.

## Product implications

A high-quality MetricGrid unlocks substantially more than a BPM badge. It can become upstream evidence for:

- beat/bar aligned playback and looping;
- beat-relative onset and source-activity measurements;
- groove and syncopation relations;
- downbeat-aware section and transition evidence;
- notation/quantization support;
- drum/bass pattern comparison;
- later rap-flow or ensemble-coordination analysis when their additional prerequisites exist.

These downstream claims must still declare their own evidence-sufficiency gates. A good beat tracker does not by itself make genre- or theory-specific interpretation safe.

## Proposed PulseEvidence contract

```typescript
type PulseEvidence = {
  sourceArtifactVersionId: string
  engine: string
  engineVersion?: string

  beats?: Array<{
    timeSeconds: number
    confidence?: number
  }>

  downbeats?: Array<{
    timeSeconds: number
    confidence?: number
  }>

  tempo?: {
    bpm: number
    confidence?: number
    scope: "global" | "segment"
    span?: {
      startSeconds: number
      endSeconds: number
    }
  }

  meter?: {
    numerator: number
    denominator: number
    confidence?: number
  }

  provenance: {
    parameters?: Record<string, unknown>
    checkpoint?: string
    checkpointChecksum?: string
  }
}
```

This is an architecture input for #336 rather than a request to create a parallel database schema.

## Promotion gate

Beat This should move from generic **RESEARCH** to **PROMOTION CANDIDATE** status, with these remaining gates:

1. Score at least one genuinely independent annotated corpus/split not listed as checkpoint training or validation data.
2. Preserve event-level localization metrics and coverage; do not regress to BPM-only evaluation.
3. Confirm the production execution model and acceptable worker latency/resource cost.
4. Decide failure/fallback behavior when the model cannot load or analyze a file.
5. Keep meter unsupported unless separately measured.
6. Only after those gates, consider changing the global `MetricGrid`/beat default.

The validation result is strong enough that additional broad candidate shopping is lower priority than validating this candidate's generalization and production ergonomics.

## Reproduction

The branch-scoped workflow acquires and verifies the five exact Candombe recordings, builds the v1.0 validation manifest, and scores `current` and `beat_this_single_final0` on identical inputs. Local scoring can also use the manifest runner once the same audio/annotation assets are available.

Results are machine-readable and include:

- per-piece beat/downbeat F1;
- canonical matched counts;
- reference and predicted coverage;
- signed and absolute timing error summaries;
- tempo error;
- per-file inference latency;
- checkpoint/dataset validity metadata.

## Remaining uncertainty

- Candombe is checkpoint validation data, not an independent external corpus.
- Five Candombe + five GuitarSet examples are not broad genre coverage.
- Meter remains unsupported.
- CPU latency is materially higher and environment-dependent.
- No source-aware groove or microtiming claims are validated merely by this benchmark.
- BeatNet remains a low-priority revisit unless it offers a concrete advantage over a now-strong Beat This candidate.
