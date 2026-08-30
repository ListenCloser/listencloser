# Analysis V3 Implementation Plan

> **Status:** Post-bakeoff convergence plan, updated 2026-08-29.
>
> **Authority:** `MASTER_SPEC.md` defines product direction. `RESEARCH_LANDSCAPE.md` records the larger technical landscape and measured adoption conclusions. #543 proposes a compact cross-track result ledger. This document does not depend on that PR; it defines the current engine/evidence architecture, remaining result gates, and the order in which evidence should reach the product.
>
> **Important:** V3 is no longer “run every candidate bakeoff.” Several tracks have already produced negative or conditional decisions. Implementation agents should preserve those conclusions and spend effort on the next result that can change a product/architecture decision.

---

## 1. Why V3 exists

The earlier product architecture over-weighted one path:

```text
mixed audio
  → transcription / MIDI
  → harmony + melody + rhythm
  → Inspector
```

That path is useful for notation-centric pitched music but cannot be the universal substrate for mixed production, rhythm-first music, timbre/arrangement analysis, or culturally broad music understanding.

V3 replaces “one representation owns truth” with **parallel, typed evidence families**.

---

## 2. Architecture V3 decision

### 2.1 Canonical flow

```text
Work
└─ source audio Version
     │
     ├─ A. specialized exact/localized MIR
     │     beat/downbeat, notes, chords, melody, symbolic transforms
     │
     ├─ B. perceptual audio evidence
     │     amplitude/dynamics, spectrum, onset activity, texture/change
     │
     ├─ C. optional task-conditioned source views
     │     stems and other expensive derived views
     │
     ├─ D. optional research representations/context
     │     embeddings, style/instrument context, multitrack symbolic evidence
     │
     └─ E. optional semantic hypotheses
           audio-language model output
                │
                ▼
        typed Evidence + immutable provenance
                │
                ▼
        claim-specific sufficiency / fallback / abstention
                │
                ▼
        deterministic Observation / Relation
                │
        ┌───────┴────────┐
        ▼                ▼
 synchronized       Breakdown findings
 representations         │
                         ▼
                    Ask / Learn / Compare
```

### 2.2 Core rule

The architecture optimizes for **claim authority**, not model novelty.

- Specialized MIR is preferred for exact musical events when validated.
- Perceptual evidence provides broad, cheap, style-neutral measurements.
- Symbolic computation derives exact relationships only when symbolic evidence is trustworthy.
- Stems are optional source views, not automatic truth.
- Embeddings/context models provide retrieval or probabilistic context only after task validation.
- Audio-language models may add semantic value but do not become detectors-of-record.
- Product-facing findings are generated from evidence + sufficiency + relations, not raw model prose.

---

## 3. Runtime tiers

Implementation should distinguish what normally runs, what is requested conditionally, and what remains research-only.

### Tier A — normal/promoted evidence path

Use when the capability is mature for its declared domain.

Current examples:

- existing specialized production MIR baselines;
- promoted perceptual evidence primitives;
- deterministic observations/relations over supported evidence;
- existing synchronized representation generation.

Properties:

- bounded operational cost;
- typed provenance;
- fail-closed output;
- usable by Breakdown/Ask only within maturity/sufficiency constraints.

### Tier B — optional / task-conditioned derived evidence

Generate only when a downstream claim or user action has a validated need.

Current example:

- `StemReference` / source separation.

Potential future examples:

- heavier MetricGrid path if runtime policy warrants;
- expensive note/source models for a specific representation or analysis question.

Properties:

- asynchronous is acceptable;
- immutable Artifact/Version should be cached;
- generating the artifact is not proof the evidence is good;
- downstream detector/sufficiency decides whether it can support a claim;
- mixture/default evidence remains available.

### Tier C — research/reference only

Current examples:

- MERT / MuQ / MusicFM / CLaMP3 / CLAP production embedding layer;
- MR-MT3 default CPU transcription;
- raw style/instrument context as user facts;
- audio-language factual analysis;
- unvalidated structure candidates.

Properties:

- no production dependency/routing merely because an evaluator exists;
- no product UI exposing scores as facts;
- promotion requires a concrete user capability and a result-bearing gate.

---

## 4. Decisions that should not be reopened casually

### 4.1 No universal MIDI/score intermediate

MIDI/score remain domain-specific representations and evidence sources.

### 4.2 No universal foundation-model layer yet

#341 evaluated the first fixed foundation set. All remain `RESEARCH`; no production vector/index is justified.

### 4.3 No universal source separation

#477/#480/#486/#507/#521 support optional task-conditioned stems, not eager preprocessing.

### 4.4 No hard genre router

#355 supports probabilistic context semantics only. Style can affect salience/explanatory framing after validation; it must not fork the application into genre products.

### 4.5 No audio-language fact authority

#362 preserves exact MIR as specialized evidence and tests audio-language only as optional grounded semantic augmentation.

### 4.6 No graph database

#336’s Evidence Graph is a conceptual/domain contract. Keep current Postgres/Supabase + Artifact/Version lineage + typed payloads until concrete product queries require another store.

### 4.7 No more generic MR-MT3 caching work

#541 shows model residency only yields ~1.08× mean speedup on the canonical five 30-second clips; expensive CPU inference remains the bottleneck. Revisit only with materially different operations plus product-value evidence.

---

## 5. Measured decision table

| Track | Evidence | Decision | Architecture consequence |
|---|---|---|---|
| Foundation #332 | #341 | RESEARCH | no production embedding/vector layer |
| Context #333 | #355 | RESEARCH / REVISIT | multi-label probabilistic context only; no hard routing |
| Separation #334 | #477/#480/#486/#507/#521; decision docs #534 | RESEARCH | mixture primary; optional cached `StemReference`; claim-specific fallback/abstention |
| Metric grid #335 | #474 | leading promotion candidate | Beat This may replace/augment librosa after independent + ops/meter gates |
| Evidence graph #336 | #371 + later domain work | KEEP conceptual | typed evidence/relations over existing persistence; no graph DB |
| Multitrack AMT #337 | #404/#541 | RESEARCH / reference | no default MR-MT3 worker; symbolic multitrack is optional, not universal |
| Audio-language #339 | #362 | RESEARCH | semantic hypothesis layer only; matched grounded-QA run required |
| Product consumer #340 | #373 + product work | KEEP | Breakdown is primary understanding surface |
| Perceptual/sufficiency | #455/#457 → #459/#460 | ADOPT bounded path | broad evidence → relations → grounded findings, with literal wording and abstention |

---

## 6. Evidence contracts

Every production-capable evidence object should answer:

1. **What source Version does this describe?**
2. **What time span / coordinate system does it use?**
3. **What engine/model/version/parameters produced it?**
4. **What maturity/domain does the result support?**
5. **What measurement unit / taxonomy / representation does it use?**
6. **Which Artifact/Version or support refs reproduce it?**
7. **What is the failure/unknown state?**

Do not call a generic model score “confidence” unless calibration supports that meaning.

### Conceptual evidence families

```ts
type SourceLocator = {
  sourceVersionId: string
  startSeconds?: number
  endSeconds?: number
}

type EvidenceBase = {
  locator: SourceLocator
  evidenceType: string
  maturity: "evaluation_only" | "experimental" | "production"
  provenance: Record<string, unknown>
}
```

Specific families may extend this with task-standard fields:

- `MetricGridEvidence`
- note/transcription evidence
- chord/key/melody evidence
- perceptual time series
- `StemReference`
- `ContextEvidence`
- optional `EmbeddingEvidence`
- optional `SemanticHypothesis`

The physical schema does not need one table per conceptual type.

---

## 7. Claim sufficiency is the routing layer

The architecture should not route by genre or by “model available.” It should route by the prerequisites of the **claim**.

Example:

```text
user/product wants: "the bass becomes more active here"
    │
    ├─ direct mixture/perceptual evidence sufficient?
    │       └─ yes → make literal supported observation
    │
    ├─ is a source-aware bass view known to improve this claim?
    │       └─ yes → request/cache StemReference and run downstream evidence
    │
    └─ evidence weak/conflicting?
            └─ fallback to mixture wording or abstain
```

This is the role of #457 and downstream sufficiency contracts.

### Requirements

- fail closed on missing/malformed evidence;
- keep support refs through every relation/finding;
- preserve both sides of comparisons;
- separate unavailable / withheld / failed / supported;
- never infer unsupported semantic labels from the presence of a lower-level measurement.

---

## 8. Relations are the reusable explanation primitive

Rather than implement a separate high-level detector for every future explanation, prefer reusable operations over evidence:

- higher/lower/unchanged,
- before/after,
- enters/exits,
- similar/different,
- repeats/follows,
- denser/sparser in an explicitly measured unit,
- same/different source-role activity,
- relative pitch/harmony relationships where symbolic evidence supports them.

The product sequence is:

```text
Evidence
→ Sufficiency
→ Observation / Relation
→ Grounded Finding
→ Breakdown / Ask
```

This is more scalable than `genre → bespoke feature list`.

---

## 9. Source separation implementation policy (#334)

The old plan to run a generic 2–3-separator tournament is superseded by measured evidence.

### Current policy

```text
source audio
  ├─ default mixture evidence
  └─ optional request:
       HTDemucs-equivalent StemReference
          ↓
       downstream task detector
          ↓
       claim-specific sufficiency
          ├─ supported
          ├─ fallback to mixture
          └─ abstain
```

### Why

- objective drum/bass/vocal/other quality is strongly positive on BabySlakh and MUSDB18;
- downstream beat F1 does not improve in aggregate;
- bass AMT gains precision at substantial recall cost;
- severe negative-tail stem failures exist;
- hosted CPU is feasible asynchronously but Oracle concurrency/cost is unmeasured.

### Allowed next source-separation work

Only reopen for:

1. a concrete source-aware product claim;
2. matched mixture-vs-stem downstream scoring on real/out-of-domain audio;
3. explicit failure detector / fallback / abstention;
4. actual Oracle worker topology/cost/concurrency;
5. a challenger separator targeted at a demonstrated HTDemucs failure mode.

Do **not** run a separator tournament for its own sake.

---

## 10. MetricGrid implementation policy (#335)

Beat This is the current leading candidate because #474 shows materially better localized beat/downbeat evidence than production librosa on a valid checkpoint-associated validation split.

### Remaining promotion gates

1. **Independent corpus:** one genuinely independent annotated dataset/split.
2. **Operations:** latency/worker/fallback policy for the slower model.
3. **Meter:** separately measured; do not infer meter from downbeats by assumption.
4. **Downstream regressions:** beat-relative density/groove/notation consumers must improve or at least not regress.
5. **Provenance:** exact checkpoint/split/training-overlap metadata stays machine-readable.

If these pass, promote the *MetricGrid evidence contract*, not merely a brand name. Keep a fallback path for operational failure.

---

## 11. Foundation/context implementation policy (#332 / #333)

### Foundation embeddings

Do not create a vector column/index until one of these exists:

- scored passage similarity/retrieval UX,
- cross-work search,
- text-to-passage retrieval,
- library clustering with user value,
- a measured downstream context head that beats simpler alternatives.

A future result should compare actual retrieval behavior, not generic benchmark reputation.

### Style/instrument context

Before product exposure:

- run a labeled standard split;
- report top-k/multi-label metrics;
- inspect calibration and adjacent-segment stability;
- inspect ambiguous/multi-style works;
- include culturally diverse failure slices;
- preserve taxonomy/model provenance.

Context may change salience or explanatory vocabulary. It must not suppress universal evidence or become `if genre == ...`.

---

## 12. Generic multitrack AMT policy (#337)

### Current evidence

#404 established MR-MT3 as a useful quality/reference candidate.

#541 measured the exact process-vs-resident question:

- fresh process mean: **83.107 s / 30 s**
- resident model mean: **79.810 s / 30 s**
- mean speedup: **1.0828×**
- one-time load: **2.918 s**
- heavy clips remain ~116–144 s
- semantic output parity and repeat determinism pass

### Decision

`MR-MT3 = RESEARCH / reference`.

Do not implement a production resident worker based on this result. Revisit only if a new model/runtime/hardware makes the operation materially different **and** instrument-aware symbolic evidence improves a real product capability.

A plausible downstream product gate, if operations become viable, is localized layer/instrument activity and entrance/exit evidence for Breakdown—not another generic note-F1 benchmark with no consumer.

---

## 13. Audio-language policy (#339)

No model prose enters `Insight` as a factual detector result.

The next legitimate experiment is a fixed rights-safe corpus comparing:

```text
audio_only
evidence_only
audio_plus_evidence
```

on identical questions and grading contracts.

Promotion requires `audio_plus_evidence` to improve supported-claim rate and usefulness without degrading contradiction/unsupported-claim rate, citations, abstention, temporal grounding, or specificity.

If a legitimate GPU environment is unavailable, record the operations blocker. Do not change production topology just to make the research candidate runnable.

---

## 14. Structure policy

The structure evaluator is mature enough to run. Do not add abstraction before evidence.

Next:

1. finalize/fetch the deterministic SongFormBench BC selection;
2. materialize the exact same audio provenance for all candidates;
3. run All-In-One and SongFormer (or the current fixed candidate set);
4. report boundary/grouping metrics and per-track failures;
5. keep semantic labels a separate maturity gate.

A useful boundary/grouping result can ship before Verse/Chorus semantics if the product language remains literal.

---

## 15. Piano transcription and notation policy

Two result gates already own the main questions.

### #540 — Basic Pitch vs Transkun production profiles

Run identical audio/reference rows through the exact production registry and compare:

- onset F1,
- onset+offset F1,
- spurious/missed notes,
- note-count ratio,
- duration error,
- runtime/RSS,
- production cleanup/provenance.

No routing change before the result.

### #502 — audio→score stage attribution

Measure:

```text
reference MIDI → current metric grid → score
vs
audio → production transcription → same metric grid → score
```

Then rank error contribution:

- transcription,
- metric grid,
- quantization/duration,
- voice/staff assignment,
- MusicXML/engraving,
- rendering.

Fix the largest measured user-visible contributor first.

---

## 16. Product integration order

The cross-research roadmap is:

```text
Analysis V3 evidence + #455/#456/#457
        ↓
#459 minimal promoted evidence substrate
        ↓
#460 reusable observations / relations
        ↓
#461 grounded Breakdown / Ask / shared-time integration
        ↓
#462 extensible analytical frameworks
```

### Product consumer

Breakdown remains the primary understanding surface.

A finding should answer:

- what changed / what relationship exists;
- where it happens in musical time;
- which evidence supports it;
- what immediate action is valid (focus, compare, play/loop when the product state supports it);
- which interpretation/framework is being used when semantic language goes beyond literal measurement.

Do not create a second “Analysis dashboard” that exposes raw engine outputs.

---

## 17. Representation policy

Representations are coordinated views of one Work, not a hierarchy in which one view owns truth.

Current/future-compatible views:

- waveform,
- spectrogram,
- Piano Roll,
- score when meaningful,
- beat/bar grid,
- structure timeline,
- source/stem lanes,
- perceptual/evidence timeline,
- relative harmony/theory view,
- similarity/retrieval view when justified.

All should share source identity and musical time. A representation becomes visible when its real persisted artifact/evidence exists; processing should not replace the recording as the primary product object.

---

## 18. Persistence / Evidence Graph migration rule (#336)

Keep:

- Work / Version / Artifact lineage,
- current Postgres/Supabase persistence,
- typed domain payloads,
- immutable derived artifacts,
- support references.

Add physical schema only for a demonstrated query/product requirement.

### Concrete triggers that could justify new persistence

- cross-work vector search at measured scale → pgvector/external vector index;
- relation querying across many Works → first-class relation persistence if current JSON/domain resolution becomes insufficient;
- source-artifact caching/query pressure → explicit index/metadata if current Artifact lineage is insufficient.

No graph database or schema-per-evidence-family by default.

---

## 19. Platform policy

Keep Vercel + Oracle worker + Supabase until measured workloads require something else.

Possible triggers:

| Measured trigger | Response |
|---|---|
| heavier but CPU-feasible optional analysis | async/cached worker job |
| GPU-only research becomes product-critical | on-demand external GPU worker before Kubernetes |
| sustained concurrency overwhelms one worker | add/scale workers based on queue/runtime metrics |
| vector retrieval becomes a product | pgvector/external index after query/scale evidence |
| model cold-start dominates | persistent worker/model cache only when measured to matter |
| intrinsic inference dominates | optimize/replace model/hardware; caching is not the answer |

#541 is a concrete example of the last row: model residency did not materially change MR-MT3’s heavy CPU cost.

---

## 20. Remaining result-bearing gates

These are the highest-value allowed research actions. Prefer completing an active lane over opening another harness.

| Priority | Gate | Result needed | Avoid |
|---:|---|---|---|
| 1 | #540 piano transcription | real Basic Pitch-vs-Transkun corpus result | another adapter/profile abstraction |
| 1 | #502 notation | real stage-attribution result | more notation evaluator layers |
| 1 | #550/#516 structure | materialized fixed corpus + candidate scores | more harness generalization |
| 1 | #335 MetricGrid | independent annotated corpus + ops/meter | citing validation-split result as global proof |
| 2 | #333 context | labeled standard-split/calibrated comparison | raw CLAP tags in product |
| 2 | #339 audio-language | real matched grounded-QA GPU run | architecture-by-model-card |
| 2 | #337 multitrack | no further work unless new ops + product-value hypothesis | more MR-MT3 caching/wrapper tuning |
| 2 | #334 separation | concrete downstream source-aware claim | another SDR-only separator tournament |
| ongoing | #459→#461 | relation-backed product integration | descriptor sprawl / second dashboard |

If another agent already owns one row, do not duplicate it.

---

## 21. What not to build now

Do not build:

- universal source separation;
- a production embedding/vector layer with no retrieval feature;
- a hard genre-specific pipeline;
- an MR-MT3 resident CPU service justified only by caching;
- a graph database;
- raw audio-language factual analysis;
- raw classifier scores labeled “confidence” without calibration;
- a universal score/MIDI endpoint for all music;
- semantic high-level relations directly from low-level descriptors without sufficiency;
- more candidate/harness infrastructure after a result-bearing path exists.

---

## 22. Promotion template

Every new production promotion should include:

```text
user capability / claim
    ↓
exact evidence prerequisite
    ↓
task-standard benchmark + per-piece failures
    ↓
license / operational gate
    ↓
claim-specific sufficiency / abstention
    ↓
typed evidence contract + provenance
    ↓
bounded production adapter
    ↓
real-stack product verification
    ↓
grounded Breakdown/Ask wording
```

A benchmark winner is not automatically a product feature.

---

## 23. Definition of V3 convergence

#327 can be considered architecture-complete when:

1. the measured cross-track decisions are durable in repository docs;
2. active child tracks have either a result or an explicit blocker, not just a harness;
3. the engine/evidence architecture is expressed in typed contracts and routing principles;
4. the first promoted evidence→relation→Breakdown path demonstrates the model end to end;
5. unresolved research candidates are clearly marked `RESEARCH`/`REVISIT`, not allowed to block product progress.

It is **not** necessary to solve every future genre, model, or analysis mode before convergence.

---

## 24. Implementation-agent rule

Before starting Analysis work:

1. read the relevant section here and the owning issue/REPORT;
2. consult the compact decision ledger from #543 if/when it is merged;
3. search open PRs for overlap;
4. ask: **what decision will my result change?**
5. if a runnable harness already exists, run it and produce evidence instead of extending it;
6. do not productionize research-only candidates without an explicit promotion issue/gate.

The preferred default is now **evidence → relation → product value**, not **repo discovery → adapter → more infrastructure**.
