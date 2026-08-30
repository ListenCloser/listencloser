# OSS-first MIR evaluation policy

This policy refines the evaluation direction tracked by #636 and the repository OSS-first cleanup rule in #634.

## Presumption

For mature MIR problems with a credible maintained open-source implementation, OSS is the presumptive implementation. Repository-local implementations are legacy until they demonstrate a material, reproducible advantage.

Do not require OSS to defeat bespoke code before adoption. Instead:

1. verify the OSS implementation satisfies the required input/output contract;
2. verify license, maintenance, runtime, and deployment constraints;
3. run the smallest evaluation needed to detect a material regression where quality can differ;
4. adopt OSS unless bespoke code demonstrates a meaningful reproducible advantage on held-out or product-path evidence;
5. delete the bespoke implementation and obsolete tests/helpers/fallbacks.

For standard infrastructure such as canonical MIR metrics and supported dataset loaders, prefer the established OSS implementation directly after contract verification. Do not run ceremonial bakeoffs merely to justify deleting equivalent repository-local code.

## Initial decision matrix

Do not restart a broad model-zoo survey before these already-identified seams are resolved.

| Capability | Default/control | Candidate(s) to evaluate | Burden of proof |
| --- | --- | --- | --- |
| beat/downbeat | exact current production path | Beat This; BeatNet only where it adds decision value | custom/librosa path must justify surviving a credible OSS replacement |
| transcription | upstream Basic Pitch behavior | Transkun; Piano Transcription Inference where domain-appropriate | custom Basic Pitch postprocessing must prove incremental value rule-by-rule |
| Roman numeral / harmonic function | current production `theory_interpreter` | `music21` on the same trusted-key + root/quality contract | bespoke mapping survives only with measured same-contract advantage |
| cadence / local key region | withheld | none until a candidate earns re-entry | already-rejected heuristics stay deleted; do not replace them speculatively |
| structure | current product path / All-In-One where configured | additional maintained segmentation OSS only for a live decision | do not create another structure framework merely to compare tools |
| notation / performance-to-score | current stage-separated pipeline | `music21`, Partitura, MuseScore tooling by the responsibility each actually owns | bespoke quantization/normalization rules must prove product-specific value |

The matrix is intentionally bounded. Add a candidate only when it can plausibly change a production decision.

## Initial dataset policy

The repository currently has adapters for ASAP, BabySlakh, GuitarSet, MAESTRO, and Slakh. Treat them as task-specific evidence sources, not one interchangeable benchmark pool.

- **MAESTRO**: piano transcription/performance-MIDI evidence; record model-training overlap before claiming held-out performance.
- **ASAP**: performance-to-score, aligned symbolic, and beat/downbeat evidence for classical piano; its current adapter requires manual acquisition and does not claim an official train/test split.
- **GuitarSet**: real guitar transcription/rhythm evidence; do not treat a model's training corpus as held-out promotion evidence.
- **Slakh / BabySlakh**: useful multi-instrument and stage-isolation evidence; label synthetic audio explicitly rather than treating it as equivalent to real recordings.
- **Product fixtures**: regression/product-path evidence only; never silently promote them to a general MIR benchmark.

For the default Beat This checkpoints, use GTZAN or another independently held-out corpus for promotion evidence unless checkpoint-specific provenance establishes a valid alternative. Upstream Beat This documentation states that its main `final*` models were trained on all of its considered data except GTZAN and warns that evaluation on training datasets can be unfairly optimistic.

Dataset validity is per **candidate × checkpoint × split**, not a permanent property of a dataset. Every durable result must label training overlap / held-out status explicitly.

## Canonical dataset and metric tooling

Prefer `mirdata` for datasets it supports when its exact dataset version, annotation surface, and acquisition behavior satisfy the evaluation contract. Its purpose is reproducible MIR dataset access and it currently includes, among others, GuitarSet and MAESTRO. Do not delete a local adapter until that contract is verified; keep thin local handling only for gaps such as unsupported alignment/materialization requirements.

Prefer `mir_eval` for standard MIR scoring where its task semantics match the question. In particular, its beat evaluator provides canonical beat F-measure and additional established beat metrics; it also provides standard evaluators for chord, transcription, and segmentation tasks. Repository-local standard metric reimplementations should be deletion targets. Product-specific diagnostics may remain when they measure something the canonical MIR metric does not, such as latency, score readability/tie fragmentation, representation lineage, or downstream claim sensitivity.

## Custom heuristics layered over OSS

Evaluate each custom rule as an ablation:

```text
upstream OSS
vs
upstream OSS + custom rule
```

A custom heuristic survives only when it demonstrates incremental value on valid evidence. Otherwise delete it. Do not preserve disabled fallbacks "just in case."

## Minimal evaluation stack

Prefer a small, boring stack:

- canonical dataset tooling such as `mirdata` where it satisfies the exact dataset/version/annotation contract;
- canonical task metrics such as `mir_eval` where applicable;
- thin adapters that normalize production and candidate outputs onto the same contract;
- one small typed result/run schema;
- JSON durable evidence;
- ordinary tests for schema, normalization, and evidence-link validity.

Avoid introducing experiment databases, dashboards, custom orchestration engines, or one framework per task unless a concrete product/evaluation requirement proves they are necessary.

## Decision order

Prefer execution in this order:

1. delete duplicate standard metric/dataset infrastructure where OSS already owns the problem;
2. delete already-rejected heuristics/capabilities;
3. make upstream OSS the control for remaining algorithmic comparisons;
4. run only decision-producing evaluations;
5. preserve only common evaluation glue that proved necessary.

A successful evaluation cleanup may have negative net LOC. Benchmark count and report volume are not success metrics; production simplification and traceable decisions are.