# Analysis V3 Implementation Plan

> **Status:** Execution plan for the research/architecture reset in `MASTER_SPEC.md`.
>
> **Authority:** `MASTER_SPEC.md` defines product direction. `RESEARCH_LANDSCAPE.md` records the candidate landscape. This document defines sequencing, evaluation gates, canonical outputs, and what implementation agents should do next.
>
> **Important:** This is deliberately not a request to immediately replace the current production engines. Analysis V3 starts with evidence-producing bakeoffs, then makes bounded adoption decisions.

---

## 1. Why V3 exists

The current application has a useful synchronized workspace and increasingly trustworthy tonal/symbolic analysis, but it still over-represents one worldview:

```text
mixed audio
  → transcription / MIDI
  → harmony + melody + rhythm
  → Inspector
```

That works unusually well for notation-centric pitched music. It is not a sufficient universal architecture for mixed-production music, rhythm-first traditions, timbre/arrangement-centric music, or cross-cultural music understanding.

V3 therefore adds **parallel evidence families** rather than making symbolic MIDI the universal intermediate representation:

```text
                         Work audio
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
 specialized MIR      foundation reps      source-aware audio
 beats/chords/AMT     embeddings/text       stems/instruments
        │                   │                   │
        └──────────────┬────┴──────────────┬────┘
                       ▼                   ▼
                  typed evidence      context evidence
                       └─────────┬─────────┘
                                 ▼
                    observations / relations
                                 ▼
                 Inspector / representations / Ask
```

The strategic change is not “use AI instead of MIR.” It is **use the best paradigm for each claim**:

- specialized/localized engines for exact events,
- symbolic computation for exact relationships when symbolic evidence is reliable,
- foundation embeddings for similarity, retrieval, broad context, and transferable features,
- source separation for instrument/source-specific behavior,
- audio-language models only as qualified semantic/context evidence and explanation,
- deterministic/calibrated observation logic to convert evidence into human-readable musical relationships.

---

## 2. Decisions already made

Implementation agents should not reopen these decisions without contradictory benchmark evidence.

### 2.1 Keep the current specialized production stack while V3 is evaluated

Keep as current baselines:

- transcription: Basic Pitch + Transkun profile routing,
- chords: `lv-chordia`,
- global key / theory utilities: music21,
- melody: LStoM,
- notation: current quantization/MusicXML pipeline,
- rhythm: current production beat path + deterministic measurements,
- structure: evaluation-only baseline only.

A candidate is not adopted merely because it loads or has a newer paper.

### 2.2 Do not add more bespoke Analysis micro-features by default

Already-active, bounded, truthful work may finish. Broad new analysis claims should wait for the V3 bakeoffs where the underlying evidence family matters.

### 2.3 Do not hard-code genre products

Piano, house, reggaeton, jazz, pop, rock, non-Western traditions, etc. are **diversity probes**, not branches in the application ontology.

The target is:

```text
universal evidence
  + multi-label context/style/instrument evidence
  + capability prerequisites/relevance
  → style-aware emphasis
```

not:

```text
if genre == "house": show_house_ui()
```

### 2.4 Score is a domain-specific representation

Score remains first-class when useful, but no Analysis V3 contract may assume that every work has a meaningful score.

### 2.5 Unknown is a valid result

A model may be technically runnable yet unsuitable for product claims. Capability maturity stays separate from implementation availability.

---

## 3. Research findings that change the execution plan

### 3.1 Beat This is a current strong beat baseline, not a legacy curiosity

MIREX 2025 explicitly includes **Beat This!** as a baseline. It remains competitive across multiple beat-tracking test sets. The current hello-ai registry defaults the beat engine to `librosa`, while `beat_this` is an optional engine. Therefore the V3 beat track should primarily ask:

> Does Beat This materially improve beat timing over current `librosa`, and what should provide downbeat/meter/bar-phase evidence?

BeatNet remains relevant because it jointly models beat/downbeat/tempo/meter, but it should not be presumed superior at ordinary beat tracking.

### 3.2 MusicFM is relevant to structure, not just generic embeddings

MIREX 2025 Music Structure Analysis reports a MusicFM baseline trained on Harmonix with nontrivial structure metrics (ACC 0.705, HR.5 0.644, HR3 0.710). This makes MusicFM a concrete candidate for future structure evidence as well as a foundation representation candidate.

The existing librosa structure baseline remains useful as an interpretable evaluation baseline.

### 3.3 CLaMP3 is especially aligned with hello-ai

CLaMP3 aligns text, audio, MIDI/performance signals, sheet music, and images in one representation space. Because hello-ai already persists audio, MIDI, and MusicXML representations, CLaMP3 should receive a high-priority operational bakeoff for:

- cross-representation consistency,
- text-to-passage retrieval,
- cross-work similarity,
- audio ↔ MIDI/score retrieval.

Do not assume it wins on runtime or deployment fit.

### 3.4 “Universal” music embeddings require cultural/generalization checks

Recent ISMIR work explicitly shows that foundation-model behavior varies across Western-popular and world-music corpora and may encode training-data bias. V3 evaluation must therefore include a diversity probe and must not call any representation “universal” merely because it scores well on Western popular datasets.

### 3.5 Source-separation evaluation should use an inference harness, not random architecture integrations

BS-RoFormer / Mel-Band RoFormer are strong modern architecture families, but code repositories do not automatically provide production-ready, legally reusable weights. Prefer a maintained evaluation/inference harness such as the MSST ecosystem where practical, and audit each selected checkpoint’s weight/training-data terms independently.

### 3.6 Multi-instrument AMT is a separate research question

Generic mixed music may eventually benefit from multi-track symbolic evidence. MT3 is an Apache-2.0 research baseline; YourMT3/YourMT3+ is an interesting newer quality reference but GPL-3.0 constrains straightforward production adoption. This is tracked separately in #337 and must not delay the four core V3 tracks.

---

## 4. Execution order

The research tracks can run in parallel, but adoption decisions should follow these dependencies.

```text
Track A: foundation representation ──────┐
                                         ├─→ Evidence/embedding contract
Track B: style/instrument tagging ───────┤
                                         │
Track C: source separation ──────────────┤
                                         ├─→ style-aware observations / UX
Track D: beat/downbeat/meter ────────────┤
                                         │
Track E: optional multi-track AMT ───────┘

Concrete outputs from A-D
    ↓
#336 Evidence Graph design
    ↓
bounded production adapters / migrations only where justified
```

### Recommended practical priority

1. **A — Foundation representations (#332)**: highest architectural leverage for similarity, retrieval, context features, cross-modal consistency.
2. **D — Beat/downbeat/meter (#335)**: foundational for rhythm/groove/structure/notation and likely cheap enough to evaluate quickly.
3. **C — Source separation (#334)**: potentially transformative for generic mixed music, but operationally heavier.
4. **B — Style/instrument tagging (#333)**: depends partly on choosing useful representations, though Essentia can be benchmarked independently.
5. **E — Generic multi-instrument AMT (#337)**: optional; evaluate after stems/foundation evidence clarifies product value.

If multiple agents are available, A-D should be parallel worktrees with no production integration.

---

## 5. Shared evaluation corpus

Every V3 track should use both **task-standard public benchmarks** and a small rights-safe **product diversity probe**.

### 5.1 Task-standard datasets

Use established metrics/datasets rather than inventing private scores:

| Track | Primary benchmark families |
|---|---|
| Foundation reps | MARBLE/reference downstream tasks; candidate-native retrieval benchmarks |
| Style/instrument | MTG-Jamendo and relevant published tagging benchmarks |
| Separation | MUSDB18 / legally usable stem benchmarks; MoisesDB only where its non-commercial terms are acceptable for research |
| Beat/downbeat | MIREX conventions; Ballroom / GiantSteps / GTZAN / other lawful labeled sets as task-appropriate |
| Structure follow-up | MIREX structure conventions; SALAMI/Harmonix where audio + labels are lawfully available |
| Multi-instrument AMT | task-standard multi-instrument transcription datasets with per-instrument note/event metrics |

### 5.2 Product diversity probe

Maintain a small rights-safe set spanning materially different musical organizations, for example:

- sparse acoustic / solo pitched,
- dense produced pop/rock,
- rhythm-first dance/electronic,
- Latin/groove-heavy,
- jazz/improvisatory,
- expressive classical/acoustic,
- at least one non-Western tradition where lawful material and appropriate interpretation are available.

These labels are probes, not application genres.

The probe answers operational/product questions such as:

- does the model fail on a domain absent from its training distribution?
- are segment embeddings stable?
- do style tags collapse ambiguous/multi-style works?
- does separation produce unusable artifacts on acoustic material?
- does beat tracking fail on expressive tempo?

It is not a substitute for benchmark ground truth.

---

## 6. Common candidate scorecard

Every research agent must produce one row per candidate with the following fields.

```text
candidate
repo / paper / version
code license
weight license
training-data restriction if known
model/checkpoint checksum
install size
model download size
Python/platform requirements
CPU feasibility
GPU feasibility
ARM feasibility
10s latency
30s latency
whole-track latency
peak RAM / VRAM
runtime downloads
failure rate
benchmark dataset/split
primary metrics
per-piece distribution
known domain failures
canonical output shape
ADOPT / RESEARCH / REJECT / REVISIT
```

Do not conflate code license, model-weight license, and training-dataset license.

---

## 7. Track A — foundation representations (#332)

### 7.1 Candidate set is fixed for the first bakeoff

Evaluate:

1. MERT
2. MuQ
3. MusicFM
4. CLaMP3
5. LAION CLAP as the generic audio-text baseline

Do **not** expand the candidate list unless these reveal a clearly missing capability.

MuQ/MuQ-MuLan released weights have non-commercial terms; evaluate them as research candidates unless licensing changes.

### 7.2 Product tasks

The bakeoff is not “which embedding has the highest abstract benchmark score?” Test concrete product tasks:

#### Within-work segment similarity

Given a selected 5–15 s passage, retrieve other passages from the same work.

Qualitatively inspect whether results preserve:

- broad musical identity,
- melody,
- rhythm/groove,
- timbre/production,
- section similarity.

Do not claim these factors are disentangled unless evaluated.

#### Cross-work similarity

Retrieve nearest passages/works from the rights-safe probe corpus.

#### Text-to-passage retrieval

For models supporting text, try neutral factual prompts such as:

- “drums and bass enter”
- “solo piano”
- “dense distorted guitars”
- “sparse vocal passage”

Avoid subjective prompts as the primary evaluation.

#### Cross-representation consistency

CLaMP3 gets an explicit test:

```text
same Work audio segment
↔ corresponding MIDI
↔ corresponding MusicXML/score
```

Measure whether matched representations rank above mismatched passages.

### 7.3 Output contract proposal

Do not persist vectors in production during the bakeoff. Produce a candidate contract for #336:

```ts
type EmbeddingEvidence = {
  model: string
  modelVersion: string
  modality: "audio" | "midi" | "score" | "text"
  span?: { startSeconds: number; endSeconds: number }
  dimensionality: number
  normalized: boolean
  artifactVersionId: string
  vectorRef: string // storage/index reference, not necessarily DB vector column
  provenance: {...}
}
```

The bakeoff may store evaluation artifacts outside the product schema.

### 7.4 Gate

Adopt a canonical embedding path only if it has a compelling combination of:

- meaningful retrieval quality,
- acceptable license,
- practical inference/deployment,
- stable segment embeddings,
- a product capability we actually intend to expose.

A model may win research quality and still be `RESEARCH` because of weight licensing or GPU cost.

---

## 8. Track B — style / instrument / semantic context (#333)

### 8.1 Candidates

- Essentia Discogs-EffNet / related released classifiers,
- MTG-Jamendo baseline/model path where practical,
- winner/research winner from Track A using a lightweight probe,
- one audio-text zero-shot baseline only if it adds a materially different capability.

### 8.2 Product output is context evidence, not routing truth

Target:

```ts
type ContextEvidence = {
  taxonomy: string
  labels: Array<{ label: string; score?: number }>
  scope: "work" | "segment"
  span?: TimeSpan
  calibrated: boolean
  provenance: {...}
}
```

Use multi-label output. A single hard genre string must not become the workspace state machine.

### 8.3 Gate

Before product exposure, inspect:

- top-k quality,
- calibration where possible,
- label taxonomy comprehensibility,
- stability across adjacent segments,
- ambiguity/multi-label behavior,
- culturally diverse failure modes.

If model tags are too unstable or taxonomy-specific, they may still be useful internally as routing/context evidence without prominent user-facing labels.

---

## 9. Track C — source separation (#334)

### 9.1 First question is downstream value, not stem novelty

Source separation should become a first-class evidence layer only if separated sources materially improve product questions.

Evaluate at minimum:

- drums,
- bass,
- vocals,
- other/harmonic remainder.

### 9.2 Candidate strategy

Prefer 2–3 practical checkpoint/inference paths through a maintained harness where possible:

- a BS-RoFormer or Mel-Band RoFormer checkpoint,
- a current Demucs-family baseline if operationally useful,
- one additional maintained model only if it fills a clear stem/quality gap.

Audit checkpoint terms separately.

### 9.3 Downstream tests

For the same mixtures, measure whether stems improve:

- beat/onset evidence on drums,
- bass timing / pitch analysis,
- vocal melody extraction,
- chord recognition on harmonic remainder,
- instrument/source entrance detection,
- arrangement/energy observations.

A separator with a slightly better SDR but no downstream benefit may not be worth the operational cost.

### 9.4 Output contract proposal

```ts
type StemEvidence = {
  role: "vocals" | "drums" | "bass" | "other" | string
  sourceVersionId: string
  artifactVersionId: string
  model: string
  modelVersion: string
  provenance: {...}
}
```

No schema migration during the bakeoff.

---

## 10. Track D — beat / downbeat / tempo / meter (#335)

### 10.1 Correct candidate framing

Current code defaults `BEAT_ENGINE=librosa` and has an optional `beat_this` adapter. Benchmark:

1. current librosa path,
2. Beat This as the primary modern beat baseline,
3. BeatNet primarily for its joint downbeat/tempo/meter/bar-phase value.

Only add Essentia if the first three reveal a clear gap or it is trivial to include as a reference.

### 10.2 Evaluate tasks separately

Do not collapse this into one BPM number.

Measure:

- beat F-measure / task-standard metrics,
- downbeat F-measure,
- tempo accuracy,
- meter/bar-phase accuracy where labels exist,
- local tempo behavior where supported,
- failure rate and per-domain distribution.

MIREX 2025 is useful calibration: Beat This remains a strong baseline but newer systems can outperform it on some sets, so we should benchmark rather than assume either “old” or “SOTA.”

### 10.3 Product implications

The chosen metric-grid evidence should underpin:

- beat/bar representation,
- beat-relative onset analysis,
- groove modules,
- structure alignment,
- notation quantization where appropriate,
- drum/bass pattern comparisons.

Target contract for #336:

```ts
type MetricGridEvidence = {
  beats: number[]
  downbeats?: number[]
  tempoBpm?: number
  meter?: { numerator: number; denominator: number }
  barIndexByBeat?: number[]
  confidence?: number | null
  provenance: {...}
}
```

---

## 11. Track E — generic multi-instrument AMT (#337)

This track is intentionally lower priority.

The question is not “can we transcribe more instruments?” It is:

> Does instrument-separated symbolic evidence enable materially better analysis or representations than audio/stem/foundation evidence alone?

Use current Basic Pitch as baseline, MT3 as permissively licensed research reference if runnable, and YourMT3/YourMT3+ as a quality/reference candidate with GPL implications clearly recorded.

Do not change production transcription routing until this track produces a domain-specific win.

---

## 12. Evidence Graph migration rule (#336)

Do not build a graph database.

Do not add new relational tables before the bakeoffs reveal concrete persistence/query requirements.

During research, outputs may be JSON/NPZ/Parquet/evaluation artifacts.

After A-D, #336 must answer which of these are actually necessary:

- typed Observation distinct from current Insight,
- first-class Relation,
- embedding references / vector index,
- stem references,
- context evidence,
- section/group membership,
- cross-work similarity references.

Prefer existing Postgres/Supabase + JSONB until query/product requirements justify more.

---

## 13. UX V3 runs in parallel (#328)

UX work may proceed without waiting for research results, but it must remain representation-neutral.

Design for capabilities, not today’s exact tabs.

Target shell remains:

```text
Library / Work

Workspace
├─ representation selector
├─ primary canvas
├─ contextual Inspector / Ask
└─ global transport
```

Future-compatible representations include:

- Waveform,
- Spectrogram,
- Piano Roll,
- Score,
- Beat/Bar Grid,
- Structure Timeline,
- Stem Mixer,
- Harmony / Relative-Theory view,
- Similarity/Retrieval view.

### UI content hierarchy

The Inspector should progress:

```text
summary
→ meaningful relationships
→ localized evidence
→ theory/style/cultural explanation
→ provenance/details
```

Do not make engine names, classifier taxonomies, or raw model scores the normal user experience.

### Design references

Mobbin and 21st.dev are pattern libraries only. Hooktheory, Sonic Visualiser, Moises, professional DAW/audio tools, and strong editorial/analysis products are more important references for product interaction semantics.

---

## 14. Platform V3 runs in parallel (#329)

The current Vercel + Oracle + Supabase topology remains the default until a V3 engine creates a real new requirement.

Potential architecture triggers:

| Trigger | Likely response |
|---|---|
| Foundation model fits CPU/RAM | keep current worker / optional cached model |
| Heavy GPU-only model, low request volume | external/on-demand GPU worker before Kubernetes |
| Separation takes minutes on CPU | optional asynchronous GPU compute path |
| multiple concurrent heavy jobs | additional worker(s) / managed containers |
| vector retrieval needed | start with Postgres/pgvector or external index only after measured scale/query need |
| experimental engine rollout | lightweight config/profile/feature flag, not heavyweight SaaS by default |

Do not add Jenkins beside GitHub Actions, Kafka, Kubernetes, service mesh, or Backstage without a problem that specifically requires them.

---

## 15. Human-readable theory / culture contract

V3 must make explanations deeper without pretending one theory vocabulary is universal.

When a concept is detected, the product should be able to answer:

1. **What is it?**
2. **Where is it in this work?**
3. **What evidence supports it?**
4. **What function/relationship does it commonly describe?**
5. **Which theoretical/historical/cultural framework uses this concept?**
6. **What related passage/concept should the user compare?**
7. **Can the user immediately listen/loop it?**

Example: “French augmented-sixth chord” should be explained as a term from Western common-practice chromatic harmony, show the actual chord tones/resolutions when detected, and avoid presenting the label as a universal ontology of pitch organization.

Implementation of a theory concept requires both a trustworthy detector and a vetted educational reference layer. An LLM may explain supplied evidence; it must not create the detection itself.

---

## 16. Learning/reference program for product decisions

The product/research owner should use these to organize domain knowledge before specifying new analytical modules.

### Computational music / MIR

- Meinard Müller, *Fundamentals of Music Processing* and the FMP notebooks.
- Xavier Serra + Julius O. Smith, *Audio Signal Processing for Music Applications*.
- ISMIR tutorials/programs and MIREX task definitions/results.
- Stanford CCRMA DSP, psychophysics/music cognition, and computational-theory curriculum.

### Western tonal theory

- MIT Harmony & Counterpoint I / II.
- MIT Musical Analysis.
- Aldwell & Schachter, *Harmony and Voice Leading*.
- Open Music Theory.

### Popular / groove / style-specific theory

Do not extrapolate the common-practice curriculum to all styles. For new style-aware modules, first identify authoritative scholarship in that domain. Useful organizing concepts include popular-song form, harmonic rhythm, groove/pulse/subdivision/syncopation/microrhythm, production/arrangement, and style-specific cultural histories.

---

## 17. What implementation agents must not do during V3 bakeoffs

They must not:

- choose a production model based on stars/reputation,
- add more candidates because browsing found something interesting,
- modify product schemas before #336,
- expose tags/stems/structure/embeddings in the UI during research,
- hard-code genre-specific product routes,
- call embedding similarity a factual musical explanation,
- call beat-phase distribution “syncopation,”
- infer semantic Verse/Chorus labels from an unvalidated boundary model,
- spend the bakeoff refactoring unrelated application code,
- convert research-only/non-commercial checkpoints into unqualified production dependencies.

---

## 18. Research-agent deliverable contract

Every track ends in a committed report and machine-readable result artifacts.

Suggested layout:

```text
backend/evaluation/analysis_v3/<track>/
  README.md
  run.py
  adapters/
  fixtures_or_manifest/
  results/
    <candidate>.json
  REPORT.md
```

Do not commit copyrighted benchmark audio. Commit manifests, scripts, metrics, and legally redistributable tiny fixtures only.

`REPORT.md` must end with exactly one decision per candidate:

- `ADOPT`
- `RESEARCH`
- `REJECT`
- `REVISIT`

and one architecture recommendation for the track.

---

## 19. Promotion path after research

```text
candidate loads
  ↓
benchmark runs
  ↓
operational/license gate
  ↓
research decision
  ↓
bounded production adapter PR
  ↓
capability registry entry = evaluation_only
  ↓
real-stack/product verification
  ↓
product-quality evaluation
  ↓
experimental / production promotion if justified
```

Do not skip directly from “benchmark winner” to prominent Inspector claim.

---

## 20. First implementation task

The first lower-quality implementation agent should execute **#332 — foundation representation bakeoff**.

Why first:

- it can unlock similarity/retrieval without changing trusted local MIR facts,
- CLaMP3 directly tests our multi-representation premise,
- embeddings can later support #333 tagging,
- it provides concrete persistence/query requirements for #336,
- it is isolated enough to run as evaluation-only work without destabilizing production.

The agent receives a fixed candidate list, fixed product tasks, fixed metrics/operational fields, and a strict stop-before-production-integration rule. It should not perform broad research or choose product direction.

---

## 21. References checked for this plan

Primary/public references include:

- ISMIR 2026 tutorials: https://ismir2026.ismir.net/tutorials
- ISMIR 2025 SSL tutorial: https://ismir2025program.ismir.net/tutorials.html
- MIREX 2025 beat results: https://music-ir.org/mirex/wiki/2025%3AAudio_Beat_Tracking_Results
- MIREX 2025 structure results: https://music-ir.org/mirex/wiki/2025%3AMusic_Structure_Analysis_Results
- CLaMP3 paper: https://aclanthology.org/2025.findings-acl.133/
- MERT: https://github.com/yizhilll/MERT
- MuQ: https://github.com/tencent-ailab/MuQ
- MusicFM: https://github.com/minzwon/musicfm
- CLaMP3: https://github.com/sanderwood/clamp3
- LAION CLAP: https://github.com/LAION-AI/CLAP
- Beat This: https://github.com/CPJKU/beat_this
- BeatNet: https://github.com/mjhydri/BeatNet
- MSST: https://github.com/ZFTurbo/Music-Source-Separation-Training
- MT3: https://github.com/magenta/mt3
- YourMT3: https://github.com/mimbres/YourMT3

Verify upstream status, model licenses, and releases again when each bakeoff actually executes; research software changes.