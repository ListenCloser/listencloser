# Perceptual evidence evaluation — bounded M1 promotion gate

Issue: #455  
Parent: #327  
Roadmap consumer: #457 / #459

## Status

**PROMOTION CANDIDATE — narrow within-work measured evidence only.**

The synthetic correctness gate is now supplemented by a real-audio stability probe and a canonical-preprocessing rerun. The result supports a bounded M1 implementation of typed perceptual series for explicit within-work A/B comparisons. It does **not** support semantic timbre adjectives, calibrated loudness, cross-song ranking, or automatic interpretation.

The real-audio probe uses:

- the repository's existing `real-piano.m4a` real-stack fixture, used only as an acoustic/piano engineering fixture;
- public Candombe performance `csic.1995_ansina1_03`, CC BY 4.0, verified against MD5 `fffe0c4677d994cbc16e7009b7cad982`.

Two recordings are intentionally **not** called a diversity benchmark. They are a preprocessing/stability gate.

Canonical result provenance:

- evaluation branch: `eval-perceptual-evidence-v3`;
- behavioral result head: `ef6af406405686554b66beb15b91d588992bd586`;
- GitHub Actions workflow: `Perceptual Real Audio Stability`, run `33241509991`;
- librosa `0.11.0`, numpy `1.26.4`;
- canonical preprocessing candidate: **mono + 22.05 kHz**;
- intended comparison scope: **within one work**.

## First-round evidence set

| feature | measured meaning | canonical real-audio result | M1 decision |
| --- | --- | --- | --- |
| RMS | frame amplitude proxy | exact gain response; ~5% median shift after 128 kbps MP3 remains | **BOUNDED** — relative evidence under one canonical decode/preprocessing path only |
| spectral centroid | spectral center of mass | canonical codec drift ~0.1% piano / ~0.6% Candombe | **PROMOTE for within-work comparisons** |
| relative coarse-band energy | fraction of frame STFT power by broad frequency region | main bands generally <1% codec drift after canonicalization; span-boundary sensitive | **PROMOTE with explicit span provenance** |
| onset strength | localized spectral-flux/transient evidence | canonical codec drift ~0.24% piano / ~1.62% Candombe | **PROMOTE for within-work comparisons** |

No semantic adjective is an output of this evidence layer.

## Why canonical preprocessing is required

The native-sample-rate diagnostic intentionally recomputes the same descriptors after changing sample rate without first imposing a canonical analysis contract. It fails badly enough to be a hard architectural warning.

On Candombe, the native-rate diagnostic includes approximately:

- onset-strength median: **+356%**;
- spectral centroid: **+18%**;
- large changes in coarse high-frequency-band proportions.

Those values are not safe to compare across files analyzed at arbitrary native sample rates. The solution is not feature-specific correction factors; it is one explicit preprocessing contract before feature extraction.

Therefore the bounded M1 path is:

```text
decoded work
  -> mono
  -> resample to 22.05 kHz
  -> time-localized PerceptualSeriesEvidence
  -> explicit seconds spans
  -> within-work comparison
```

The original native-rate failure stays in the evaluation output because it establishes why this contract is necessary.

## Canonical codec stability

Original recordings and ffmpeg/libmp3lame 128 kbps variants were independently decoded and then both canonicalized to mono 22.05 kHz before descriptor extraction.

### Repository piano fixture

Median relative codec deltas after canonicalization:

- onset strength: approximately **+0.24%**;
- spectral centroid: approximately **+0.11%**;
- low-band energy fraction: approximately **+0.02%**;
- low-mid fraction: approximately **+0.01%**;
- mid fraction: approximately **+0.03%**;
- high-band fraction: approximately **+1.38%**, on a very small absolute component;
- RMS: approximately **-4.99%**.

### Candombe recording

Median relative codec deltas after canonicalization:

- onset strength: approximately **-1.62%**;
- spectral centroid: approximately **+0.61%**;
- low-band energy fraction: approximately **+0.16%**;
- low-mid fraction: approximately **-0.07%**;
- mid fraction: approximately **+0.63%**;
- high-band fraction: approximately **+3.59%**, again on a small component;
- RMS: approximately **-4.98%**.

### Interpretation

Canonical preprocessing materially removes the sample-rate/container confound for onset strength, centroid, and the principal band-energy components under this probe. That is sufficient to justify a narrow measured-series implementation for same-work comparisons.

RMS is different: the ~5% codec-level shift remains even after sample-rate canonicalization. Treat it as an amplitude proxy under a controlled decode/preprocessing chain, not calibrated loudness and not a cross-encode absolute ranking signal.

## Gain behavior

Scaling source amplitude by 0.5 produced the expected result:

- RMS median changes by exactly -50%;
- spectral centroid is effectively unchanged;
- relative band-energy fractions are unchanged to numerical precision;
- onset-strength median is effectively unchanged.

This confirms that the three non-RMS descriptors are suitable for gain-independent relation evidence under the tested implementation. RMS intentionally retains amplitude information.

## Span-boundary sensitivity

A 10-second span shifted later by only 0.5 seconds can cross genuinely different musical content.

Observed examples:

- RMS/onset medians are relatively stable in these probes;
- centroid changes are modest;
- coarse band ratios can move substantially, including roughly +40% for one piano low-band example and around -9% for a Candombe low-band example.

This is not necessarily estimator noise. The altered window can contain different spectral content. It means the **claim is localization-dependent**.

Therefore the first relation layer should compare:

- user-selected spans; or
- spans supplied by another evidence source whose provenance and boundary quality are explicit.

Do not hide uncertain structure boundaries behind an apparently precise A/B conclusion. A later relation-quality layer can add boundary perturbation/sensitivity envelopes where useful.

## Bounded M1 recommendation

Promote only the evidence substrate required for literal comparisons:

```text
canonical PerceptualSeriesEvidence
  + explicit span locators
  + provenance / preprocessing metadata
  -> measured A/B relation input
```

Candidate literal observations include:

- onset activity is higher/lower in span B than span A;
- spectral centroid is higher/lower in span B than span A;
- relative low/low-mid/mid/high spectral energy distribution changed between spans;
- RMS amplitude proxy increased/decreased within the same canonical work, with its restricted meaning explicit.

These are evidence/derived observations, not editorial interpretations.

## Do not promote yet

This evaluation does not justify:

- `brighter`, `warmer`, `fuller`, `thinner`, `more exciting`, `more intense`, or similar adjectives as measured facts;
- calibrated loudness claims from RMS;
- cross-song descriptor ranking;
- source/instrument identity inferred from spectral bands;
- automatic `drop`, `buildup`, `chorus`, or transition semantics;
- universal change thresholds;
- exact boundary claims without trusted/user-selected localization;
- persistence as one database column per descriptor;
- frontend exposure before relation/evidence provenance can be inspected.

Semantic or style-specific interpretation remains downstream of the evidence layer and must satisfy #457 sufficiency/applicability gates.

## Contract input for #336

The evaluation continues to support a time-series contract rather than whole-track scalar fields:

```ts
type PerceptualSeriesEvidence = {
  feature: string
  unit?: string
  frameTimesSeconds: number[]
  values: number[] | number[][]
  normalization: string
  channelMode: "mono" | "stereo" | "mid_side" | string
  artifactVersionId: string
  provenance: {
    sampleRate: number
    preprocessing: string
    engine: string
    engineVersion?: string
  }
}
```

For this first M1 slice, `sampleRate` should be 22050 and `channelMode` should be mono. Stereo/spatial evidence is a separate conditional family and should not be silently derived after downmixing.

Rich A/B output should later be represented as a grounded **RelationObservation** under the existing Evidence Graph Observation contract, optionally backed by lightweight graph relation edges. Do not turn the existing Relation edge itself into a second large evidence schema.

## What this changes in the roadmap

The remaining uncertainty is no longer “do cheap perceptual descriptors work at all?” The bounded engineering question is now whether to productionize a small canonical series extractor and expose it first to relation/analysis code.

Recommended next step:

1. implement canonical mono/22.05 kHz perceptual extraction as a bounded evidence provider;
2. emit typed time-localized series with explicit preprocessing provenance;
3. implement no semantic prose in that PR;
4. follow with one `COMPARE` RelationObservation over explicit spans;
5. evaluate whether those comparisons unlock useful Inspector/Ask proof interactions before expanding the descriptor set.

Adding more generic DSP features or another descriptor library is lower priority until a concrete downstream relation requires something missing.

## Remaining uncertainty

- only two real recordings were used for preprocessing stability;
- no claim is made about broad cross-style distributional norms;
- RMS is not calibrated loudness;
- no stereo/spatial evidence has been validated;
- no automatic transition detector has been validated;
- downstream product usefulness still needs an end-to-end relation/proof test;
- future style-specific analyses may require additional evidence primitives rather than more interpretation over these four series.
