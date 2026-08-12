# Real-audio transcription benchmark — GuitarSet + BabySlakh

Run date: 2026-08-12
Corpus: `real_audio_v1` (10 clips: 5 guitar + 5 full-mix)
Engine: Basic Pitch (production defaults: onset=0.5, frame=0.3)

## Metric semantics

- **onset F1** = onset-only match (pitch + onset within 50 ms).
- **note F1** = onset+offset match (pitch + onset + offset within 50 ms). This is
  the stricter measure that captures note *duration* quality.

These are now distinct. Onset F1 measures "did it find the right notes at the
right time"; note F1 additionally measures "were the note lengths right".

## Dataset composition

| Dataset | Clips | Category | Source | License | Split |
|---------|-------|----------|--------|---------|-------|
| GuitarSet | 5 | guitar | Zenodo 3371780 | CC BY 4.0 | test (fold 0) |
| BabySlakh | 5 | full_mix | Zenodo 4603870 | CC BY 4.0 | fixed 20-track subset |

Archives (checksum-verified):
- `annotation.zip` 39.1 MB (md5:b39b78e6…)
- `audio_mono-mic.zip` 656.9 MB (md5:275966d6…)
- `babyslakh_16k.tar.gz` 882.8 MB (md5:311096dc…)

## Baseline (onset=0.5, frame=0.3)

| Category | Onset F1 | Note F1 | Excessive rate | Missed rate |
|----------|----------|---------|----------------|-------------|
| guitar | **0.7294** | **0.4281** | 0.2491 | 0.2688 |
| full_mix | **0.3157** | **0.0681** | 0.6534 | 0.6963 |

## Cleanup ablation

Production cleanup (`_clean_midi`) removes **zero** notes on all 10 clips:
`removed_short=0, removed_low_velocity=0, removed_out_of_range=0, merged_overlaps=0`.

Conclusion: the current cleanup rules are piano-tuned (pitch range 21–108, 75 ms
short-note floor, low-velocity 18) and **do not trigger on guitar or full-mix
material**. Cleanup neither helps nor hurts here — it is a no-op. On real data,
the rules need to be re-evaluated per material type rather than assumed helpful.

## Threshold sweep (onset-only F1)

| Category | Best onset/frame | Best onset F1 | vs current (0.5/0.3) |
|----------|------------------|---------------|----------------------|
| guitar | 0.6 / 0.3 | 0.7373 | +0.008 |
| full_mix | 0.6 / 0.2 | 0.3700 | +0.054 |

Both categories prefer a slightly higher onset threshold (0.6); full mixes also
prefer a lower frame threshold (0.2). No single threshold materially rescues
full mixes.

## Conclusions

1. **Basic Pitch is ~2.3× better on isolated guitar (0.73 onset F1) than full mixes (0.32 onset F1).**
2. **Duration quality collapses under the stricter note metric.** Guitar drops from 0.73 → 0.43 and full mixes from 0.32 → 0.07 when note *offsets* are scored. Even where onsets are roughly right, Basic Pitch's note lengths are poor — a direct problem for notation.
3. **Error character differs by category.** Guitar errors are balanced (25% FP / 27% missed). Full mixes are dominated by BOTH a false-positive explosion (65%) AND misses (70%).
4. **Cleanup is a no-op on real data** — the piano-tuned rules never fire on guitar/mix.
5. **Threshold tuning gives marginal gains only** — the onset/offset gap is a model limitation, not a threshold problem.

## Recommendation for the next algorithm PR

**Two fronts, in priority order:**

1. **Source separation / stem-wise transcription for full mixes** — the 0.32 onset F1 / 0.07 note F1 on mixtures is the largest absolute gap.
2. **Note duration accuracy** — even on the "easy" guitar category, note F1 (0.43) is far below onset F1 (0.73), meaning offset/duration estimation needs attention before notation can be trustworthy.

The duration finding is new evidence not visible in the earlier onset-only benchmark, and it should change the roadmap: notation quality is limited by transcription *durations*, not just note detection.
