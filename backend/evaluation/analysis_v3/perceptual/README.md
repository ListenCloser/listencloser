# Analysis V3 perceptual evidence (#455)

This directory evaluates a small, reusable layer of **measured audio evidence** between exact event detectors and semantic interpretation.

It is evaluation-only. Nothing here changes `capabilities.json`, production routing, persistence, Inspector/Breakdown, Ask, or deployment dependencies.

## First slice

The initial dependency-neutral baseline uses libraries already present in the locked backend environment:

- RMS amplitude envelope
- spectral centroid
- relative coarse-band energy (`low`, `low_mid`, `mid`, `high`)
- onset-strength envelope

These were selected because they map to recurring downstream relationships without requiring semantic labels:

| evidence | literal meaning | possible downstream relation | not asserted here |
| --- | --- | --- | --- |
| RMS | frame amplitude/energy proxy | A is louder/higher-energy than B | exciting, intense |
| spectral centroid | spectral center of mass | spectral center shifts upward/downward | bright, dark |
| relative band energy | fraction of frame power in coarse bands | low end enters/drops; energy redistributes | bass instrument identity |
| onset strength | localized spectral-flux/transient evidence | activity/transient density changes | groove/style identity |

A semantic explanation may later contextualize these observations, but the measured evidence layer must not encode those interpretations as fact.

## Deterministic validation

Run:

```bash
uv run --project backend python -m backend.evaluation.analysis_v3.perceptual.run_synthetic
```

or write machine-readable output:

```bash
uv run --project backend python -m backend.evaluation.analysis_v3.perceptual.run_synthetic \
  --output backend/evaluation/analysis_v3/perceptual/results/synthetic.json
```

The controlled probes currently verify:

1. an 8x amplitude change produces the expected RMS ratio;
2. a 220 Hz -> 4 kHz tone change moves the spectral centroid accordingly;
3. 100 Hz and 6 kHz tones concentrate power in the expected coarse bands;
4. relative band energy is stable under a global gain change;
5. denser impulse activity produces materially stronger onset activity.

These probes establish basic directionality, localization semantics, and one invariance property. They do **not** establish product usefulness on real music.

## Current channel policy

This first slice fails closed on stereo input instead of silently downmixing it. Stereo/mid-side evidence has different semantics and should be evaluated as its own #455 sub-slice before a canonical channel policy is chosen.

## Next evidence gates

Before any feature can be recommended for production:

1. run rights-safe real-music diversity probes;
2. test codec/sample-rate/gain/window stability;
3. evaluate downstream A/B span comparisons and change ranking;
4. determine normalization rules appropriate to product claims;
5. compare maintained OSS implementations only where behavior/quality differs materially;
6. map each retained feature into #457 evidence-sufficiency gates;
7. record `ADOPT / RESEARCH / REJECT / REVISIT` per feature.

The expected outcome is a deliberately small evidence set, not wholesale adoption of a feature-extraction library.
