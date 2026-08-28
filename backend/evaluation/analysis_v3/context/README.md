# Analysis V3: Style, Instrumentation, and Semantic Context

Evaluation-only work for #333. Nothing in this directory changes production routing, `capabilities.json`, persistence, Inspector, or Ask.

## Product question

Can probabilistic style/instrument/context evidence usefully influence what hello-ai emphasizes without turning genre into a rigid product branch?

## Candidates in this stage

1. **Essentia Discogs-EffNet + MTG-Jamendo heads** — supervised reference candidate with published genre/instrument/mood-theme benchmarks. Licensing is research-friendly but not a free commercial-production path.
2. **LAION CLAP `laion/larger_clap_music`** — reuse the permissively licensed audio-text candidate already measured in #332; evaluate whether zero-shot factual labels are discriminative enough to justify further product work.

MuQ-MuLan remains a useful research reference, but its released weights are non-commercial and this stage does not need another heavyweight download to answer the immediate decision.

## Evidence classes

- `REFERENCE_BENCHMARK`: metrics published in official model metadata; not measured by hello-ai.
- `PRIOR_LOCAL_AND_REFERENCE_EVIDENCE`: reuse of committed #332 CLAP operational/retrieval results plus upstream references; performs no new model inference.
- `QUALITATIVE_PRODUCT_PROBE`: tiny rights-safe hello-ai probe over GuitarSet/MAESTRO with explicit coarse labels plus BabySlakh stability-only examples.

The tiny product probe is not an MTG-Jamendo benchmark and must not be presented as one.

## Reproduce without model downloads

```bash
cd backend
uv run python -m backend.evaluation.analysis_v3.context.run --task prior
```

This reads the already-committed #332 CLAP result and `reference_metrics.json`.

## Opt-in zero-shot probe

```bash
export MUSIC_EVAL_CACHE_DIR=/path/to/backend/evaluation/.cache
cd backend
uv run python -m backend.evaluation.analysis_v3.context.run --task zero-shot --device cpu
```

This requires the rights-safe cached audio referenced by `manifests/context_probe.json` and access to the CLAP checkpoint. It is intentionally excluded from required CI.

## Metrics

- precision@k
- recall@k
- label-ranking average precision
- adjacent-window top-k Jaccard as a **stability diagnostic only**
- prompt-ranking diversity diagnostic for the prior #332 CLAP text-retrieval result

Raw CLAP cosine similarities are recorded as `score`; they are **not** called confidence. High segment stability is also not treated as accuracy because a constant model can be stably wrong.

## Decision semantics

Each candidate gets `ADOPT`, `RESEARCH`, `REJECT`, or `REVISIT`. This stage does not authorize production exposure merely because a model is runnable.
