# AMT engine bakeoff — Basic Pitch vs ByteDance piano transcription

Run date: 2026-08-12
Corpus: BabySlakh isolated piano stems (oracle setup), 4 clips with reference notes
Metric: onset F1 (pitch+onset) and note F1 (pitch+onset+offset), strict 50 ms

## Environment

- Python 3.9, CPU (no GPU)
- Basic Pitch 0.4.0 (Spotify, general polyphonic AMT — production baseline)
- ByteDance high-resolution piano transcription (`piano_transcription_inference`
  0.0.6), model `Note_pedal`, checkpoint ~165 MB, trained on MAESTRO v2
  (solo piano), Apache 2.0
- Note: `piano_transcription_inference` repo (bytedance/piano_transcription) is
  archived (Dec 2025); the inference package is published by the first author.

## Candidate engines considered

| Engine | Disposition | Reason |
|--------|-------------|--------|
| Basic Pitch | **ran** | baseline (general polyphonic) |
| ByteDance piano | **ran** | piano specialist, CPU, public checkpoint |
| MT3 (Google) | rejected | TensorFlow/t5x, heavy deps, no lightweight CPU checkpoint path verified |
| Omnizart | rejected | research codebase, unmaintained, TensorFlow-era |
| Onsets & Frames (Magenta) | rejected | TF1-era, archived, superseded |

## Aggregate results (piano stems, 4 clips)

| Engine | Onset F1 | Note F1 | Excessive rate | Missed rate |
|--------|----------|---------|----------------|-------------|
| Basic Pitch | 0.7249 | 0.1071 | 0.1694 | 0.2686 |
| ByteDance piano | **0.8394** | **0.5144** | 0.2107 | 0.0934 |

## Per-clip (onset F1 / note F1)

| Clip | ref | Basic Pitch | ByteDance piano |
|------|-----|-------------|-----------------|
| Track00001/S02 | 50 | 0.79 / 0.04 | 0.96 / 0.79 |
| Track00003/S00 | 174 | 0.85 / 0.12 | 0.96 / 0.76 |
| Track00005/S02 | 51 | 0.85 / 0.02 | 0.95 / 0.04 |
| Track00005/S06 | 144 | 0.40 / 0.25 | 0.48 / 0.47 |

## Reference baseline (recomputed in #203/#204, same environment)

| Category | Engine | Onset F1 | Note F1 |
|----------|--------|----------|---------|
| guitar (GuitarSet) | Basic Pitch | 0.7294 | 0.4281 |
| full mix (BabySlakh) | Basic Pitch | 0.3157 | 0.0681 |

## Findings

1. **ByteDance piano materially outperforms Basic Pitch on isolated piano.**
   Onset F1 +0.11 (0.72 → 0.84), note F1 +0.41 (0.11 → 0.51) — far above the
   +0.10 "meaningful" threshold.
2. **The note-duration gap is dramatically reduced.** This directly addresses
   the PR #203 finding that Basic Pitch's durations were the notation bottleneck.
   On piano, ByteDance recovers note durations far better (note F1 0.51 vs 0.11).
3. **The gain is piano-specific.** ByteDance is trained on MAESTRO solo piano and
   cannot process guitar or full mix. Basic Pitch remains the only general
   candidate.
4. **One clip (Track00005/S02) is hard for both** — both engines reach note F1
   ~0.02–0.04, suggesting that stem has content (sustained/rolled chords?) that
   neither duration model handles.
5. **Full-mix remains unsolved** — neither engine helps mixtures; #204 showed
   separation doesn't rescue it either.

## Decision

1. **Does any OSS engine materially outperform Basic Pitch?** Yes — ByteDance
   piano, on piano material (+0.11 onset, +0.41 note F1).
2. **Does the winner differ by material?** Yes — ByteDance wins on isolated
   piano only; it is inapplicable to guitar/full mix.
3. **Does any model materially improve note durations?** Yes — ByteDance on
   piano (note F1 0.11 → 0.51).
4. **Is the gain worth its cost?** On piano: yes (modest latency +0.2s→~6s per
   clip, ~165 MB checkpoint, CPU-friendly). On other material: N/A.
5. **Should production remain Basic Pitch, switch, or route?** Keep Basic Pitch
   as the general default; consider **engine routing** so piano-specialist input
   uses ByteDance. Do not switch globally.
6. **Next PR?** A piano-aware routing experiment: detect/route piano material to
   ByteDance while keeping Basic Pitch elsewhere — OR, if the product stays
   general-music, revisit duration reconstruction for Basic Pitch.

## Resource footprint

| Engine | Model size | 20 s clip runtime (CPU) |
|--------|-----------|--------------------------|
| Basic Pitch | ~small (bundled) | ~0.2 s |
| ByteDance piano | ~165 MB checkpoint | ~6 s |

## Scope

No production changes. Engines are isolated behind `evaluation.amt_engines`.
