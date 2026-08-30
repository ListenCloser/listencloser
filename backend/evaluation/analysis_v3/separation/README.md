# Analysis V3: Source Separation Evidence Track

This directory contains the source-separation research harness for #334.

## Current decision

**RESEARCH.** Source separation is useful as an **optional, cached, task-conditioned evidence primitive**, not as universal preprocessing for every work.

The evidence now answers substantially more than the original feasibility harness:

| Gate | Result | Product implication |
|---|---|---|
| Objective quality, synthetic (#480) | BabySlakh: drums +13.983 dB mean SI-SDR, bass +12.900 dB; drums/bass improve 5/5 | HTDemucs can isolate useful source signal |
| Objective quality, held-out real recordings (#521) | MUSDB18 test preview: drums +13.3558 dB mean, 50/50 improved; bass +12.9033 dB, 47/50; other +8.9048 dB, 49/50; vocals +12.0349 dB, 48/50 | Objective source-quality premise generalizes, but rare failures remain severe |
| Beat downstream (#477) | drum-stem beat F1 mean delta -0.0045; 2 improve / 2 degrade / 1 tie | Do not require separation before coarse beat tracking |
| Bass AMT downstream (#486) | onset F1 +0.0578 mean, but onset+offset -0.0088; large recall collapse | Useful as precision-oriented secondary evidence, not replacement transcription |
| CPU operations (#507) | hosted x86 and ARM both feasible asynchronously; 180 s audio: 85.918 s x86 / 152.278 s ARM; peak RSS 1.79 / 1.60 GB | Plausible on-demand worker path; actual Oracle concurrency/cold-start/cost still unmeasured |

The negative tail in #521 is important: successful stem generation does **not** imply a reliable stem. Bass and vocal examples degrade by more than 20 dB relative to the mixture baseline. Downstream claim gates therefore need fallback/abstention.

## Candidate stance

| Candidate | Decision | Why |
|---|---|---|
| HTDemucs (`955717e8`) | **RESEARCH** | strong objective source quality and practical hosted-CPU operation, but downstream benefit is claim-specific |
| BS-RoFormer / Mel-Band RoFormer family | **REVISIT / DEFER** | modern family worth comparing only after a concrete source-aware claim has a promotion target; another SDR-only bakeoff is not the current bottleneck |

## Architecture

Keep direct mixture evidence primary:

```text
mixture -> direct task evidence
```

Request source separation only when a downstream capability has evidence that the source-aware path may improve the claim:

```text
mixture
  -> direct evidence ---------------------------┐
  -> optional separator -> StemReference -------+-> claim-specific sufficiency gate
                                                |
                                                +-> fallback / abstain on disagreement
```

Use the canonical #336 `StemReference` contract. Stem audio remains ordinary immutable Artifact/Version data; no per-stem confidence should be invented. Confidence belongs to a calibrated downstream observation if such calibration exists.

## Rules for future experiments

1. **Do not use SI-SDR as a proxy for product value.** Score the actual downstream claim.
2. Preserve mixture evidence and compare/corroborate rather than silently replacing it with stem-derived evidence.
3. Define a claim-specific failure/fallback rule before promotion.
4. Request separation by claim sufficiency/expected value, not by genre or a global `separation_enabled` flag.
5. Keep heavyweight separation dependencies evaluation-only until a production deployment gate is satisfied.
6. A RoFormer challenger becomes high priority only when a demonstrated source-aware task has a promotion target or HTDemucs failure mode to address.

## Existing harness

The original feasibility runner remains available:

```bash
python -m backend.evaluation.analysis_v3.separation.run --candidate bs_roformer
python -m backend.evaluation.analysis_v3.separation.run --candidate all
python -m backend.evaluation.analysis_v3.separation.run --candidate demucs --device cpu
```

Its historical feasibility results should not be confused with the later result-bearing PRs above.

See `REPORT.md` for the full evidence synthesis, provenance boundaries, architecture decision, and remaining ADOPT gates.
