# Librosa Structure Boundary Baseline (evaluation only)

## Purpose

This is a deliberately small, CPU-feasible diagnostic baseline.  It uses the
maintained `librosa` dependency already present in the worker: CENS chroma,
cosine self-similarity recurrence, a symmetric chroma-change novelty curve, and
`librosa.util.peak_pick`.  It returns unlabelled candidate times only.  It does
not infer section names, repetitions, hierarchy, key regions, or confidence.

## Provenance

- Engine: `librosa_structure_baseline`
- Library: librosa 0.11.0 in the evaluation environment
- Parameters: 512-sample hop, eight-frame comparison window, 4 s minimum
  spacing, 0.2 peak threshold
- Implementation: `evaluation/structure_librosa.py`

## Runtime smoke: `tests/fixtures/real-piano.m4a`

Executed locally on 2026-08-27 using `librosa.load(..., sr=None, mono=True)`:

- decoded duration: 54.528 s
- CENS frames: 5,113
- recurrence density: 0.02067
- proposed transition times (s): 1.664, 10.656, 15.040, 24.853, 34.816,
  40.779, 51.957

This fixture has no structural reference annotation and is explicitly marked
qualitative-only in `evaluation/corpora/oss_bakeoff_qualitative_v1.json`.
Therefore the run establishes only decode/runtime behavior, not boundary
accuracy or musical usefulness.

## Benchmark status

SALAMI's public annotation repository is CC0 and supplies human structural
annotations: <https://github.com/DDMAL/salami-data-public>.  However, its
README explicitly says the matching audio cannot be redistributed; audio must
be obtained lawfully and mapped to the annotations before evaluation.  No such
verified audio/annotation pairing exists in this repository, so this baseline
has **no quantitative boundary F1/precision/recall result**.

## Product gate

**Not cleared.**  Keep this module evaluation-only and do not add it to the
capability registry, API, Inspector, annotation timeline, or Ask.  A candidate
promotion needs a versioned, legally accessible audio-plus-annotation corpus,
a reproducible boundary metric run against it, a comparison against an
appropriate baseline, and product withholding behavior.
