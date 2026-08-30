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
