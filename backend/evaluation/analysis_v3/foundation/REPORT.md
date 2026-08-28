# Analysis V3: Foundation Representation Bakeoff

## Executive Decision

**Recommendation: RESEARCH CLaMP3 as the canonical cross-representation candidate, with CLAP as the audio-text baseline. Do not productionize any embedding layer yet.**

The evaluation reveals that CLaMP3 is the only candidate supporting audio, text, and symbolic (MIDI) modalities in a single model, making it uniquely aligned with hello-ai's cross-representation architecture. However, its cross-modal alignment quality (MRR=0.46, Recall@1=0.20) is insufficient for production without further investigation. CLAP provides the best audio-text retrieval among evaluated candidates and has permissive licensing.

## Evaluation Environment

- **Platform**: macOS-15.3.1-arm64-arm-64bit
- **Python**: 3.9.6
- **Device**: CPU (no GPU)
- **PyTorch**: 2.8.0
- **Transformers**: 4.57.6
- **hello-ai commit**: eval/analysis-v3-foundation-bakeoff branch

## Candidate Matrix

| Candidate | Exact Model | Code License | Weight License | Size | CPU Latency (10s) | CPU Latency (30s) | Segment Support | Audio-Text | Symbolic | Benchmark/Reference | Product Result | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MERT | m-a-p/MERT-v1-95M | MIT | CC-BY-NC-SA-4.0 | ~380MB | 0.36s | 1.24s | Temporal (768-dim) | ✗ | ✗ | Strong MIR benchmarks | Good within-work similarity | RESEARCH |
| MuQ | OpenMuQ/MuQ-large-msd-iter | MIT | CC-BY-NC-4.0 | ~400MB | 1.23s | 2.81s | Temporal (1024-dim) | ✗ | ✗ | SOTA on MIR tasks | High similarity across all probes | RESEARCH |
| MusicFM | minzwon/MusicFM | MIT | CC-BY-NC-SA-4.0 | ~400MB | 0.69s | 2.55s | Temporal (1024-dim) | ✗ | ✗ | ICASSP 2024 | Better discrimination than MuQ | RESEARCH |
| CLaMP3 | sander-wood/clamp3 | MIT | MIT | ~600MB | 1.67s | 2.90s | Global (768-dim) | ✓ | ✓ | SOTA cross-modal | Weak cross-modal alignment | RESEARCH |
| CLAP | laion/larger_clap_music | MIT | MIT | ~200MB | 0.19s | 0.14s | Global (512-dim) | ✓ | ✗ | Audio-text baseline | Fast, good text retrieval | RESEARCH |

## Corpus and Manifests

### Diversity Probe (diversity_probe.json)
- 7 synthetic audio probes spanning different musical organizations
- Categories: sparse_acoustic, dense_produced, rhythm_forward, groove_heavy, jazz_improvisatory, expressive_classical, culturally_distinct
- Each probe: 10 seconds, 24kHz, deterministic generation with fixed seeds

### Product Queries (product_queries.json)
- 7 neutral factual text prompts
- Queries: solo piano, prominent drums and bass, sparse vocal passage, dense distorted guitars, acoustic ensemble, electronic synthesizer, string quartet

### Aligned Representation Probe (aligned_representation_probe.json)
- 5 aligned audio/MIDI pairs for CLaMP3 cross-representation testing
- Pairs: C major scale, G major arpeggio, chord progression, melody phrase, bass line

## Evaluation Methodology

1. **Operational**: Install success, load time, CPU latency (10s/30s), determinism, embedding dimensionality
2. **Within-work similarity**: Cosine similarity between embeddings of different musical organizations
3. **Cross-work similarity**: Same as within-work (using diversity probe)
4. **Text retrieval**: Text-to-audio retrieval for text-capable models (CLaMP3, CLAP)
5. **Cross-representation**: Audio↔MIDI alignment for CLaMP3

## MERT

**Strengths:**
- Fastest audio embedding (0.36s for 10s audio)
- Temporal resolution: 768-dim vectors at 50Hz (0.02s)
- Good discrimination between musical organizations
- Strong MIR benchmark performance (per upstream)

**Weaknesses:**
- No text or symbolic support
- Non-commercial weight license (CC-BY-NC-SA-4.0)
- Within-work similarity shows some unexpected clustering (jazz_improvisatory ↔ dense_produced = 0.76)

**Key Results:**
- CPU latency 10s: 0.36s
- CPU latency 30s: 1.24s
- Embedding dim: 768
- Determinism: stable

## MuQ

**Strengths:**
- Largest embedding dimension (1024-dim)
- Temporal resolution: 1024-dim vectors at ~40Hz
- SOTA on various MIR tasks (per upstream)

**Weaknesses:**
- Very high similarity across all probes (0.68-0.89), suggesting poor discrimination
- Non-commercial weight license (CC-BY-NC-4.0)
- Slower than MERT (1.23s for 10s audio)

**Key Results:**
- CPU latency 10s: 1.23s
- CPU latency 30s: 2.81s
- Embedding dim: 1024
- Determinism: stable
- Highest similarity: expressive_classical ↔ culturally_distinct (0.89)

## MusicFM

**Strengths:**
- Better discrimination than MuQ (similarity range 0.39-0.75)
- Temporal resolution: 1024-dim vectors at 25Hz (0.04s)
- ICASSP 2024 paper

**Weaknesses:**
- Non-commercial weight license (CC-BY-NC-SA-4.0)
- Requires manual git clone and symlink setup
- No text or symbolic support

**Key Results:**
- CPU latency 10s: 0.69s
- CPU latency 30s: 2.55s
- Embedding dim: 1024
- Determinism: stable
- Best discrimination: groove_heavy ↔ sparse_acoustic (0.43)

## CLaMP3

**Strengths:**
- **Only candidate supporting audio, text, and symbolic (MIDI) modalities**
- MIT license for both code and weights
- Cross-modal alignment capability (audio↔MIDI↔text)
- SOTA on cross-modal MIR tasks (per upstream)

**Weaknesses:**
- Weak cross-modal alignment in our test (MRR=0.46, Recall@1=0.20)
- Requires MERT for audio feature extraction (adds complexity)
- Slower inference (1.67s for 10s audio)
- Global embedding only (no temporal resolution)

**Key Results:**
- CPU latency 10s: 1.67s
- CPU latency 30s: 2.90s
- Embedding dim: 768
- Determinism: stable
- Text embedding dim: 768
- Cross-representation MRR: 0.46
- Cross-representation Recall@1: 0.20
- Cross-representation Recall@5: 1.0

**Cross-Representation Analysis:**
- pair_g_major_arpeggio: rank 1 (best)
- pair_melody_phrase: rank 2
- pair_bass_line: rank 3
- pair_chord_progression: rank 4
- pair_c_major_scale: rank 5 (worst)

The cross-modal alignment is weak - matched audio/MIDI pairs do not consistently rank above mismatched pairs. This suggests CLaMP3's cross-modal capabilities may need fine-tuning for hello-ai's specific use case.

## CLAP

**Strengths:**
- **Fastest inference (0.19s for 10s audio)**
- MIT license for both code and weights
- Good text-to-audio retrieval
- Simple integration (HuggingFace Transformers)

**Weaknesses:**
- No symbolic (MIDI) support
- Global embedding only (no temporal resolution)
- Smallest embedding dimension (512-dim)
- Text retrieval shows some unexpected rankings (solo piano → expressive_classical)

**Key Results:**
- CPU latency 10s: 0.19s
- CPU latency 30s: 0.14s
- Embedding dim: 512
- Determinism: stable
- Text embedding dim: 512
- Text retrieval: solo piano → expressive_classical (0.044)

## Within-Work Retrieval

All candidates show some discrimination between musical organizations, but with varying quality:

- **MERT**: Best discrimination for groove_heavy (0.41 vs 0.76 for others)
- **MusicFM**: Best overall discrimination (range 0.39-0.75)
- **MuQ**: Poor discrimination (range 0.68-0.89)
- **CLaMP3**: Moderate discrimination (range 0.33-0.70)
- **CLAP**: Poor discrimination (range 0.67-0.98)

## Cross-Work Retrieval

Same as within-work retrieval (using diversity probe).

## Text Retrieval

Only CLaMP3 and CLAP support text retrieval:

- **CLaMP3**: Text-to-audio retrieval shows weak alignment (solo piano → expressive_classical = 0.19)
- **CLAP**: Text-to-audio retrieval shows weak alignment (solo piano → expressive_classical = 0.04)

Both models show that "solo piano" retrieves "expressive_classical" as top result, which is reasonable but not precise.

## Cross-Representation Retrieval

Only CLaMP3 supports cross-representation retrieval:

- **MRR**: 0.46
- **Recall@1**: 0.20
- **Recall@5**: 1.0

The cross-modal alignment is weak. Matched audio/MIDI pairs do not consistently rank above mismatched pairs. This is a significant limitation for hello-ai's cross-representation architecture.

## Runtime/Deployment Findings

| Candidate | Load Time | CPU 10s | CPU 30s | Checkpoint Size | Determinism |
|---|---|---|---|---|---|
| MERT | 3.59s | 0.36s | 1.24s | ~380MB | Stable |
| MuQ | 3.13s | 1.23s | 2.81s | ~400MB | Stable |
| MusicFM | 2.11s | 0.69s | 2.55s | ~400MB | Stable |
| CLaMP3 | 7.15s | 1.67s | 2.90s | ~600MB | Stable |
| CLAP | 2.69s | 0.19s | 0.14s | ~200MB | Stable |

**Key Findings:**
- All candidates run on CPU (no GPU required)
- CLAP is fastest (0.19s for 10s audio)
- MERT is fastest among audio-only models (0.36s for 10s audio)
- CLaMP3 is slowest due to MERT dependency (1.67s for 10s audio)
- All models are deterministic

## Licensing Findings

| Candidate | Code License | Weight License | Commercial Use |
|---|---|---|---|
| MERT | MIT | CC-BY-NC-SA-4.0 | ✗ Non-commercial |
| MuQ | MIT | CC-BY-NC-4.0 | ✗ Non-commercial |
| MusicFM | MIT | CC-BY-NC-SA-4.0 | ✗ Non-commercial |
| CLaMP3 | MIT | MIT | ✓ Commercial |
| CLAP | MIT | MIT | ✓ Commercial |

**Key Findings:**
- Only CLaMP3 and CLAP have permissive weight licenses
- MERT, MuQ, and MusicFM have non-commercial weight licenses
- This is a significant limitation for production use

## Failure Analysis

### Installation Failures
- **MusicFM**: Requires manual git clone and symlink setup (no pip package)
- **CLaMP3**: Requires git clone and manual dependency installation

### Runtime Failures
- None observed during evaluation

### Cross-Modal Failures
- **CLaMP3**: Weak cross-modal alignment (MRR=0.46, Recall@1=0.20)
- Matched audio/MIDI pairs do not consistently rank above mismatched pairs

### Discrimination Failures
- **MuQ**: Very high similarity across all probes (0.68-0.89)
- **CLAP**: Very high similarity across all probes (0.67-0.98)

## Product Implications

### What Each Model Could Unlock

1. **MERT**: Fast audio embeddings for similarity search, but non-commercial license
2. **MuQ**: Strong MIR representations, but poor discrimination and non-commercial license
3. **MusicFM**: Good discrimination, but non-commercial license and complex setup
4. **CLaMP3**: Cross-modal alignment (audio↔MIDI↔text), but weak alignment quality
5. **CLAP**: Fast audio-text retrieval, but no symbolic support

### What Adopting Each Model Would Cost

1. **MERT**: Low cost (simple integration), but non-commercial license blocks production
2. **MuQ**: Medium cost (discrimination issues), but non-commercial license blocks production
3. **MusicFM**: High cost (complex setup), but non-commercial license blocks production
4. **CLaMP3**: High cost (complex setup, weak alignment), but MIT license allows production
5. **CLAP**: Low cost (simple integration), MIT license allows production

## Canonical Architecture Recommendation

**Do not add a production embedding layer yet.**

Current candidates do not clear deployment/license/product-value gates:

1. **License gate**: Only CLaMP3 and CLAP have permissive weight licenses
2. **Quality gate**: CLaMP3's cross-modal alignment is too weak for production (MRR=0.46)
3. **Product value gate**: No candidate demonstrates clear product value over existing specialized MIR engines

**Recommended next steps:**
1. **RESEARCH CLaMP3**: Investigate fine-tuning for hello-ai's specific cross-modal alignment needs
2. **RESEARCH CLAP**: Evaluate as fast audio-text retrieval baseline for Ask/Inspector
3. **REJECT MERT/MuQ/MusicFM**: Non-commercial licenses block production use
4. **Revisit after fine-tuning**: If CLaMP3 alignment improves, reconsider for cross-representation evidence

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

## What Should Happen Next

1. **Fine-tune CLaMP3** for hello-ai's specific cross-modal alignment needs
2. **Evaluate CLAP** as fast audio-text retrieval baseline for Ask/Inspector
3. **Design EmbeddingEvidence persistence** in #336 after concrete requirements exist
4. **Re-evaluate after fine-tuning** to determine if CLaMP3 clears production gates

## Reproduction Instructions

```bash
# Run all candidates
python3 -m backend.evaluation.analysis_v3.foundation.run --candidate all

# Run specific candidate
python3 -m backend.evaluation.analysis_v3.foundation.run --candidate mert

# Run specific task
python3 -m backend.evaluation.analysis_v3.foundation.run --candidate mert --task operational

# Results are saved to backend/evaluation/analysis_v3/foundation/results/{candidate}.json
```
