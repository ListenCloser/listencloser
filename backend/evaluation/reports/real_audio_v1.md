# Real-audio transcription benchmark — GuitarSet + BabySlakh

Run date: 2026-08-12
Corpus: `real_audio_v1` (10 clips: 5 guitar + 5 full-mix)
Engine: Basic Pitch (production defaults unless noted)

## Dataset composition

| Dataset | Clips | Category | Source | License | Split |
|---------|-------|----------|--------|---------|-------|
| GuitarSet | 5 | guitar | Zenodo 3371780 | CC BY 4.0 | test (fold 0) |
| BabySlakh | 5 | full_mix | Zenodo 4603870 | CC BY 4.0 | fixed 20-track subset |

Archives (all checksum-verified):
- `annotation.zip` 39.1 MB (md5:b39b78e6…)
- `audio_mono-mic.zip` 656.9 MB (md5:275966d6…)
- `babyslakh_16k.tar.gz` 882.8 MB (md5:311096dc…)

## Baseline (onset=0.5, frame=0.3)

| Category | Clips | Note F1 | Onset F1 | Excessive rate | Missed rate | Avg runtime |
|----------|-------|---------|----------|----------------|-------------|-------------|
| guitar | 5 | **0.7294** | 0.7294 | 0.2491 | 0.2688 | 0.66s |
| full_mix | 5 | **0.3157** | 0.3157 | 0.6534 | 0.6963 | 0.24s |

### Per-clip

| Clip | Category | Note F1 | pred | ref |
|------|----------|---------|------|-----|
| guitarset_bn1_comp | guitar | 0.7266 | 135 | 121 |
| guitarset_rock2_comp | guitar | 0.6982 | 277 | 379 |
| guitarset_jazz1_comp | guitar | 0.7624 | 173 | 189 |
| guitarset_ss3_solo | guitar | 0.7574 | 100 | 69 |
| guitarset_funk1_comp | guitar | 0.7025 | 196 | 251 |
| babyslakh_01 | full_mix | 0.4012 | 187 | 147 |
| babyslakh_02 | full_mix | 0.1352 | 200 | 229 |
| babyslakh_03 | full_mix | 0.4183 | 257 | 422 |
| babyslakh_04 | full_mix | 0.2232 | 131 | 102 |
| babyslakh_05 | full_mix | 0.4007 | 234 | 325 |

## Threshold sweep (best note F1 per category)

| Category | Best onset/frame | Best note F1 | vs current (0.5/0.3) |
|----------|------------------|--------------|----------------------|
| guitar | 0.6 / 0.3 | 0.7373 | +0.008 |
| full_mix | 0.6 / 0.2 | 0.3700 | +0.054 |

## Conclusions

1. **Basic Pitch is materially better on isolated guitar (0.73 F1) than full mixes (0.32 F1).** The gap is ~2.3×.
2. **Error character differs sharply by category.** Guitar errors are balanced (25% false positives, 27% missed). Full mixes are dominated by BOTH a huge false-positive explosion (65%) AND missed notes (70%) — Basic Pitch both over- and under-transcribes mixtures simultaneously.
3. **Full-mix transcription is poor enough (0.32 F1, 65% FP) to justify source separation as the next experiment.** A separation-first pipeline (mixture → stems → Basic Pitch per stem) is the highest-leverage next step.
4. **Threshold preferences differ only slightly by category.** Both prefer a slightly higher onset threshold (0.6 vs 0.5), suggesting modest false-positive suppression helps. Full mixes additionally prefer a lower frame threshold (0.2). No single threshold dramatically rescues full mixes.
5. **Cleanup ablation** was not separately run in this pass (the baseline metrics above already include the production cleanup path); a rule-level ablation on real audio is the natural follow-up once source separation is evaluated.

## Recommendation for the next algorithm PR

**Target source separation / stem-wise transcription for full mixes.** The guitar-only path is already usable; mixtures are where Basic Pitch collapses. A separation-first experiment (even a lightweight, evaluation-only comparison) would directly address the 0.32 F1 full-mix result.

## Note

Cleanup ablation and onset+offset F1 are pending the evaluation-metrics split (onset-only vs onset+offset) that landed separately. This PR's numbers use the existing note/onset F1 metric.
