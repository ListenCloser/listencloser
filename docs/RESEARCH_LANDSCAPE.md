# MIR / Music AI Research Landscape and Adoption Matrix

> **Purpose:** Practical research and adoption reference for hello-ai.
>
> **Status:** Consolidated after the first Analysis V3 bakeoff cycle, 2026-08-29.
>
> **Rule:** Treat measured hello-ai results as stronger evidence than candidate reputation. A new paper, model, or repository is not a reason to reopen a settled decision unless it targets a documented failure mode or product gate. `docs/EVALUATION_DECISIONS.md` is the compact cross-track ledger; this document explains the larger technical landscape and architecture implications.

---

## 1. Current Analysis V3 decisions

The first V3 cycle produced useful negative results as well as promotion candidates. The architecture is no longer waiting for a single universal model.

| Evidence family | Current decision | What we know | Next decision-changing evidence |
|---|---|---|---|
| Specialized MIR | **KEEP / PROMOTE SELECTIVELY** | Exact/localized detectors remain the strongest authority for beat, pitch, chord, and similar factual claims. | Task-specific held-out/product regressions when changing an engine. |
| Perceptual audio evidence | **ADOPT AS MINIMAL EVIDENCE SUBSTRATE** | Low-level, localized measurements are the clearest V3 research→production success and already support deterministic A/B relations. | Product composition in Breakdown/Ask, plus claim-specific sufficiency. |
| Foundation embeddings | **RESEARCH** | #341 measured MERT, MuQ, MusicFM, CLaMP3, and CLAP. No candidate simultaneously demonstrated license, deployment, and product-value justification for a production vector layer. | A scored retrieval/similarity product task that would actually be exposed. |
| Style / instrument context | **RESEARCH / REVISIT** | #355 shows supervised reference value but licensing constraints for Essentia; raw CLAP prompt similarity was not discriminative enough to become factual tags. | Labeled standard-split evaluation, calibration/error slices, cultural/generalization probes. |
| Source separation | **RESEARCH — OPTIONAL / TASK-CONDITIONED** | #480/#521 strongly validate objective stem quality; #477/#486 show that cleaner stems do not automatically improve downstream MIR. | A concrete source-aware user claim with robust real-recording benefit + failure/abstention policy + production-topology evidence. |
| Metric grid / beat | **LEADING PROMOTION CANDIDATE: BEAT THIS** | #474 shows a very large localized beat/downbeat advantage over production librosa on the checkpoint-associated Candombe validation split, while global BPM alone hides failures. | Genuinely independent annotated corpus + runtime/fallback decision + meter evaluation. |
| Generic multi-instrument AMT | **RESEARCH / REFERENCE** | #404 shows promising MR-MT3 quality. #541 shows persistent model reuse only improves mean CPU time ~1.08×; expensive clips remain ~4–5× real time. | A materially different runtime/model/hardware profile *and* downstream product-value proof. |
| Audio-language models | **RESEARCH — SEMANTIC HYPOTHESIS ONLY** | #362 and external benchmark evidence reject treating audio-language prose as exact MIR authority. | Rights-safe real model run: audio-only vs evidence-only vs audio+evidence with claim-level groundedness scoring. |
| Structure | **RESEARCH — RESULT PENDING** | Candidate-neutral scoring/harness work is sufficiently mature. | Materialize the fixed SongFormBench corpus and run the candidates; do not extend the harness first. |
| Piano transcription / notation | **ACTIVE RESULT GATES** | Exact production-profile and audio→score stage-attribution evaluators exist. | Run the real corpus and identify the largest user-visible error contributor before changing algorithms. |

### Architecture implication

The product should not have one universal intermediate representation. It should have a small set of evidence families with different authority and cost:

```text
source Work / audio Version
  │
  ├─ specialized MIR
  │    beats / downbeats / pitch / chords / note events / exact symbolic transforms
  │
  ├─ perceptual audio evidence
  │    dynamics / spectrum / onset activity / texture / localized changes
  │
  ├─ optional task-conditioned source views
  │    stems or other derived views requested only when a claim benefits
  │
  ├─ optional research representations
  │    embeddings / context tags / multi-instrument symbolic evidence
  │
  └─ optional semantic hypotheses
       audio-language model outputs
            │
            ▼
      typed evidence + provenance
            │
      claim-specific sufficiency
        / fallback / abstention
            │
            ▼
   deterministic observations / relations
            │
            ▼
 synchronized representations + Breakdown
            │
            ▼
 Ask explains and cites evidence; it does not invent detector facts
```

This is the durable V3 direction unless future benchmarks contradict it.

---

## 2. Field map: paradigms that should coexist

### 2.1 Signal-processing / classical MIR

Strengths:

- interpretable and localizable,
- inexpensive,
- mature metrics,
- useful for beat/chroma/onset/spectral/structure primitives.

Examples: librosa, Essentia, Sonic Annotator/Vamp, recurrence/novelty methods.

**hello-ai role:** keep as inexpensive evidence and baselines where measured quality is adequate. Replace individual engines only with matched-domain evidence.

### 2.2 Symbolic / computational musicology

Strengths:

- precise pitch/rhythm/harmony relationships,
- theory-aware operations,
- score/notation integration,
- corpus analysis.

Examples: music21, Partitura, Symusic, pretty_midi.

**hello-ai role:** high-authority when the symbolic evidence itself is trustworthy. MIDI and score are not universal facts about every recording.

### 2.3 Task-specific neural MIR

Strengths:

- strong quality on hard perception tasks,
- localized outputs,
- benchmarkable task contracts.

Examples include Basic Pitch / Transkun, lv-chordia, LStoM, Beat This / BeatNet, source separators, and specialized notation models.

**hello-ai role:** default candidate class for precise claims when it wins a task-standard evaluation and fits operations/licensing.

### 2.4 Music foundation representations

Examples: MERT, MuQ, MusicFM, CLaMP3, CLAP-family models.

Useful for similarity, retrieval, broad transfer, and context features. They are not intrinsically more authoritative than specialized MIR.

**hello-ai measured result (#341):** keep all first-round candidates at `RESEARCH`; do not create a production vector/embedding layer yet.

### 2.5 Source-aware audio

Source separation can create drums/bass/vocals/other views that make some downstream evidence easier to estimate.

**hello-ai measured result (#477/#480/#486/#507/#521):** source isolation quality is real, but downstream value is claim-dependent. Keep mixture evidence primary and treat stems as optional immutable `StemReference` artifacts.

### 2.6 Audio-language / multimodal reasoning

Useful for language interfaces and semantic synthesis. Risks include hallucination, poor calibration, weak temporal grounding, and high deployment cost.

**hello-ai role:** optional semantic hypothesis/explanation layer downstream of trusted evidence. Exact beat/key/pitch/chord/instrument claims require specialized evidence or separate task validation.

### 2.7 Human / corpus / theory systems

Hooktheory and expert music-breakdown media demonstrate the *information architecture* users value: synchronized examples, relative relationships, sections, comparison, and explanation tied back to sound.

**hello-ai role:** use these as product/explanation references, not as justification to hard-code one theoretical tradition.

---

## 3. Measured foundation-model landscape (#332 / #341)

The first fixed bakeoff evaluated MERT, MuQ, MusicFM, CLaMP3, and CLAP.

| Candidate | Measured CPU 10 s | Measured CPU 30 s | Modalities relevant here | Decision | Main blocker / uncertainty |
|---|---:|---:|---|---|---|
| MERT | 0.36 s | 1.24 s | audio | RESEARCH | released weight terms are non-commercial; no exposed product task win |
| MuQ | 1.23 s | 2.81 s | audio | RESEARCH | non-commercial released weights; no exposed product task win |
| MusicFM | 0.69 s | 2.55 s | audio | RESEARCH | non-commercial released weights; setup/product value |
| CLaMP3 | 1.67 s | 2.90 s | audio + text + symbolic | RESEARCH | cross-modal probe too small; product retrieval value unproven |
| CLAP | ~0.10 s | ~0.10 s* | audio + text | RESEARCH | global/cropped behavior and weak prompt discrimination in tiny product probe |

*The evaluated CLAP path crops to a fixed duration.

CLaMP3’s corrected aligned MAESTRO audio↔MIDI probe produced:

- Recall@1: **0.20**
- Recall@5: **1.00**
- MRR: **0.49**

Five pairs are not enough to promote or reject the cross-modal idea.

### Foundation-model decision rule

Do not benchmark foundation models in the abstract. Reopen this track only for a concrete product task such as:

- “find passages like this,”
- cross-work similarity,
- text-to-passage retrieval,
- representation consistency,
- library clustering/search.

A production embedding layer is justified only when a scored user task, rights, operational fit, and persistence/query requirement all exist.

---

## 4. Style, instrument, mood, and semantic context (#333 / #355)

### Essentia as a reference

Official Discogs-EffNet / MTG-Jamendo heads provide useful supervised reference evidence. #355 records upstream test metrics such as:

| Task | PR-AUC | ROC-AUC |
|---|---:|---:|
| genre | 0.20 | 0.88 |
| instrument | 0.20 | 0.78 |
| mood/theme | 0.14 | 0.76 |

These are upstream reference metrics, not matched hello-ai measurements. Open/pretrained licensing is not suitable as an unquestioned default commercial dependency; treat Essentia as a strong reference or revisit commercial licensing if measured value warrants it.

### CLAP as a zero-shot baseline

The #332/#355 tiny product probe showed poor prompt discrimination: seven factual prompts collapsed heavily onto the same retrieved items, and `solo piano` did not reliably retrieve the MAESTRO piano examples.

That does **not** prove CLAP is generally useless. It does prove that raw cosine similarity is not a factual tag confidence.

### Context evidence contract

Validated context should be:

- multi-label,
- scoped to work or segment,
- explicitly taxonomy-specific,
- called `score` unless calibrated,
- allowed to influence salience/explanatory framing,
- forbidden from becoming a rigid genre router.

Remaining gate: standard labeled split + calibration + ambiguity/cultural failure analysis.

---

## 5. Beat / downbeat / tempo / meter (#335)

### Production baseline

Current production uses librosa-derived beat evidence and does not supply validated downbeat/meter evidence.

### Beat This

#474 evaluated Beat This `single_final0` on the published Candombe `single.split` validation rows and found:

| Metric | production librosa | Beat This |
|---|---:|---:|
| mean beat F1 | 0.3847 | **0.9989** |
| reference beat coverage | 33.46% | **100%** |
| median matched beat error | 40.6 ms | **10.9 ms** |
| mean downbeat F1 | unsupported | **1.0000** |
| tempo accuracy @4% | 100% | 100% |

The key lesson is architectural: **global BPM correctness is not enough** for groove, phase, bar-relative comparison, structure alignment, or notation.

### Current decision

Beat This is the leading `MetricGridEvidence` promotion candidate, not yet the global production default.

Before promotion:

1. score a genuinely independent annotated corpus not used for this checkpoint’s training/validation;
2. preserve coverage + event-localization metrics, not BPM alone;
3. decide asynchronous CPU/runtime/fallback behavior;
4. evaluate meter separately;
5. rerun beat-relative downstream regressions.

BeatNet remains relevant primarily if it supplies validated meter/bar-phase evidence that Beat This does not.

---

## 6. Harmony, tonality, melody, and symbolic analysis

### Chords

`lv-chordia` remains the production audio-chord foundation after internal evaluation. Do not restart engine shopping without a documented domain failure.

### Key / theory

music21 remains useful for symbolic/theory operations. Theory labels must state the analytical framework and should not be presented as culturally universal.

### Melody

LStoM remains the production-default symbolic melody extraction path after internal evaluation. Its archived upstream status is less important than owned model provenance, tests, and domain validation.

### Symbolic utilities

- **Partitura:** strong modern score/MIDI/MEI utility; Apache-2.0.
- **Symusic:** fast modern symbolic representation/transformations; useful if measured performance or glue-code simplification warrants migration.
- **pretty_midi:** continue where it is already a sufficient boundary.
- **note-seq:** archived; do not adopt as a new central dependency.

### Rule

Symbolic relationships can be highly trustworthy, but only after the audio→symbolic evidence path itself clears the relevant accuracy gate.

---

## 7. Generic multi-instrument transcription (#337)

MR-MT3 is the strongest current research/reference path, but it does not clear the operational gate for default CPU deployment.

#404 established useful quality/reference evidence. #541 then compared fresh CLI processes with one persistent model across the exact same five 30-second Slakh excerpts.

| Metric | fresh process | resident model |
|---|---:|---:|
| mean time / 30 s | 83.107 s | 79.810 s |
| median time / 30 s | 90.701 s | 83.306 s |
| mean paired speedup | — | **1.0828×** |
| one-time model load | — | **2.918 s** |

The two heaviest clips were essentially unchanged: `117.018→115.746 s` and `143.739→143.866 s`. CLI and resident outputs matched semantically.

### Decision

**MR-MT3 = RESEARCH / reference.** Repeated loading is not the primary bottleneck; CPU inference is.

Do not:

- add a production MR-MT3 dependency,
- build a resident worker solely to recover wrapper overhead,
- make multitrack symbolic transcription the universal substrate.

Revisit only when there is both:

1. a materially different operations profile (different runtime/model/hardware), and
2. a product capability whose quality measurably depends on instrument-aware symbolic evidence.

---

## 8. Source separation (#334)

### What the measurements say

Objective isolation is strong:

- #480 BabySlakh: mean ΔSI-SDR **+13.983 dB drums**, **+12.900 dB bass**.
- #521 MUSDB18 preview, all 50 test tracks:
  - drums **+13.3558 dB**, 50/50 improved;
  - bass **+12.9033 dB**, 47/50 improved;
  - other **+8.9048 dB**, 49/50 improved;
  - vocals **+12.0349 dB**, 48/50 improved.

But the negative tail matters: some bass/vocal rows degrade catastrophically.

Downstream value is not automatic:

- #477: drums-vs-mixture production beat F1 mean delta **-0.0045**.
- #486: bass stem improves onset-only Basic Pitch F1 by **+0.0578** mean, while onset+offset mean delta is **-0.0088** and recall drops sharply.

Operations are plausible but not free:

- #507 180 s audio: ~85.9 s hosted x86 CPU / ~152.3 s hosted ARM CPU;
- peak RSS roughly 1.6–1.8 GB;
- actual Oracle concurrency/cold-start/cost remains unmeasured.

### Current architecture

Source separation is **not universal preprocessing**.

Use:

```text
mixture evidence = primary
optional StemReference = immutable cached derived artifact
stem-specific detector evidence = claim evidence
claim sufficiency = decides whether stem evidence is usable
mixture fallback / abstention = required for weak/conflicting stem evidence
```

Do not run a RoFormer tournament merely because newer separators exist. Revisit a challenger when a concrete source-aware claim has a failure mode or promotion target.

---

## 9. Perceptual evidence and musical relations (#455 / #457 / #459 / #460)

This is the most important V3 convergence path because it has already moved from evaluation into bounded production contracts.

Examples of useful low-level evidence:

- RMS/amplitude dynamics,
- spectral centroid/band energy,
- onset strength/activity,
- register/spectral distribution,
- temporal windows over the same source Version.

These measurements are valuable because they are:

- localizable,
- cheap,
- interpretable,
- comparable between spans,
- compatible with abstention,
- useful across genres without pretending to be a high-level cultural interpretation.

### Product rule

A low-level measurement is not automatically a semantic claim:

- spectral centroid ≠ “brightness” unless wording is explicitly validated;
- onset density ≠ “excitement”;
- RMS ≠ calibrated perceptual loudness;
- event density ≠ “busyness” or syncopation.

The progression is:

```text
typed evidence
→ sufficiency
→ deterministic observation/relation
→ literal grounded finding
→ optional theory/context explanation
```

This is the preferred way to add breadth without creating a bespoke detector for every future style.

---

## 10. Structure / form

The structure track has enough evaluation infrastructure. The current blocker is evidence, not architecture.

Use established boundary/grouping metrics and keep separate:

1. boundary detection,
2. repeated-section grouping,
3. semantic section labels.

Do not require Verse/Chorus labels before validated boundaries/grouping can be useful.

Current next step: use the frozen SongFormBench selection from #550/#516 and produce candidate results. Do not expand the harness first.

---

## 11. Audio-language models (#339 / #362)

The correct product experiment is not “which model writes the nicest paragraph?”

It is:

```text
same audio case + same question
  ├─ audio only
  ├─ structured hello-ai evidence only
  └─ audio + structured hello-ai evidence
```

`audio + evidence` is useful only if it increases supported claims/usefulness without worsening:

- contradiction,
- unsupported claims,
- citation quality,
- abstention,
- temporal grounding,
- specificity.

External CMI-Bench/MUSE evidence is an important warning that general audio-language systems can trail specialized MIR and struggle on basic music relations.

### Decision

No audio-language model is a production factual authority. Music Flamingo / Audio Flamingo / Qwen-class models remain research candidates or controls. A future Ask path may use raw audio as *additional semantic context* only after the matched grounded-value gate.

---

## 12. Notation / transcription / score

The current score problem must be decomposed rather than treated as one engraving bug.

Active evaluation work separates:

```text
audio
→ predicted note events
→ metric grid
→ quantization / durations / voices / staffing
→ MusicXML
→ renderer
```

#540 targets exact production Basic Pitch vs Transkun profiles. #502 targets audio→predicted-MIDI→Score stage attribution.

Next action is the real result on a fixed corpus, then fix the largest measured contributor. Do not add another notation abstraction before those results exist.

---

## 13. Evidence authority and trust tiers

Use trust/maturity per claim, not per model brand.

### Tier 1 — measured/localized evidence

Examples: beat timestamps, note events, chord candidates, RMS windows, stem-derived detector outputs.

Requirements: exact source Version/span, engine/model version, parameters, provenance, known metric/domain.

### Tier 2 — deterministic derived observations

Examples: “span B has higher measured RMS amplitude than span A,” harmonic interval derived from validated notes.

Requirements: evidence support refs + deterministic computation + sufficiency.

### Tier 3 — model-estimated context

Examples: style/instrument tags, embedding similarity, source-role hypotheses.

Requirements: task validation, calibration when called confidence, taxonomy/model provenance, graceful ambiguity.

### Tier 4 — interpretive/semantic explanation

Examples: “the arrangement opens up,” stylistic/function explanations.

Requirements: cite lower-tier support, state framework/assumptions where relevant, abstain when evidence does not support the wording.

An LLM can compose or explain evidence; it does not promote Tier 3/4 language into Tier 1 fact.

---

## 14. Persistence / Evidence Graph direction (#336)

Keep the conceptual Evidence Graph; do **not** build a graph database.

Prefer current Postgres/Supabase + immutable Artifact/Version lineage + typed JSON/domain contracts until a real query need justifies another persistence primitive.

Useful conceptual entities include:

- source Version / time span,
- Evidence,
- Observation,
- Relation,
- support/provenance references,
- optional StemReference,
- optional embedding/vector reference,
- ContextEvidence,
- section/group membership.

Physical schema changes require concrete product/query pressure. The graph is an ontology and dependency model first.

---

## 15. Product/commercial references

### Hooktheory

Learn from relative notation, synchronized chord/melody playback, section context, cross-key relationships, and educational explanations tied to actual passages. Do not copy its Western tonal ontology as a universal one.

### Sonic Visualiser / Vamp

Learn from synchronized representations, annotation layers, multiple time resolutions, and plugin-like evidence extraction.

### Moises / AudioShake

Learn from stems as user-manipulable source views. hello-ai should still require evidence gates before using stems as factual analysis inputs.

### Cyanite / commercial tagging systems

Learn from multi-label/segment-level context and versioned model outputs; raw taxonomy labels remain model-specific evidence.

### DAWs / production tools

Learn from persistent time, source/layer orientation, transport, and low-friction comparison. The product should feel like one musical object viewed through multiple representations, not a set of disconnected analysis dashboards.

---

## 16. Research communities and benchmark culture

Follow:

- ISMIR / MIREX for task definitions, evaluation practice, and music-specific research;
- MTG/UPF, QMUL C4DM, AudioLabs Erlangen, NYU MARL, Stanford CCRMA;
- Spotify Research, Adobe Research, and other groups connecting music understanding with product interaction;
- ICASSP / DAFx for signal processing and source separation;
- CHI / NIME / Audio Mostly for music interaction and human-centered AI.

Important methodological references:

- MARBLE for music-representation evaluation;
- MIREX task metrics rather than private aggregate scores;
- mir_eval / task-standard matching where applicable;
- standard labeled splits with train/validation/test provenance recorded explicitly.

---

## 17. Cultural / framework boundary

Do not equate “general music understanding” with common-practice tonal analysis or Western-pop taxonomies.

For any style/framework-specific explanation:

1. identify the analytical tradition or vocabulary;
2. state prerequisites and applicability;
3. distinguish measured evidence from interpretation;
4. validate on representative material;
5. retain universal evidence even if context classification is uncertain.

Piano, jazz, house, reggaeton, hip-hop, classical, orchestral, and non-Western traditions should be **diversity probes and framework contexts**, not hard-coded product forks.

---

## 18. Current recommendation matrix

| Area | Current state | Allowed next move |
|---|---|---|
| Transcription | Basic Pitch + Transkun production profiles | Run #540 real corpus; change routing only from result |
| Chords | lv-chordia | Keep; reopen only for concrete domain failure |
| Key/theory | music21 + gated theory | Keep; expand claims only with framework/evidence gate |
| Melody | LStoM | Keep; validate new domains/interpretations separately |
| Rhythm | librosa production; Beat This leading candidate | Independent MetricGrid result + ops/meter gate |
| Perceptual evidence | promoted minimal substrate | Build relations/grounded product composition, not descriptor sprawl |
| Structure | eval harness mature | Materialize fixed corpus and run candidates |
| Style/instrument | research context evidence | Labeled scored/calibrated run |
| Foundation embeddings | no production layer | Reopen only for scored retrieval/similarity product task |
| Source separation | optional research StemReference | Concrete source-aware claim; no universal preprocessing |
| Multi-instrument AMT | MR-MT3 research/reference | Revisit only with new ops profile + downstream value |
| Audio-language | semantic hypothesis research | Real matched grounded-QA run on legitimate GPU |
| Similarity/search | no production vector layer | Depend on a demonstrated retrieval UX need + embedding gate |
| Breakdown | primary understanding surface | Consume grounded observations/relations with time + provenance |
| Ask | evidence-grounded | Cite evidence/relations; raw-audio semantic augmentation only after #339 gate |
| Generation | future | Defer until understanding/evidence architecture is stable |

---

## 19. What not to build now

Do not spend the next cycle on:

- a universal embedding/vector database without a scored retrieval product;
- eager source separation for every upload;
- another separator tournament without a source-aware claim target;
- MR-MT3 process-caching/warm-worker tuning as if wrapper overhead were the bottleneck;
- a hard genre router;
- raw CLAP/LLM scores displayed as factual confidence;
- a graph database for the conceptual Evidence Graph;
- a universal MIDI/score ontology;
- semantic Verse/Chorus claims before structure evidence is validated;
- more evaluation harness abstraction when the owning track already has a runnable result gate.

---

## 20. Research issue template

Every new bakeoff or reopened track should state:

```markdown
# Product decision
What user capability or architecture choice changes if this succeeds?

# Existing evidence
Which prior result or failure mode requires reopening the question?

# Candidate / baseline
Exact system, version/checkpoint, code license, weight license, training/data restrictions.

# Evaluation
Dataset/split/sample IDs, task-standard metrics, per-piece distribution, operational metrics.

# Product gate
What numeric/qualitative result is sufficient to change routing, exposure, or persistence?

# Output contract
Typed evidence + provenance + maturity.

# Failure / abstention
How does the product behave when the evidence is missing, weak, or contradictory?

# Decision
ADOPT / RESEARCH / REJECT / REVISIT.
```

The key discipline is: **once a runnable harness exists, the default next PR is result-bearing, not another harness extension.**
