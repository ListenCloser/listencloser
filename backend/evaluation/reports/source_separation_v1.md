# Source separation vs direct transcription — BabySlakh full mixes

Run date: 2026-08-12
Corpus: 5 BabySlakh tracks (Track00001–Track00005), 20 s excerpts
Engine: Demucs htdemucs 4.0.1 + Basic Pitch (onset=0.5, frame=0.3)

## Environment

- Library: demucs 4.0.1 (maintained fork: adefossez/demucs)
- Model: htdemucs (hybrid transformer)
- License: MIT (library + model)
- Model download: ~80 MB
- Device: CPU (macOS, no GPU)
- Separation latency: ~7 s per 20 s clip

## Metric semantics

- **onset F1** = onset-only match (pitch + onset ≤ 50 ms)
- **note F1** = onset+offset match (pitch + onset + offset ≤ 50 ms) — strict

These are internal strict metrics, not directly comparable to all AMT literature.

## Aggregate results (5 clips)

| Pipeline | Onset F1 | Note F1 | Excessive rate | Missed rate |
|----------|----------|---------|----------------|-------------|
| mixture (baseline) | 0.3157 | 0.0681 | 0.6534 | 0.6963 |
| other-only | 0.3230 | 0.0732 | 0.6096 | 0.7093 |
| vocals+other (raw) | 0.3116 | 0.0697 | 0.6643 | 0.6742 |
| vocals+other (dedup) | 0.3119 | 0.0711 | 0.6525 | 0.6862 |
| all-pitched (raw) | 0.3308 | 0.0826 | 0.6803 | 0.6214 |
| all-pitched (dedup) | 0.3372 | 0.0853 | 0.6541 | 0.6375 |
| **oracle stems (raw)** | **0.4233** | **0.1155** | 0.6030 | 0.5248 |
| oracle stems (dedup) | 0.4099 | 0.1105 | 0.5896 | 0.5706 |

## Per-clip (onset F1 / note F1)

| Track | baseline | other | voc+other | all-pitched | oracle |
|-------|----------|-------|-----------|-------------|--------|
| Track00001 | 0.4012 / 0.0880 | 0.4138 / 0.0964 | 0.4017 / 0.0967 | 0.4287 / 0.1072 | 0.4769 / 0.1373 |
| Track00002 | 0.1352 / 0.0106 | 0.1354 / 0.0133 | 0.1396 / 0.0143 | 0.1398 / 0.0150 | 0.2897 / 0.0575 |
| Track00003 | 0.4183 / 0.1033 | 0.4234 / 0.1052 | 0.4120 / 0.1009 | 0.4369 / 0.1152 | 0.4510 / 0.1229 |
| Track00004 | 0.2232 / 0.0446 | 0.2335 / 0.0502 | 0.2289 / 0.0479 | 0.2405 / 0.0584 | 0.4296 / 0.1126 |
| Track00005 | 0.4007 / 0.0938 | 0.4090 / 0.1011 | 0.3759 / 0.0960 | 0.4402 / 0.1307 | 0.4693 / 0.1474 |

## Failure analysis

- **Separation helps marginally and inconsistently.** all-pitched dedup (0.337 onset F1)
  beats baseline (0.316) by ~+0.02, but vocals+other is essentially flat.
- **The oracle is the decisive evidence.** With *ground-truth* isolated stems,
  onset F1 only reaches 0.42 and note F1 0.12 — far below the GuitarSet guitar
  result (~0.73 / 0.43). Basic Pitch is weak on BabySlakh's instrumentation
  (bass, synth, dense piano) even when perfectly separated.
- **False positives stay high everywhere** (0.59–0.68), and missed rate stays
  high (0.52–0.71). Separation does not fix the core over/under-transcription.

## Answers

1. **Does source separation materially improve full-mix transcription?** No — +0.02 onset F1 at best, inconsistent across clips.
2. **Best stem configuration?** "all-pitched" (bass+other+vocals), but only marginally above baseline.
3. **Does it reduce false positives, misses, or both?** Neither meaningfully (excessive stays ~0.65, missed ~0.64).
4. **Does it improve strict note-duration F1?** Barely (0.068 → 0.085); durations remain poor.
5. **How much latency does separation add?** ~7 s per 20 s clip on CPU (~0.35× realtime), vs ~0.25 s for direct transcription.
6. **Is the gain large enough to justify production complexity?** No.
7. **Is separation or transcription the larger bottleneck?** Transcription. The oracle (perfect separation) is still only 0.42/0.12, so Basic Pitch itself is the limit on BabySlakh instruments.
8. **Next experiment?** Alternative AMT engine routing, or duration reconstruction, on isolated/stem-wise material — NOT source separation.

## Recommendation

**Do not productionize source separation.** The evidence (marginal gain + oracle
bottleneck) points to Basic Pitch being the limiting factor on full-mix
material. The next experiment should compare alternative AMT engines (or a
piano/bass specialist) directly on the same BabySlakh stems, using the oracle
result (0.42/0.12) as the upper bound that a better engine must beat.
