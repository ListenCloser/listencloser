# Analysis V3: Foundation Representation Bakeoff

Evaluation harness for benchmarking music foundation representations for similarity, retrieval, and downstream MIR.

## Quick Start

```bash
# Run all tasks for a single candidate
python -m backend.evaluation.analysis_v3.foundation.run --candidate mert

# Run only operational metrics
python -m backend.evaluation.analysis_v3.foundation.run --candidate mert --task operational

# Run all candidates
python -m backend.evaluation.analysis_v3.foundation.run --candidate all

# Use GPU if available
python -m backend.evaluation.analysis_v3.foundation.run --candidate mert --device cuda
```

## Candidates

| Candidate | Model ID | Audio | Text | Symbolic | License (Weights) |
|---|---|---|---|---|---|
| MERT | m-a-p/MERT-v1-95M | ✓ | ✗ | ✗ | CC-BY-NC-SA-4.0 |
| MuQ | OpenMuQ/MuQ-large-msd-iter | ✓ | ✗ | ✗ | CC-BY-NC-4.0 |
| MusicFM | minzwon/MusicFM | ✓ | ✗ | ✗ | CC-BY-NC-SA-4.0 |
| CLaMP3 | microsoft/clamp3 | ✓ | ✓ | ✓ | MIT |
| CLAP | laion/larger_clap_music | ✓ | ✓ | ✗ | MIT |

## Evaluation Tasks

1. **Operational**: Install, load, latency, memory, determinism
2. **Within-work similarity**: Segment-to-segment similarity within synthetic probes
3. **Cross-work similarity**: Similarity across different musical organizations
4. **Text retrieval**: Text-to-audio retrieval for text-capable models
5. **Cross-representation**: Audio↔MIDI alignment for symbolic-capable models

## Manifests

- `diversity_probe.json`: Synthetic audio probes spanning different musical organizations
- `product_queries.json`: Neutral factual text prompts for retrieval
- `aligned_representation_probe.json`: Audio/MIDI aligned pairs for CLaMP3 testing

## Results

Results are saved to `results/{candidate}.json` with machine-readable evaluation output.

## License

Code: MIT
Model weights: See individual candidate licenses above.
