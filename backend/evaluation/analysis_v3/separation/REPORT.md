# Analysis V3 Source Separation Decision Report

## Executive decision

**Recommendation: `RESEARCH`.**

HTDemucs now has strong evidence that it produces objectively cleaner drums/bass/other/vocal sources on controlled synthetic mixtures and on the full held-out MUSDB18 test-preview set. It is also operationally feasible on controlled hosted x86_64 and ARM64 CPUs.

That is **not** enough to make source separation universal preprocessing. The downstream evidence is selective:

- coarse beat detection does not improve in aggregate after drum separation;
- bass transcription becomes more precision-oriented but loses substantial recall;
- real-recording source quality has a rare but severe negative tail;
- actual Oracle worker concurrency, cold-start behavior, queue capacity, and cost remain unmeasured.

The architecture decision is therefore narrower:

> Keep mixture evidence primary. Retain #336 `StemReference` as an optional, cached, task-conditioned evidence primitive requested only by claims whose source-aware path has demonstrated value. Every promoted source-aware claim needs explicit fallback/abstention when stem evidence is unreliable or disagrees with corroborating evidence.

This report supersedes the original first-stage feasibility interpretation in this directory. The historical harness remains useful, but the decision is now grounded in #477, #480, #486, #507, and #521.

---

## 1. Product question

Should source separation become a first-class evidence capability for mixed music in hello-ai, and if so should it be:

1. universal preprocessing;
2. a task-conditioned evidence path;
3. research-only;
4. rejected?

The answer is **task-conditioned research evidence**. The current data rejects universal preprocessing and does not yet justify production ADOPT.

---

## 2. Candidate and provenance

### HTDemucs

- package: `demucs==4.1.0`
- model: `htdemucs`
- model signature: `955717e8`
- exact weight artifact: `adefossez/HTDemucs/955717e8.safetensors`
- verified SHA256: `d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd`
- artifact size: 80.13 MB
- inference: `shifts=0` for deterministic evaluation
- code / evaluated weight licensing: MIT as recorded by the evaluation track

The result-bearing workflows fail closed on weight drift rather than silently accepting an unknown checkpoint.

### RoFormer family

BS-RoFormer / Mel-Band RoFormer remains a modern separation family worth revisiting, but **another generic SDR bakeoff is not currently the highest-value uncertainty**.

The original package-path probe was blocked in the repo's older Python 3.9 environment and did not have an exact legally verified pretrained checkpoint wired. More importantly, the later HTDemucs results show that source quality itself is no longer the main unanswered question.

Decision: **`REVISIT / DEFER` until a concrete source-aware claim has a promotion target or a demonstrated HTDemucs failure family to address.**

Code, checkpoint, and training-data rights must still be audited independently for any future RoFormer candidate.

---

## 3. Evidence summary

| Gate | Dataset / topology | Measured result | Decision impact |
|---|---|---|---|
| Objective source quality (#480) | BabySlakh, fixed 5 × 30 s controlled excerpts | drums **+13.983 dB** mean SI-SDR; bass **+12.900 dB**; other **+7.042 dB**; drums/bass 5/5 positive | strong evidence that HTDemucs isolates useful source signal |
| Held-out real source quality (#521) | official MUSDB18 7 s preview, canonical `test`, all **50 tracks** | drums **+13.3558 dB**, 50/50 positive; bass **+12.9033 dB**, 47/50; other **+8.9048 dB**, 49/50; vocals **+12.0349 dB**, 48/50 | source-quality premise broadly survives real recordings, but not uniformly |
| Beat downstream (#477) | BabySlakh fixed 5 × 60 s | production beat F1 mean delta **-0.0045**; 2 improve / 2 degrade / 1 tie | do not require drums separation before coarse beat tracking |
| Beat localization diagnostic (#477) | same comparison | matched-beat timing error tightens on all selected tracks | possible narrower timing-refinement use case, still unpromoted |
| Bass AMT downstream (#486) | BabySlakh fixed 5 × 30 s | onset F1 **+0.0578 mean**, **+0.1041 median**; onset+offset **-0.0088 mean**; predicted notes collapse ~1625 → 345 and matches ~120 → 54 | precision-oriented secondary evidence, not replacement transcription |
| Hosted x86 operation (#507) | Ubuntu 24.04 x86_64, 4 CPUs, 2 torch threads | 10 s: **12.928 s**; 30 s: **16.627 s**; 180 s: **85.918 s**; peak RSS **1.79 GB** | plausible asynchronous CPU path |
| Hosted ARM operation (#507) | Ubuntu 24.04 ARM, 4 CPUs, 2 torch threads | 10 s: **12.477 s**; 30 s: **29.100 s**; 180 s: **152.278 s**; peak RSS **1.60 GB** | operationally feasible but ~1.77× slower than x86 at 180 s |

The central result is **not** “separation works” or “separation does not work.” It is:

> Objective source quality is strong, while downstream musical value depends on the claim and error mode.

---

## 4. Objective source quality

### 4.1 Controlled synthetic reference — #480

BabySlakh is useful because the mixture and isolated sources are aligned and legally usable for evaluation.

Fixed first-30-second excerpts from `Track00001`–`Track00005` produced:

| family | scored | mean ΔSI-SDR | median ΔSI-SDR | improved / degraded |
|---|---:|---:|---:|---:|
| drums | 5 | +13.983 dB | +15.287 dB | 5 / 0 |
| bass | 5 | +12.900 dB | +11.829 dB | 5 / 0 |
| other | 5 | +7.042 dB | +9.247 dB | 4 / 1 |
| vocals | 0 | n/a | n/a | references absent in selected tracks |

This establishes real source-quality gain on a controlled synthetic corpus. It does not establish downstream benefit or broad real-recording generalization by itself.

Result provenance in #480 includes workflow/artifact/checkpoint details; BabySlakh is CC BY 4.0.

### 4.2 Held-out real recordings — #521

The real-recording gate used the official MUSDB18 7-second preview through `musdb==0.4.3`, canonical `test` subset, all **50 available tracks**, with no favorable-track selection.

Metric: `fast_bss_eval.si_sdr(..., zero_mean=True, clamp_db=100.0)`; decision quantity is separated-stem SI-SDR minus the **original mixture's SI-SDR against the same reference**. Stereo channels are scored independently and averaged; silent references are withheld.

| stem | mean ΔSI-SDR | median Δ | min / max | improved | degraded |
|---|---:|---:|---:|---:|---:|
| drums | **+13.3558 dB** | +13.4134 | +4.0237 / +23.6036 | **50/50** | 0 |
| bass | **+12.9033 dB** | +14.3130 | -27.1231 / +23.6753 | **47/50** | 3 |
| other | **+8.9048 dB** | +8.7463 | -4.0430 / +19.6995 | **49/50** | 1 |
| vocals | **+12.0349 dB** | +13.1413 | -23.0183 / +26.4917 | **48/50** | 2 |

Exact successful workflow run: `33277448298` on benchmark head `8c331145d753904a1402928c4973422ea3f76efe`.

Metrics artifact: `9721997702`; artifact ZIP digest:

`sha256:5fe358a637ffc012db248b9eabd915f746c50e335957cb69da1bd0ca2be156e9`

Generated full-result JSON SHA256:

`a5499da8c0fddf61ffb5964305d8801570359e5f8e7bf9f8fa0d57f029b224a0`

No MUSDB or separated audio is committed or uploaded. MUSDB audio is restricted to academic use per the dataset/package documentation; only metrics/provenance are retained.

### 4.3 Negative tail

Successful inference is **not** a reliability guarantee. #521 includes six degraded stem rows, including:

- `Tom McKenzie - Directions`, bass: **-27.1231 dB**
- `Motor Tapes - Shore`, vocals: **-23.0183 dB**
- `PR - Oh No`, bass: **-18.5421 dB**
- `Skelpolu - Resurrection`, vocals: -4.9614 dB
- `Arise - Run Run Run`, other: -4.0430 dB
- `Juliet's Rescue - Heartbeats`, bass: -1.4940 dB

This is the strongest reason the architecture must separate **artifact availability** from **claim sufficiency**.

---

## 5. Downstream value

### 5.1 Beat tracking — #477

Question: does the exact production beat estimator improve when given the HTDemucs drums stem instead of the same mixture?

Result across five fixed BabySlakh tracks:

- mean beat-F1 delta: **-0.0045**;
- 2 tracks improve;
- 2 tracks degrade;
- 1 ties.

Matched-event localization becomes tighter on all selected tracks, which is interesting for a later groove/timing-refinement claim, but aggregate beat detection does not improve.

Decision: **keep direct mixture beat evidence as the default.** A drum stem may be optional/corroborating for a narrower timing claim after direct validation.

### 5.2 Bass transcription — #486

Question: does the exact production Basic Pitch path improve when given the HTDemucs bass stem?

Result:

- onset-only F1: **+0.0578 mean**, **+0.1041 median**, 3/5 improve;
- onset+offset F1: **-0.0088 mean**;
- one selected track falls to zero matched notes after separation;
- predictions fall roughly **1625 → 345**;
- matched reference notes fall roughly **120 → 54**.

Interpretation: the bass stem behaves mainly as a **false-positive/precision filter purchased with recall loss**.

Decision: useful as a precision-oriented second evidence view or candidate filter, not a replacement transcription path.

---

## 6. Operational evidence — #507

The controlled operational gate pins the exact HTDemucs artifact, sets `shifts=0`, and controls PyTorch to two CPU threads on both architectures.

### x86_64

| audio | latency | RTF | process peak RSS |
|---|---:|---:|---:|
| 10 s | 12.928 s | 1.2928 | 1413.56 MB |
| 30 s | 16.627 s | 0.5542 | 1456.06 MB |
| 180 s | 85.918 s | 0.4773 | 1792.81 MB |

### ARM64

| audio | latency | RTF | process peak RSS |
|---|---:|---:|---:|
| 10 s | 12.477 s | 1.2477 | 1222.94 MB |
| 30 s | 29.100 s | 0.9700 | 1333.05 MB |
| 180 s | 152.278 s | 0.8460 | 1604.45 MB |

Exact controlled workflow run: `33276919383`, benchmark head `3a6f9d98c6e0656d1b3582e14b71722e56f3851c`.

The ARM runner exposed a real packaging issue: `sphn` had no compatible Linux ARM wheel and its source build failed under CMake 4.x. The final run uses the upstream-documented CMake 3.x workaround (`cmake==3.31.10`) while retaining Demucs' declared dependency graph. This is a packaging constraint, not a PyTorch/model incompatibility.

Both architectures are plausible for background analysis, but GitHub-hosted controls are **not** the production Oracle worker topology.

Still unmeasured:

- warm vs cold worker latency;
- model/cache persistence on Oracle;
- concurrent jobs;
- queue contention/backpressure;
- memory behavior under concurrency;
- storage/network overhead for stem artifacts;
- actual operating cost.

---

## 7. Architecture recommendation

Use the canonical #336 contract:

```typescript
type StemReference = {
  sourceVersionId: string
  stems: Array<{
    role: "vocals" | "drums" | "bass" | "other" | string
    artifactVersionId: string
  }>
  provenance: Provenance
  maturity: Maturity
}
```

Stem binaries remain ordinary immutable Artifact/Version data.

### Hard rules

1. A `StemReference` is a **reference to generated evidence**, not proof that the source is correct.
2. Do not invent per-stem confidence values when the separator does not provide calibrated confidence.
3. Downstream observations own their own calibrated confidence/score and evaluation boundary.
4. Mixture evidence remains available; source-aware evidence must not silently replace it.
5. Source separation is requested by downstream claim sufficiency/expected value, not genre or a global feature flag.
6. A source-aware claim must define what happens when stem evidence is missing, weak, or conflicts with mixture/corroborating evidence.

### Target routing shape

```text
mixture
  ├─> direct evidence ------------------------------------┐
  │                                                       │
  └─> [only when justified] separator -> StemReference ---+-> claim-specific gate
                                                          │
                                                          ├-> supported observation
                                                          ├-> mixture fallback
                                                          └-> abstain / withhold
```

This matches #457's evidence-sufficiency architecture: **measured evidence → localized relation/observation → claim-specific gate → optional interpretation**.

---

## 8. Decision by use case

| Use case | Current stance |
|---|---|
| universal import-time four-stem generation | **REJECT for now** |
| coarse beat tracking through drums stem | **REJECT as default** |
| drum timing/groove refinement | **RESEARCH** |
| bass note transcription replacement | **REJECT as replacement** |
| precision-oriented bass candidate evidence | **RESEARCH** |
| source/layer entry-exit evidence | **RESEARCH**; requires direct claim validation + artifact/bleed fallback |
| synchronized isolate/listen UX | **RESEARCH**; requires perceptual/product-value and operational gate |
| HTDemucs as available research separator | **RESEARCH / keep** |
| RoFormer family challenger | **REVISIT / DEFER** until a concrete promoted task exists |

---

## 9. What not to build next

Do **not** spend the next source-separation cycle on:

- a generic “which separator has the best SDR?” tournament;
- automatic stems for every upload;
- a dedicated stem database/table before product query pressure exists;
- a per-stem confidence field without calibration semantics;
- genre-specific source-separation routers;
- replacing mixture-derived beat or AMT evidence solely because a stem exists;
- production dependency wiring before the Oracle deployment gate.

The current uncertainty is **selection policy + downstream user value**, not whether HTDemucs can produce cleaner stems.

---

## 10. Gates required before `ADOPT`

Upgrade #334 from `RESEARCH` only after all relevant gates for a concrete product path are met:

1. **Claim/value gate** — identify a source-aware product/claim family that measurably improves with stems.
2. **Failure-policy gate** — define and validate claim-specific disagreement/fallback/abstention for bad stems, including the negative tail seen in #521.
3. **Real/out-of-domain gate** — validate the promoted claim on real recordings outside a separator-native benchmark where practical.
4. **Evidence-sufficiency gate** — encode request conditions and promotion thresholds in #457 rather than routing by global feature flags.
5. **Production-topology gate** — replay on the actual Oracle worker with realistic cold start, concurrency, queue, memory, storage, and cost constraints.
6. **Perceptual/user-value gate** — if stems themselves become audible user-facing representations, verify artifact quality and whether isolate/A-B listening is actually useful.
7. **Challenger gate** — only then compare a maintained RoFormer-family candidate on the **same downstream + operational contract** if HTDemucs quality is a remaining blocker.

---

## 11. Historical feasibility harness

The original feasibility runner in this directory established that HTDemucs could load and emit four stems and that the then-evaluated BS-RoFormer package path was blocked in the older local environment.

Those historical numbers are useful implementation history but are **superseded for current decisions** by the controlled result-bearing PRs above.

Reproduction of the original harness remains:

```bash
export MUSIC_EVAL_CACHE_DIR=/path/to/backend/evaluation/.cache
python3 -m backend.evaluation.analysis_v3.separation.run --candidate all
python3 -m backend.evaluation.analysis_v3.separation.run --candidate demucs
```

Do not interpret its smoke outputs as objective quality or downstream evidence.

---

## 12. Coordinator state

Result-bearing work is intentionally split into independently reviewable PRs:

- #477 — separation → beat downstream
- #480 — BabySlakh objective SI-SDR
- #486 — separation → bass AMT
- #507 — controlled x86/ARM operational cost
- #521 — held-out MUSDB18 real-recording objective generalization

No source-separation result alone authorizes production routing. #334 remains open at **RESEARCH** until the concrete ADOPT gates above are satisfied.
