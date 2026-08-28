# Analysis V3 Audio-Language Grounded QA — Reference/Feasibility Stage

hello-ai base commit: `19fe23a765d6b80ce099be428e46f701cf97c828`

## Executive decision

**No audio-language model should become a production fact source.**

This stage supports a narrower architecture decision: continue a **research-only, evidence-grounded multimodal Ask path** where raw-audio semantic reasoning is evaluated as an optional input beside trusted specialized evidence.

| Candidate | Checkpoint | License / deployment constraint | Current evidence | Decision |
|---|---|---|---|---|
| Music Flamingo | `nvidia/music-flamingo-2601-hf` | 16.5 GB, NVIDIA OneWay Noncommercial; upstream tested on A100 80 GB | strongest music-specialized semantic candidate; no hello-ai grounded run | RESEARCH |
| Audio Flamingo 3 | `nvidia/audio-flamingo-3-hf` | 16.5 GB, NVIDIA OneWay Noncommercial; 10-minute cap | general audio-language control; MUSE exposes music-perception weaknesses | RESEARCH |
| Qwen2.5-Omni | `Qwen/Qwen2.5-Omni-7B` | 22.4 GB, Apache-2.0; heavy GPU-oriented checkpoint | permissive baseline, but MUSE reports near-chance behavior on several tasks | REVISIT |
| LLark | no released checkpoint | Apache-2.0 code; no official trained weights | architecture/evaluation reference only | REVISIT |

There is no `ADOPT` decision in this stage.

## What is measured here

No large audio-language checkpoint is run by this PR. The stage contributes:

- exact candidate/checkpoint/license/runtime metadata from official upstream sources;
- reference benchmark conclusions from CMI-Bench and MUSE;
- a deterministic claim-level scoring contract for future model runs;
- a fixed hello-ai question manifest;
- a non-composite gate for deciding whether raw audio adds grounded value over evidence-only Ask.

Any future local model measurement must be stored separately with model version/checksum, hardware, audio IDs/spans, prompts, generation settings, raw response, and manual annotation provenance.

## Checkpoint-specific operational findings

### Music Flamingo — RESEARCH

The current Hugging Face Transformers checkpoint is an 8B, ~16.5 GB model using a Qwen2.5-7B language backbone. The current Transformers/model-card path supports up to 20 minutes of audio; this supersedes older project-page descriptions of an approximately 15-minute receptive field. NVIDIA reports A100 80 GB as test hardware. We have not measured hello-ai CPU/GPU latency or memory.

The released weights use the NVIDIA OneWay Noncommercial License. That alone prevents this checkpoint from being a default commercial production dependency, even if research quality is high.

### Audio Flamingo 3 — RESEARCH

The current HF checkpoint is ~16.5 GB and uses a Qwen2.5-7B backbone. It processes 30-second audio windows with a 10-minute total cap; longer inputs are truncated. The weights are NVIDIA OneWay Noncommercial.

AF3 is useful as the general audio-language control, but MUSE reports AF3 at or near chance on several fundamental music-perception/relational tasks. It cannot be treated as an exact musical fact engine.

### Qwen2.5-Omni-7B — REVISIT

The official checkpoint is 22.4 GB and Apache-2.0. That licensing is much more compatible with a future product than the NVIDIA candidates, but licensing alone is not enough: MUSE reports Qwen2.5-Omni at or near chance on several core music-perception tasks, and the checkpoint is heavier than the NVIDIA 7B/8B candidates. No hello-ai audio-only runtime is measured here.

### LLark — REVISIT

The official Spotify repository is Apache-2.0 but explicitly says the paper is not accompanied by trained models. Retraining is outside this bakeoff. LLark remains a useful historical design/evaluation reference, not a runnable candidate.

## Reference benchmark findings

### CMI-Bench — exact MIR warning

CMI-Bench (ISMIR 2025) reformulates 14 traditional MIR task families across 20 datasets into open-ended instruction following while retaining task-standard MIR metrics. Its experiments report significant gaps between audio-text LLMs and specialized supervised systems, together with cultural, chronological, and gender biases.

Product implication: an audio-language model does **not** inherit authority over beat/downbeat, key, pitch/melody, instrument, tagging, or similar exact facts merely because it can answer questions about them.

### MUSE — relational reasoning warning

MUSE evaluates 10 fundamental music-perception and auditory-relational tasks against a 200-person human baseline. It reports a persistent human gap, with Qwen2.5-Omni and Audio Flamingo 3 at or near chance on several tasks; chain-of-thought prompting is inconsistent and often detrimental.

Product implication: before/after, same/different, pitch/rhythm/timbre relation claims from an audio LLM remain hypotheses unless grounded by other evidence or separately validated.

## hello-ai grounded comparison

The product-specific experiment is not `which model writes the nicest paragraph?` It is:

```text
same question
  ├─ audio only
  ├─ structured hello-ai evidence only
  └─ audio + structured hello-ai evidence
```

Human/manual annotation partitions each answer into supported, contradicted, and unsupported claims and checks evidence references, abstention, temporal localization, usefulness, and specificity.

`audio_plus_evidence` passes the deterministic grounded-value gate only if it:

- increases supported-claim rate;
- increases human usefulness;
- does not increase contradiction rate;
- does not increase unsupported-claim rate;
- does not reduce citation recall/precision where citations are expected;
- does not reduce abstention accuracy;
- does not reduce temporal-grounding accuracy where localization is required;
- does not reduce specificity.

There is deliberately no weighted composite that can hide a hallucination regression behind prettier prose.

## Proposed SemanticHypothesis contract

Schema proposal only; #336 owns persistence.

```typescript
type SemanticHypothesis = {
  model: string
  modelVersion: string
  scope: "work" | "segment" | "comparison"
  span?: { startSeconds: number; endSeconds: number }
  promptClass: string
  statement: string
  supportRefs: string[]
  contradictionRefs?: string[]
  verification: "unverified" | "evidence_consistent" | "evidence_conflicted"
  provenance: Record<string, unknown>
}
```

A `SemanticHypothesis` is intentionally not the same class as a measured Observation or evaluated MIR fact.

## Architecture recommendation

Keep the current Ask principle: **the LLM is an explainer over evidence, not a detector-of-record.** Research whether a music audio-language model can add useful semantic information when raw audio is supplied alongside evidence.

Recommended future path:

```text
specialized MIR / symbolic evidence ─────┐
foundation / stem / context evidence ────┼─→ evidence-grounded reasoning / explanation
raw audio semantic model ─────────────────┘
```

Not:

```text
audio → one audio LLM → all musical facts
```

## Next gate for #339

1. Run Music Flamingo first in an isolated GPU research environment on the fixed question manifest and a small rights-safe corpus.
2. Run the same cases as `audio_only`, `evidence_only`, and `audio_plus_evidence` with identical generation settings.
3. Blind/manual claim-level annotation; never self-grade with the tested model.
4. Compare against exact specialized evidence for localized MIR questions and against MUSE/CMI-Bench conventions where applicable.
5. If Music Flamingo does not clear the grounded-value gate, do not spend product effort integrating an audio-language layer merely because it is semantically fluent.
6. Keep #339 open until at least one real checkpoint run exists; this reference/feasibility stage is not completion.
