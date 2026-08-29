# Perceptual evidence evaluation — initial synthetic gate

Issue: #455  
Parent: #327  
Roadmap consumer: #457 / #459

## Status

**RESEARCH — first deterministic gate only.**

This report does not recommend product exposure. It establishes a small first-round descriptor set and a reproducible synthetic correctness contract before real-music/downstream evaluation.

## First-round candidates

| feature | implementation | measured meaning | normalization | synthetic gate | current decision |
| --- | --- | --- | --- | --- | --- |
| RMS | `librosa.feature.rms` | frame amplitude/energy proxy | none | amplitude-step ratio | RESEARCH |
| spectral centroid | `librosa.feature.spectral_centroid` | spectral center of mass | none | controlled frequency shift | RESEARCH |
| relative coarse-band energy | STFT power using `librosa.stft` | fraction of frame power by broad frequency region | per-frame total STFT power | band separation + gain invariance | RESEARCH |
| onset strength | `librosa.onset.onset_strength` | localized spectral-flux/transient evidence | librosa default | sparse vs dense impulses | RESEARCH |

No semantic adjective is a candidate output of this layer.

## What this gate establishes

The deterministic fixtures test whether the implementation responds in the expected direction to controlled physical changes and whether one explicitly normalized descriptor remains stable under global gain scaling.

This is useful because a descriptor that fails these controlled probes should not proceed to expensive real-music/product evaluation.

## What it does not establish

- real-music robustness;
- cross-codec/sample-rate robustness;
- perceptual validity of words such as `bright`, `dark`, `full`, `thin`, `intense`, or `warm`;
- structure/change-point accuracy;
- downstream explanatory value;
- stereo/spatial semantics;
- production persistence or capability exposure.

## Why librosa first

The backend already depends on librosa and uses it in production analysis paths. The first gate therefore adds no dependency or model. #455 calls for maintained OSS over bespoke DSP when practical, but it also explicitly rejects adopting an extractor wholesale.

The next comparison against Essentia or another implementation should happen only where it provides a materially different measurement, normalization, or quality path worth evaluating.

## Next decision-bearing experiment

Run the same small feature set on rights-safe real recordings and evaluate **relations**, not descriptor aesthetics:

1. A/B span energy comparison;
2. low-band entry/dropout;
3. spectral redistribution across a known transition;
4. onset/activity-density change;
5. multi-feature change convergence.

For each, record whether the relation remains stable under gain normalization, sample-rate/codec changes, and modest boundary perturbation. Feed those findings into #457 before any M1 production work.
