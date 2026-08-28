# Analysis V3: Foundation Representation Bakeoff

## Executive Decision

**Recommendation: Do not add a production embedding layer yet.**

Current candidates do not clear all deployment/license/product-value gates simultaneously. CLaMP3 is the only candidate supporting audio, text, and symbolic modalities with a permissive license, but its cross-modal alignment quality (MRR=0.46, Recall@1=0.20) on real aligned MAESTRO pairs is insufficient for production without further investigation. CLAP provides fast audio-text retrieval with a permissive license.

## Evaluation Environment

- **Platform**: macOS-15.3.1-arm64-arm-64bit (Apple Silicon)
- **Arch**: arm64
- **Python**: 3.9.6
- **Device**: CPU (no GPU)
- **PyTorch**: 2.8.0
- **Transformers**: 4.57.6
- **hello-ai commit**: `50dfc75ea6e900dcca1b402d3b719c3912d93ad5`
- **Branch**: `eval/analysis-v3-foundation-bakeoff`

## Candidate Matrix

| Candidate | Exact Model | Code License | Weight License | Size | CPU Latency (10s) | CPU Latency (30s) | Segment Support | Audio-Text | Symbolic | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| MERT | m-a-p/MERT-v1-95M | MIT | CC-BY-NC-SA-4.0 | ~380MB | 0.36s | 1.24s | Temporal (768-dim@50Hz) | ✗ | ✗ | RESEARCH |
| MuQ | OpenMuQ/MuQ-large-msd-iter | MIT | CC-BY-NC-4.0 | ~400MB | 1.23s | 2.81s | Temporal (1024-dim) | ✗ | ✗ | RESEARCH |
| MusicFM | minzwon/MusicFM | MIT | CC-BY-NC-SA-4.0 | ~400MB | 0.69s | 2.55s | Temporal (1024-dim@25Hz) | ✗ | ✗ | RESEARCH |
| CLaMP3 | sander-wood/clamp3 | MIT | MIT | ~600MB | 1.67s | 2.90s | Global (768-dim) | ✓ | ✓ | RESEARCH |
| CLAP | laion/larger_clap_music | MIT | Apache-2.0 | ~200MB | 0.10s | 0.10s | Global (512-dim) | ✓ | ✗ | RESEARCH |

## Corpus and Manifests

### Real Music Diversity Probe (diversity_probe.json)

Uses real music from established research corpora:

| ID | Dataset | Source | License | Category |
|---|---|---|---|---|
| guitarset_bossa_nova | GuitarSet | 00_BN1-129-Eb_comp | CC BY 4.0 | guitar_accomp |
| guitarset_rock | GuitarSet | 00_Rock2-142-D_comp | CC BY 4.0 | guitar_accomp |
| guitarset_jazz | GuitarSet | 00_Jazz1-130-D_comp | CC BY 4.0 | guitar_accomp |
| maestro_classical_01 | MAESTRO v3.0.0 | 2004/...Track12 | CC BY-NC-SA 4.0 | solo_piano |
| maestro_classical_02 | MAESTRO v3.0.0 | 2008/...wav--2 | CC BY-NC-SA 4.0 | solo_piano |
| babyslakh_full_mix_01 | BabySlakh | Track00001 | CC BY 4.0 | full_mix |
| babyslakh_full_mix_02 | BabySlakh | Track00002 | CC BY 4.0 | full_mix |

### Within-Work Probe

- **Work**: MAESTRO piano recording (307.1s)
- **Windows**: 10s with 5s hop → 60 windows
- **Query windows**: 0s, 60s, 120s, 180s, 240s
- **License**: CC BY-NC-SA 4.0

### Product Queries (product_queries.json)

7 neutral factual text prompts: solo piano, prominent drums and bass, sparse vocal passage, dense distorted guitars, acoustic ensemble, electronic synthesizer, string quartet.

### Aligned Representation Probe (aligned_representation_probe.json)

Uses real MAESTRO aligned audio/MIDI pairs from the same work.

## Evaluation Methodology

Evidence classes used:
- **LOCAL MEASUREMENT**: CPU latency, load time, embedding dimension measured on this machine
- **REFERENCE BENCHMARK**: Published upstream results (cited, not measured locally)
- **QUALITATIVE PRODUCT Probe**: Within-work retrieval, cross-work similarity, text retrieval

## MERT

**Model**: m-a-p/MERT-v1-95M
**Upstream**: https://github.com/yizhilll/MERT
**Code License**: MIT
**Weight License**: CC-BY-NC-SA-4.0 (non-commercial)

### LOCAL MEASUREMENT

| Metric | Value |
|---|---|
| Install success | Yes |
| Load time | 3.59s |
| CPU latency 10s (median) | 0.36s |
| CPU latency 30s (median) | 1.24s |
| Embedding dim | 768 |
| Temporal | Yes (50Hz, 0.02s resolution) |
| Determinism | Stable |
| ARM feasibility | Confirmed (macOS ARM) |

### REFERENCE BENCHMARK

MERT has strong published results on MIR downstream tasks (per upstream paper). Not measured locally.

### QUALITATIVE PRODUCT PROBE

Within-work retrieval shows musically plausible nearest neighbors from the same MAESTRO piano recording. Windows from nearby temporal positions tend to rank higher.

### Decision: RESEARCH

Strong audio representation with temporal resolution. Non-commercial weight license blocks production adoption but does not eliminate research value.

## MuQ

**Model**: OpenMuQ/MuQ-large-msd-iter
**Upstream**: https://github.com/tencent-ailab/MuQ
**Code License**: MIT
**Weight License**: CC-BY-NC-4.0 (non-commercial)

### LOCAL MEASUREMENT

| Metric | Value |
|---|---|
| Install success | Yes (requires `muq` pip package) |
| Load time | 3.13s |
| CPU latency 10s (median) | 1.23s |
| CPU latency 30s (median) | 2.81s |
| Embedding dim | 1024 |
| Temporal | Yes (~40Hz) |
| Determinism | Stable |
| ARM feasibility | Confirmed (macOS ARM) |

### REFERENCE BENCHMARK

MuQ reports SOTA on various MIR tasks (per upstream paper). Not measured locally.

### Decision: RESEARCH

Large embeddings with temporal resolution. Non-commercial weight license blocks production adoption.

## MusicFM

**Model**: minzwon/MusicFM
**Upstream**: https://github.com/minzwon/musicfm
**Code License**: MIT
**Weight License**: CC-BY-NC-SA-4.0 (non-commercial)

### LOCAL MEASUREMENT

| Metric | Value |
|---|---|
| Install success | Yes (requires git clone + symlink) |
| Load time | 2.11s |
| CPU latency 10s (median) | 0.69s |
| CPU latency 30s (median) | 2.55s |
| Embedding dim | 1024 |
| Temporal | Yes (25Hz, 0.04s resolution) |
| Determinism | Stable |
| ARM feasibility | Confirmed (macOS ARM) |

### REFERENCE BENCHMARK

MusicFM (ICASSP 2024) reports strong results on music understanding tasks. Not measured locally.

### Decision: RESEARCH

Good temporal resolution. Non-commercial weight license and complex setup block production adoption.

## CLaMP3

**Model**: sander-wood/clamp3
**Upstream**: https://github.com/sanderwood/clamp3
**Code License**: MIT
**Weight License**: MIT

### LOCAL MEASUREMENT

| Metric | Value |
|---|---|
| Install success | Yes (requires git clone) |
| Load time | 7.15s |
| CPU latency 10s (median) | 1.67s |
| CPU latency 30s (median) | 2.90s |
| Embedding dim | 768 |
| Temporal | No (global embedding) |
| Text embedding dim | 768 |
| Determinism | Stable |
| ARM feasibility | Confirmed (macOS ARM) |

### Cross-Representation (LOCAL MEASUREMENT)

Method: Real MAESTRO aligned audio/MIDI pairs from the same work.

| Metric | Value |
|---|---|
| Num pairs | 5 |
| MRR | 0.46 |
| Recall@1 | 0.20 |
| Recall@5 | 1.00 |
| Mean rank | 3.0 |

Per-pair results:
- maestro_pair_0: rank=1, score=0.006
- maestro_pair_1: rank=2, score=-0.005
- maestro_pair_2: rank=3, score=0.004
- maestro_pair_3: rank=4, score=0.020
- maestro_pair_4: rank=5, score=-0.002

**Interpretation**: Cross-modal alignment is weak. Matched audio/MIDI pairs do not consistently rank above mismatched pairs. Only 1 of 5 matched pairs ranks first.

### MusicXML/Score Path

CLaMP3's official implementation supports MusicXML via preprocessing to interleaved ABC notation. However, the upstream checkpoint packaging separates audio (SAAS) and symbolic (C2) weights, making direct audio↔score comparison require loading separate checkpoint files. This complicates but does not prevent testing.

### REFERENCE BENCHMARK

CLaMP3 reports SOTA on cross-modal MIR tasks (per upstream paper). Not measured locally.

### Decision: RESEARCH

Only candidate with audio+text+symbolic support and MIT license. Cross-modal alignment quality is insufficient for production. Further investigation needed to determine whether the weak alignment is inherent to the model or specific to our test setup.

## CLAP

**Model**: laion/larger_clap_music
**Upstream**: https://github.com/LAION-AI/CLAP
**Code License**: MIT
**Weight License**: Apache-2.0

### Checkpoint Substitution

The specified checkpoint `music_audioset_epoch_15_esc_90.14.pt` from `lukewys/laion_clap` requires the full LAION CLAP codebase with dependencies (braceexpand, webdataset, wget, etc.) that are incompatible with the evaluation environment. `laion/larger_clap_music` is a HuggingFace Transformers-based CLAP model trained on music data, from the same research group. Both are music-specific CLAP checkpoints.

### LOCAL MEASUREMENT

| Metric | Value |
|---|---|
| Install success | Yes |
| Load time | 6.03s |
| CPU latency 10s (median) | 0.10s |
| CPU latency 30s (median) | 0.10s |
| Embedding dim | 512 |
| Temporal | No (global embedding) |
| Text embedding dim | 512 |
| Determinism | Stable |
| ARM feasibility | Confirmed (macOS ARM) |

### CLAP Latency Anomaly

The 10s and 30s latencies are identical (~0.10s). This is because CLAP's audio processor crops/pads input to a fixed duration (likely 10s) regardless of input length. The reported "30s latency" therefore represents processing of ~10s of actual audio content.

### REFERENCE BENCHMARK

CLAP reports strong audio-text retrieval results. Not measured locally.

### Decision: RESEARCH

Fastest inference with permissive license. Audio cropping behavior limits whole-track evaluation. Good candidate for audio-text retrieval in Ask/Inspector.

## Within-Work Retrieval (QUALITATIVE PRODUCT PROBE)

All candidates successfully embedded 60 windows from a 307s MAESTRO piano recording. Nearest-neighbor tables show that windows from temporally nearby positions tend to rank higher, suggesting the embeddings capture some musical continuity.

Example (MERT, query at 0s):
1. window_036_180s: 0.9815
2. window_004_20s: 0.9653
3. window_001_5s: 0.9652
4. window_008_40s: 0.9649
5. window_021_105s: 0.9603

## Cross-Work Retrieval (QUALITATIVE PRODUCT PROBE)

All candidates embedded 7 real music probes from GuitarSet, MAESTRO, and BabySlakh. Ranking behavior varies by candidate. Do not interpret absolute cosine ranges as discrimination quality—different models have different cosine-space geometries.

## Text Retrieval (QUALITATIVE PRODUCT PROBE)

Only CLaMP3 and CLAP support text retrieval. Both show weak text-to-audio alignment on the synthetic probes. Results are not conclusive due to the synthetic nature of the audio probes.

## Operational Scorecard

| Field | MERT | MuQ | MusicFM | CLaMP3 | CLAP |
|---|---|---|---|---|---|
| Exact model | m-a-p/MERT-v1-95M | OpenMuQ/MuQ-large-msd-iter | minzwon/MusicFM | sander-wood/clamp3 | laion/larger_clap_music |
| Upstream repo | yizhilll/MERT | tencent-ailab/MuQ | minzwon/musicfm | sanderwood/clamp3 | LAION-AI/CLAP |
| Code license | MIT | MIT | MIT | MIT | MIT |
| Weight license | CC-BY-NC-SA-4.0 | CC-BY-NC-4.0 | CC-BY-NC-SA-4.0 | MIT | Apache-2.0 |
| Install success | Yes | Yes | Yes | Yes | Yes |
| Load time | 3.59s | 3.13s | 2.11s | 7.15s | 6.03s |
| CPU latency 10s | 0.36s | 1.23s | 0.69s | 1.67s | 0.10s |
| CPU latency 30s | 1.24s | 2.81s | 2.55s | 2.90s | 0.10s* |
| Embedding dim | 768 | 1024 | 1024 | 768 | 512 |
| Temporal | Yes (50Hz) | Yes (~40Hz) | Yes (25Hz) | No | No |
| Text support | No | No | No | Yes | Yes |
| Symbolic support | No | No | No | Yes | No |
| Determinism | Stable | Stable | Stable | Stable | Stable |
| ARM feasibility | Confirmed | Confirmed | Confirmed | Confirmed | Confirmed |

*CLAP crops audio to fixed duration; 30s latency ≈ 10s latency.

## Licensing Findings

| Candidate | Code License | Weight License | Commercial Use |
|---|---|---|---|
| MERT | MIT | CC-BY-NC-SA-4.0 | ✗ Non-commercial |
| MuQ | MIT | CC-BY-NC-4.0 | ✗ Non-commercial |
| MusicFM | MIT | CC-BY-NC-SA-4.0 | ✗ Non-commercial |
| CLaMP3 | MIT | MIT | ✓ Commercial |
| CLAP | MIT | Apache-2.0 | ✓ Commercial |

## Failure Analysis

- **CLAP**: Original specified checkpoint requires incompatible dependencies; substituted with HuggingFace version
- **CLaMP3**: Weak cross-modal alignment (MRR=0.46) on real aligned pairs
- **MusicFM**: Complex setup (requires git clone + symlink)

## Decision Table

| Candidate | Decision | Rationale |
|---|---|---|
| MERT | RESEARCH | Strong audio representation, temporal resolution. Non-commercial license blocks production. |
| MuQ | RESEARCH | Large embeddings, temporal resolution. Non-commercial license blocks production. |
| MusicFM | RESEARCH | Good temporal resolution. Non-commercial license and complex setup block production. |
| CLaMP3 | RESEARCH | Only audio+text+symbolic with MIT license. Weak cross-modal alignment needs investigation. |
| CLAP | RESEARCH | Fastest, permissive license. Audio cropping limits whole-track eval. Good for audio-text. |

## Architecture Recommendation

**Do not add a production embedding layer yet.**

Rationale:
1. **License gate**: Only CLaMP3 and CLAP have permissive weight licenses
2. **Quality gate**: CLaMP3's cross-modal alignment is weak (MRR=0.46) on real aligned pairs
3. **Product value gate**: No candidate demonstrates clear product value over existing specialized MIR engines

**What should happen next**:
1. Investigate CLaMP3's weak cross-modal alignment—is this inherent or test-setup specific?
2. Evaluate CLAP for fast audio-text retrieval in Ask/Inspector
3. Design EmbeddingEvidence persistence in #336 after concrete requirements exist
4. Re-evaluate after investigation to determine if any candidate clears production gates

## Proposed EmbeddingEvidence Contract

```typescript
type EmbeddingEvidence = {
  model: string
  modelVersion: string
  modelChecksum?: string
  modality: "audio" | "midi" | "score" | "text"
  artifactVersionId: string
  span?: {
    startSeconds: number
    endSeconds: number
  }
  dimensionality: number
  normalized: boolean
  vectorRef: string
  provenance: {
    engine: string
    engineVersion?: string
    parameters?: Record<string, unknown>
  }
}
```

This contract is proposed for Architecture #336. Do not create DB tables or pgvector indexes.

## Reproduction Instructions

```bash
# Set cache directory for real music
export MUSIC_EVAL_CACHE_DIR=/path/to/backend/evaluation/.cache

# Run all candidates
python3 -m backend.evaluation.analysis_v3.foundation.run --candidate all

# Run specific candidate
python3 -m backend.evaluation.analysis_v3.foundation.run --candidate mert

# Run specific task
python3 -m backend.evaluation.analysis_v3.foundation.run --candidate mert --task operational

# Results are saved to backend/evaluation/analysis_v3/foundation/results/{candidate}.json
```
