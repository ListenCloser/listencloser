# Analysis V3 Context Evidence Bakeoff

## Executive decision

**No context model is ready to become a production fact source.**

- **Essentia Discogs-EffNet + MTG-Jamendo heads: REVISIT for production, strong REFERENCE benchmark.** Official model metadata reports meaningful supervised benchmark performance, but Essentia's open library path is AGPLv3 for non-commercial use and the pretrained models are CC BY-NC-ND 4.0 for non-commercial use; commercial licensing is available separately. That makes the stack useful for research comparison but not a default free production dependency.
- **LAION CLAP `laion/larger_clap_music`: RESEARCH.** #332 established attractive CPU/ARM feasibility and a permissive checkpoint license, but its tiny text-to-passage probe did not show reliable factual semantic discrimination. This PR adds the matched context-evaluation path needed before any adoption decision.
- **Mood/theme wording remains withheld from product facts.** The upstream supervised reference is useful research evidence, but subjective labels and lower published PR-AUC demand stronger calibration/product-language work than genre/instrument context.

The architecture implication is to treat style/instrument outputs as **probabilistic context evidence**, never a rigid `if genre == X` router and never equivalent to measured beat/pitch/chord evidence.

## Evidence boundary

### Measured previously by hello-ai (#332)

The committed CLAP result records:
- model: `laion/larger_clap_music`
- CPU/ARM load success
- ~0.10 s measured 10-second embedding latency in that environment
- 512-dimensional global audio/text embeddings
- a seven-query text-retrieval product probe

That retrieval probe is small and qualitative. For example, the query `solo piano` did **not** rank either of the two MAESTRO solo-piano excerpts in its top four results. This is direct evidence not to convert CLAP text similarity into a factual tag confidence yet.

`--task prior` additionally computes prompt-ranking diversity diagnostics from the committed result. Low top-1 diversity or high top-3 overlap is evidence of poor prompt discrimination, but is not itself an accuracy metric.

### Official upstream REFERENCE benchmarks

Essentia's official MTG-Jamendo classification-head metadata reports:

| Task | Test PR-AUC | Test ROC-AUC | Tracks | Outputs |
|---|---:|---:|---:|---:|
| Genre | 0.20 | 0.88 | 55,215 | 87 |
| Instrument | 0.20 | 0.78 | 25,135 | 40 |
| Mood/theme | 0.14 | 0.76 | 18,486 | 56 |

These values are upstream reference evidence, **not local measurements**. They are not directly comparable to the tiny CLAP probe because the datasets, taxonomies, training regimes, and metrics differ.

Sources are machine-recorded in `reference_metrics.json`.

## Local scored probe design

`manifests/context_probe.json` deliberately scores only labels justified by source metadata:

- GuitarSet bossa nova → `bossa nova`, `guitar`
- GuitarSet rock → `rock`, `guitar`
- GuitarSet jazz → `jazz`, `guitar`
- two MAESTRO excerpts → `classical`, `piano`

BabySlakh mixtures are included only for prediction/stability inspection. The harness does **not** invent a genre or instrument ground truth for them.

The probe reports precision@1, precision@3, recall@3, and label-ranking average precision. It also reports adjacent 5-second top-3 Jaccard as a stability diagnostic, with an explicit warning that a constant model can be stably wrong.

This tiny probe is a product sanity check, not a publishable benchmark and not a replacement for the standard MTG-Jamendo test split.

## Candidate decisions

### Essentia Discogs-EffNet + MTG-Jamendo heads — REVISIT

**Research quality:** strong reference candidate because official supervised task metrics and concrete taxonomies exist.

**Product fit:** potentially useful for multi-label genre and instrumentation context; mood/theme requires more cautious language and calibration.

**Deployment/license fit:** blocked for a default free commercial path. Official Essentia licensing states the open library is AGPLv3 for non-commercial applications; pretrained models are CC BY-NC-ND 4.0 for non-commercial use, with proprietary licensing available on request. Third-party dependency obligations also need review.

**Decision:** REVISIT if a commercial license or a permissively licensed equivalent becomes justified by measured value. Keep as reference evidence now.

### LAION CLAP — RESEARCH

**Research quality:** useful zero-shot audio-text baseline.

**Product fit:** attractive if it can provide broad style/instrument context without one bespoke classifier per taxonomy, but the prior #332 prompt retrieval is not discriminative enough to trust as facts.

**Deployment/license fit:** #332 measured fast CPU/ARM inference; the Hugging Face model card for `laion/larger_clap_music` declares Apache-2.0 for the checkpoint. Training-data provenance and downstream use still require normal diligence.

**Decision:** RESEARCH. Run the labeled product probe and, if promising, a real standard-split multi-label evaluation before considering integration.

## Why no hard genre router

A work can be multi-style, genre-adjacent, culturally ambiguous, or change character by section. Context tags should influence which evidence and explanations are salient, not fork the application into genre products.

Examples of legitimate use after validation:
- raise the salience of groove evidence when rhythm-forward context is strongly supported;
- surface instrumentation/layer evidence when source-role tags are stable;
- choose explanatory vocabulary appropriate to the selected passage while still citing measured evidence.

Illegitimate use:
- `if genre == "jazz": use jazz pipeline`;
- treating one model's top label as ground truth;
- presenting raw cosine similarity as calibrated confidence;
- suppressing universal evidence because a style tag disagrees.

## Proposed ContextEvidence contract

Schema proposal only; #336 owns persistence.

```typescript
type ContextEvidence = {
  scope: "work" | "segment"
  span?: { startSeconds: number; endSeconds: number }
  taxonomy: string
  category: "style" | "instrument" | "mood_theme" | "production"
  labels: Array<{
    label: string
    score: number
  }>
  calibration?: {
    method: string
    threshold?: number
  }
  provenance: {
    engine: string
    model: string
    modelVersion?: string
    checkpointChecksum?: string
    parameters?: Record<string, unknown>
  }
  maturity: "evaluation_only" | "production"
}
```

`score` is intentionally neutral. Only a benchmarked calibration procedure may justify calling a value `confidence`.

## Failure modes the next scored run must inspect

- prompt-ranking collapse across distinct labels;
- multi-label pieces where one dominant tag hides secondary character;
- sparse acoustic recordings;
- dense produced mixes;
- section-level label instability;
- genre-adjacent ambiguity;
- culturally distant/non-Western music, where Western-pop taxonomies may be incomplete or misleading.

The current tiny corpus does **not** satisfy the cultural-generalization requirement. That remains an explicit gate before broad product claims.

## What this PR does not do

- no production engine registration
- no `capabilities.json` exposure
- no database/schema/vector-index change
- no UI tag chips
- no genre-specific product branch
- no mood/theme claims as facts
- no new model package in production dependencies
- no multi-gigabyte model download in required CI

## Next gate for #333

1. Run the CLAP zero-shot probe on cached rights-safe audio and commit the machine-readable result.
2. If CLAP clears the tiny sanity check, evaluate on a lawful labeled MTG-Jamendo test subset using task-standard multi-label metrics.
3. Compare against the Essentia reference/head on the same taxonomy where a lawful runnable environment is available.
4. Add calibration/error slices and culturally diverse probes before any production recommendation.

Until those gates are met, #333 remains open.
