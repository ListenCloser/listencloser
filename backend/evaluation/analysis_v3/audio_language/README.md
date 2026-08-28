# Analysis V3: Audio-Language Grounded QA

Evaluation-only work for #339. Nothing here registers a production model, changes `capabilities.json`, changes Ask routing, adds a GPU service, or persists model prose as musical fact.

## Product question

Does raw audio add enough value to hello-ai's existing evidence-grounded Ask architecture to justify a separate audio-language semantic layer?

The comparison is deliberately:

1. `audio_only`
2. `evidence_only`
3. `audio_plus_evidence`

The important gate is **audio+evidence vs evidence-only**, not whether a model can produce fluent music prose from raw audio.

## Current trust boundary

Production Ask already treats the LLM as an explainer over supplied evidence rather than a source of detected facts. This evaluation preserves that rule. Exact beat, pitch, chord, section, or other localized facts remain owned by evaluated specialized evidence unless an audio-language model separately clears a matched-task benchmark.

## First-round candidates

- Music Flamingo — `nvidia/music-flamingo-2601-hf`
- Audio Flamingo 3 — `nvidia/audio-flamingo-3-hf`
- Qwen2.5-Omni — `Qwen/Qwen2.5-Omni-7B`
- LLark — reference only; the official repository releases no trained checkpoint

Candidate/checkpoint metadata, licenses, model-file hashes where available, and benchmark references are recorded in `results/reference_evidence.json`.

## Evidence classes in this stage

- `REFERENCE_AND_OPERATIONAL_METADATA`: official model cards/repos; no hello-ai inference.
- `REFERENCE_BENCHMARK`: CMI-Bench and MUSE conclusions; no hello-ai inference.
- future `LOCAL_MODEL_MEASUREMENT`: only after an actual checkpoint run with exact model/version/hardware/audio/prompt provenance.

Do not relabel reference evidence as a local benchmark result.

## Required-CI-safe commands

From repository root:

```bash
uv run --project backend python -m backend.evaluation.analysis_v3.audio_language.run --task reference
uv run --project backend pytest -q backend/tests/test_analysis_v3_audio_language.py
```

These commands do not import or download any audio-language checkpoint.

## Scoring a future model run

A model-run artifact must first be manually annotated at claim level. Then:

```bash
uv run --project backend python -m backend.evaluation.analysis_v3.audio_language.run \
  --task score \
  --assessments /path/to/annotated_assessments.json
```

Each assessment records supported, contradicted, and unsupported claims; expected/cited evidence refs; abstention behavior; temporal-grounding correctness where applicable; and 1-5 human usefulness/specificity ratings.

`grounded_value_gate` intentionally avoids a weighted magic score. `audio_plus_evidence` passes only if it improves supported-claim rate and usefulness without worsening contradiction, unsupported claims, citation quality, abstention, temporal grounding, or specificity relative to `evidence_only`.

## Non-goals

- no raw model prose promoted to `Insight`
- no exact MIR authority from fluent answers
- no checkpoint downloads in CI
- no production dependency or topology changes
- no self-grading by the evaluated model
- no retraining LLark
- no claim that this stage completes #339
