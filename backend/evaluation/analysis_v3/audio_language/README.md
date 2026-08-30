# Analysis V3 Audio-Language Evaluation

Issue: #339  
Parent: #327

This directory is evaluation-only. It does **not** register an audio-language model in production, change Ask routing, add a GPU service, or persist model prose as factual `Insight` evidence.

## Decision boundary

The question is not whether one audio-language model can replace specialized MIR. The question is whether raw audio adds enough grounded semantic value to listencloser's existing evidence-driven Ask path to justify a separate research/semantic-hypothesis layer.

The evaluation therefore keeps two different test families separate:

1. **Exact / relational probes** (`manifests/task_probes.json`)
   - tempo, key, instrument presence, structure boundary, pitch direction;
   - MUSE-style before/after, same/different, relative pitch/rhythm/timbre;
   - scored with task-standard numeric/categorical metrics against case-provided ground truth.
2. **Grounded explanation benchmark** (`manifests/grounded_qa.json`)
   - compares `audio_only`, `evidence_only`, and `audio_plus_evidence` on the exact same case/question coverage;
   - human/manual claim-level annotation for support, contradiction, unsupported claims, evidence citations, abstention, temporal grounding, usefulness, and specificity;
   - never uses semantic usefulness ratings as a substitute for exact MIR accuracy.

## Trust gate

`audio_plus_evidence` only passes the grounded-value gate when it:

- evaluates the same case/question pairs as `evidence_only`;
- uses the same expected support references, abstention target, and temporal-grounding requirement for each compared pair;
- improves supported-claim rate and human-rated usefulness;
- does not worsen contradiction or unsupported-claim rate;
- does not worsen citation recall/precision when evidence citations are expected;
- does not worsen abstention accuracy;
- does not worsen temporal-grounding accuracy;
- does not worsen specificity.

There is deliberately no weighted composite that can hide a hallucination regression behind more fluent prose.

## Reproducibility

The required-CI path is checkpoint-free:

```bash
uv run --project backend python -m backend.evaluation.analysis_v3.audio_language.run --task reference
uv run --project backend pytest backend/tests/test_analysis_v3_audio_language.py
```

A future real checkpoint run starts from `schemas/model_run_template.json` and must retain:

- listencloser SHA;
- exact model/checkpoint revision and checksum when obtainable;
- code and weight licenses separately;
- hardware / Python / Torch / Transformers versions;
- peak RAM/VRAM and latency observations;
- deterministic generation settings and repeat information;
- rights-safe source dataset/item IDs, exact spans, and audio checksums;
- verbatim raw responses for all three conditions;
- blinded/manual annotation provenance.

The scorer rejects incomplete provenance, missing raw responses, duplicate raw cases, incomplete three-condition coverage, or assessments that do not exactly cover the retained responses.

## Current stage

This PR records upstream/reference evidence and evaluation contracts only. It performs no local Music Flamingo / Audio Flamingo 3 / Qwen2.5-Omni inference and makes no `ADOPT` claim.

The next #339 gate is an isolated rights-safe Music Flamingo research run if a legitimate GPU environment is available. If it is not available, record that blocker rather than changing production topology or inventing results.
