# Analysis V3: Source Separation Bakeoff

Evaluation harness for benchmarking source separation models for downstream MIR value.

## Quick Start

```bash
# Run all tasks for a single candidate
python -m backend.evaluation.analysis_v3.separation.run --candidate bs_roformer

# Run only operational metrics
python -m backend.evaluation.analysis_v3.separation.run --candidate bs_roformer --task operational

# Run all candidates
python -m backend.evaluation.analysis_v3.separation.run --candidate all

# Use GPU if available
python -m backend.evaluation.analysis_v3.separation.run --candidate bs_roformer --device cuda
```

## Candidates

| Candidate | Model ID | Code License | Weight License | Stems |
|---|---|---|---|---|
| bs_roformer | lucidrains/BS-RoFormer | MIT | CC-BY-NC-SA-4.0 | 4 |
| demucs | facebookresearch/demucs | MIT | MIT | 4 |

## Evaluation Tasks

1. **Operational**: Install, load, latency, memory, determinism
2. **Separation**: Stem extraction quality on real music

## Manifests

- `diversity_probe.json`: Real music probes from GuitarSet and BabySlakh

## Results

Results are saved to `results/{candidate}.json` with machine-readable evaluation output.

## License

Code: MIT
Model weights: See individual candidate licenses above.
