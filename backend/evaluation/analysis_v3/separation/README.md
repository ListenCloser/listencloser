# Analysis V3: Source Separation Feasibility Bakeoff

Evaluation harness for a first-stage source-separation feasibility study under #334.

This PR measures whether candidate OSS systems can load and run in the current evaluation environment and whether they can emit the expected stem set on real audio. It does **not** yet establish objective separation quality or downstream MIR improvement.

## Quick Start

```bash
python -m backend.evaluation.analysis_v3.separation.run --candidate bs_roformer
python -m backend.evaluation.analysis_v3.separation.run --candidate bs_roformer --task operational
python -m backend.evaluation.analysis_v3.separation.run --candidate all
python -m backend.evaluation.analysis_v3.separation.run --candidate demucs --device cpu
```

## Candidates

| Candidate | Model ID | Code License | Weight License | Status |
|---|---|---|---|---|
| bs_roformer | lucidrains/BS-RoFormer | MIT | CC-BY-NC-SA-4.0 | REVISIT: evaluated package path blocked on Python 3.9 |
| demucs | facebookresearch/demucs / HTDemucs | MIT | MIT | RESEARCH: operationally runnable |

## What is actually evaluated

1. install/load feasibility
2. CPU latency/runtime feasibility
3. expected stem extraction shape on real GuitarSet/BabySlakh audio

## Not yet evaluated

- objective SDR/SIR/SAR or modern source-separation benchmark quality
- perceptual separation errors
- whether separation improves beat/downbeat, chord, melody/bass, or instrumentation analysis
- production routing/storage/UI

The metric/downstream modules include scaffolding for follow-up #334 work; placeholder functions returning `None` are not completed evidence.

## Manifests

- `diversity_probe.json`: real-music extraction smoke probes from GuitarSet and BabySlakh

## Results

Machine-readable feasibility results are saved to `results/{candidate}.json`.

See `REPORT.md` for the evidence boundary, decisions, and remaining #334 gates.
