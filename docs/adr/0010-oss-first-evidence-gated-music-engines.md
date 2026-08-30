# 0010: OSS-first, evidence-gated music engines

Status: accepted
Date: 2026-08-22

## Context

The product depends on multiple music-information-retrieval and symbolic-analysis capabilities: transcription, beat tracking, notation, harmony, melody, theory interpretation, and future structure/generation features.

Several historical failures came from promoting plausible-looking algorithm output before it had sufficient evaluation, maintaining custom logic where stronger OSS existed, or conflating component/oracle accuracy with end-to-end product accuracy.

At the same time, no single representation or engine is universally best. Audio-native chord recognition can outperform chordification of transcribed MIDI, while symbolic tooling can remain stronger for theory interpretation.

## Decision

1. Prefer credible OSS/research implementations before writing substantial custom music/ML algorithms.
2. Integrate engines behind normalized adapters so production code is not coupled to vendor-specific output.
3. Treat perception/detection and musical interpretation as separate stages when they solve different problems.
4. Graduate algorithmic capabilities through `DISCOVERY -> EVALUATION -> CANDIDATE -> PRODUCTION -> MONITORED`.
5. Keep component/oracle evaluation separate from end-to-end product evaluation.
6. Withhold unvalidated user-facing claims rather than invent defaults or confidence.
7. Preserve engine/model/data licensing and provenance as part of the production decision.
8. Custom algorithms should normally begin in evaluation tooling and require benchmark evidence before becoming a production engine.

## Evidence

Recent harmony work illustrates the intended pattern:
- symbolic music21 chord recognition was empirically weak on GuitarSet,
- an audio-native OSS engine (lv-chordia) materially improved chord recognition on chordal material,
- music21 remains valuable downstream for symbolic key/theory operations,
- cadence and key-region claims remain withheld when evaluation is inadequate.

The same policy should be applied to notation, melody, structure, transcription post-processing, and future generation/evaluation systems.

## Consequences

Benefits:
- lower bespoke maintenance burden,
- easier engine replacement and bakeoffs,
- clearer provenance and product truthfulness,
- fewer architecture decisions based on one fixture or one agent's intuition.

Costs:
- evaluation and adapter work becomes a required part of algorithm adoption,
- some capabilities may remain intentionally unavailable longer,
- research repositories may require environment/packaging work before they can be fairly evaluated.

## Revisit when

Reconsider this policy only if the product develops a sustained internal research program where proprietary/custom algorithms repeatedly and measurably outperform available OSS, with sufficient resources to maintain them.
