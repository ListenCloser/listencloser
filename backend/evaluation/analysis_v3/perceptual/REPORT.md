# Perceptual evidence evaluation — bounded M1 candidate gate

Issue: #455  
Parent: #327  
Roadmap consumer: #457 / #459

## Status

**RESEARCH — bounded promotion candidate, not production-ready as-is.**

The synthetic correctness gate is now supplemented by a real-audio stability probe on:

- the repository's existing `real-piano.m4a` real-stack fixture (54.55 s), used only as an acoustic/piano engineering fixture;
- public Candombe performance `csic.1995_ansina1_03` (293.17 s), CC BY 4.0, verified against MD5 `fffe0c4677d994cbc16e7009b7cad982`.

The two recordings are intentionally **not** described as a cross-style diversity benchmark. They are a practical real-recording stability probe.

Result provenance:

- evaluation commit: `8e41f139c429e36a579210a7e4d40aa9db1902cf`;
- GitHub Actions workflow: `Perceptual Real Audio Stability`, run `33241122918`;
- machine-readable artifact: `perceptual-real-stability-8e41f139c429e36a579210a7e4d40aa9db1902cf`;
- librosa `0.11.0`, numpy `1.26.4`.

## First-round candidates

| feature | measured meaning | real-audio finding | current decision |
| --- | --- | --- | --- |
| RMS | frame amplitude proxy | behaves exactly under global gain; ~5% median shift after 128 kbps MP3 on both recordings | **BOUNDED CANDIDATE** — same decoded work / same gain chain only |
| spectral centroid | spectral center of mass | gain-invariant; codec median shift ~0.6% piano / ~3.7% Candombe; native-SR change materially shifts value | **CANDIDATE AFTER CANONICAL SR** |
| relative coarse-band energy | fraction of frame STFT power by broad frequency region | exactly gain-invariant; low/mid bands stable under codec; native-SR and boundary changes can materially alter ratios | **CANDIDATE AFTER CANONICAL SR + span policy** |
| onset strength | localized spectral-flux/transient activity evidence | gain-invariant; codec median shift ~0.2% piano / ~2.5% Candombe; strongly sample-rate dependent | **CANDIDATE AFTER CANONICAL SR** |

No semantic adjective is a candidate output of this evidence layer.

## Real-audio findings

### 1. Global gain

Scaling audio amplitude by 0.5 produced:

- RMS median: exactly -50% on both tracks;
- spectral centroid: effectively unchanged;
- relative band-energy fractions: unchanged to numerical precision;
- onset-strength median: effectively unchanged.

This is the intended behavior. RMS is an absolute amplitude proxy, not a gain-normalized loudness measure. The other three descriptors are suitable for gain-independent relations under this probe.

### 2. Codec conversion

Each source was transcoded to MP3 with ffmpeg/libmp3lame at 128 kbps.

Piano median changes:

- onset strength: +0.19%;
- spectral centroid: -0.62%;
- RMS: -4.98%;
- low and low-mid band fractions: <0.02% relative change;
- the extremely small high-band fraction changes ~1.9% relatively but only ~`8.6e-8` absolutely.

Candombe median changes:

- onset strength: +2.50%;
- spectral centroid: -3.74%;
- RMS: -4.89%;
- low / low-mid / mid band fractions: roughly +0.17% / +0.12% / +0.29% relative;
- high-band fraction: +9.5% relative, but only ~`1.42e-4` absolute.

Implication: spectral/onset/band evidence is promising for same-work comparisons across ordinary codec variation. Raw RMS should not be treated as calibrated cross-encode loudness.

### 3. Native sample-rate dependence is the main preprocessing blocker

The probe deliberately recomputed descriptors after resampling to 16 kHz while retaining the same feature definitions.

Piano median changes included:

- onset strength: -4.1%;
- centroid: -9.6%;
- RMS: +2.8%;
- mid-band fraction: -7.0%.

Candombe changed far more:

- onset strength: **+356%**;
- centroid: **+18.4%**;
- RMS: +12.5%;
- low-band fraction: +11.7%;
- mid-band fraction: +58.8%;
- high-band fraction changes by nearly 5x relatively.

These are not safe cross-file measurements if each file is analyzed at arbitrary native sample rate.

**M1 must therefore define one canonical analysis sample rate and preprocessing path before these series become comparable evidence.** Do not interpret these results as a reason to invent correction factors per sample rate.

### 4. Span-boundary sensitivity is claim-dependent

A 10-second span was shifted later by 0.5 seconds.

RMS and onset-strength medians were fairly stable on both recordings (roughly <=2.7% relative change). Spectral centroid moved ~2.7% on the piano and ~0.07% on Candombe.

Coarse-band ratios were more boundary-sensitive:

- piano low-band fraction changed ~+40.6% and low-mid ~-19.1%;
- Candombe low-band fraction changed ~-8.9% and low-mid ~+5.4%.

This does **not** mean the band estimator is numerically unstable. A shifted musical window can legitimately contain different spectral content. It means an A/B claim near a transition depends materially on span localization.

Consequences for #457/#460:

- explicit user-selected spans are a legitimate early comparison path;
- automatically selected spans should carry structure/localization provenance;
- boundary-sensitive claims should eventually report or gate on a small localization-sensitivity envelope rather than pretending the boundary is exact.

## M1 recommendation

Do not promote the current functions verbatim as arbitrary-input evidence providers.

The next bounded M1 contract should be:

```text
single decoded work
  -> canonical mono preprocessing
  -> canonical sample rate
  -> PerceptualSeriesEvidence
  -> explicit seconds locators
  -> within-work A/B RelationObservation
```

Initial product-safe relation language can remain literal:

- `RMS median increased by ... within this work`;
- `spectral centroid is higher in span B than span A`;
- `low-band power fraction increased/decreased`;
- `onset-strength aggregate increased/decreased`.

Do not yet expose:

- `brighter`, `warmer`, `fuller`, `thinner`, `more intense`, `more energetic` as measured facts;
- cross-song absolute RMS ranking;
- cross-file descriptor comparison without identical canonical preprocessing;
- source/instrument identity inferred from band energy;
- exact transition claims from coarse spans without localization evidence.

## Next decision-bearing experiment

One small preprocessing experiment remains before recommending an actual M1 production PR:

1. choose a canonical sample rate and channel policy;
2. canonicalize both original and codec variants through the same path;
3. rerun the two real recordings and verify that codec/source-container differences remain small after canonicalization;
4. retain raw native-SR failure evidence in this report rather than erasing it;
5. if stable, promote only the typed measured series + within-work A/B comparison contract.

There is no current evidence that adding a second OSS descriptor library would be more valuable than first fixing this preprocessing contract.
