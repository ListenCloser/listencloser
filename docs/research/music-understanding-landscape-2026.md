# Music Understanding Landscape 2026 — Product Architecture V3

> **Status:** Research/strategy input. No production capability is promoted by this document.
> **Date:** 2026-08-27
> **Scope:** MIR, symbolic analysis, foundation representations, audio-language models, source separation, product taxonomy, evidence architecture, evaluation and R&D roadmap for hello-ai.

## Executive recommendation

If hello-ai were designed from scratch in 2026, it should **not** be an audio → MIDI → symbolic-facts → Inspector pipeline. It should be a **multi-representation evidence system** in which audio, stems, beat/bar scaffolding, symbolic note events, score structure, learned embeddings, and semantic model estimates are peers with different trust levels.

The architectural center should move from **MIDI** to a canonical **time-aligned evidence layer**. MIDI remains extremely valuable for note-level pitch/timing, transcription inspection, notation and symbolic theory, but it should no longer be the ontology through which all music is interpreted.

Three changes matter most:

1. **Embeddings become first-class evidence.** Segment/work embeddings are not merely opaque tagging helpers; they enable similarity, repetition, semantic retrieval, cross-work comparison and multimodal consistency. CLaMP3 is unusually relevant because it aligns audio, MIDI, score and text; MERT, MuQ, MusicFM and CLAP remain important bakeoff baselines.
2. **Source separation becomes analysis infrastructure.** Drums, bass, vocals and other/harmonic stems should feed beat/groove, melody, arrangement, instrumentation and section-change analysis. The success criterion is downstream analysis lift, not SDR alone.
3. **The user-facing product shifts from a taxonomy of MIR tasks to an interactive explanation model.** The best default experience is closer to a high-quality human breakdown: what happens, where it happens, what changed, how layers relate, and what evidence supports the explanation.

The present Analysis V3 strategy in `MASTER_SPEC.md`, `RESEARCH_LANDSCAPE.md`, issue #327 and PR #338 is directionally strong. The main upgrades recommended here are: elevate embeddings and stems from “candidate capabilities” to architectural peers; replace a flat Insight mental model with relational evidence sufficient for cross-section explanations; broaden the beat bakeoff beyond Beat This because MIREX 2025 systems surpassed it; and make the product taxonomy explicitly composition/performance/arrangement/sound/structure rather than Harmony/Melody/Rhythm/Structure.

---

## 1. Current hello-ai architecture, verified from main

Current production truth is governed by runtime code and `backend/config/capabilities.json`, not historical docs.

### Product/runtime

- One persistent musical Work with synchronized representations, playback and selection.
- Representations: Waveform, Piano Roll, Score, Spectrogram, Compare.
- Playback sources are independent from representations: Original, Transcription, Score when artifacts exist.
- Analysis is persisted and exposed through Inspector, annotations and Ask subject to capability policy.
- Durable worker + Supabase queue/storage; Vercel/Next.js proxies to FastAPI.

### Current music engines / evidence

**Transcription**
- Basic Pitch / specialist Transkun routing historically, depending on profile.
- Output is MIDI/note entities and rendered transcription audio.

**Notation**
- MIDI → quantized MusicXML, grand staff, score playback.

**Harmony**
- Audio chords: lv-chordia, production.
- Global key: music21 on MIDI, production.
- Roman numeral / harmonic function: deterministic interpretation when chord + key evidence are trusted.
- Cadence, key regions, voice leading, harmonic rhythm remain withheld/evaluation-only.

**Melody**
- LStoM symbolic melody extraction, experimental; POP909 held-out F1 in registry 0.768.
- Register extrema, interval summary, conservative contour/activity derivations inherit the model’s domain limitations.

**Rhythm**
- Audio beat/tempo engine; current strategic docs indicate librosa is the present baseline.
- MIDI + beat derived density, rests/gaps, beat-relative onset distribution.
- No validated syncopation claim.

**Structure**
- Evaluation-only librosa CENS/recurrence/novelty baseline; older All-In-One metadata is acknowledged as possible registry drift.

### Current architecture in one line

```text
mixed audio
  ├─ transcription → MIDI/notes → notation + symbolic analysis
  ├─ beat/tempo
  ├─ audio chords
  └─ waveform/spectrogram
       ↓
  persisted Entities/Insights/Spans/Alignments
       ↓
  Inspector / annotations / Ask
```

### Keep / challenge

Keep: persistence, provenance, capability gating, synchronized transport/selection, immutable lineage, precise engine adapters, “unknown is valid”, and evaluation-first exposure.

Challenge: MIDI centrality, score as privileged endpoint, the flat analysis taxonomy, micro-feature-by-micro-feature detector growth, and the assumption that the LLM should only verbalize already-human-designed MIR facts.

---

## 2. What the 2026 landscape says

### 2.1 Classical MIR is still indispensable

MIREX 2025 continues to evaluate beat tracking, audio chord estimation, music structure, key, transcription, captioning and Music Reasoning QA. Traditional MIR has not been displaced; it remains the best way to get calibrated, localized outputs for many exact tasks.

Important operational implication: foundation models should **not** replace precise temporal MIR outputs simply because they are newer.

### 2.2 The meaningful change is representation learning

MARBLE now supports or tracks MERT, MusicFM, MuQ, MuQ-MuLan, CLaMP3, DaSheng and Qwen audio encoders. This makes it practical to compare learned representations on common downstream tasks instead of adopting models based on paper reputation.

The core product implication is larger than “better genre tags”: embeddings can serve as a general substrate for similarity, section grouping, retrieval, semantic search and cross-modal comparison.

### 2.3 Audio-language models are useful, but not trustworthy enough to be sole detectors

Spotify LLark demonstrated music-specific instruction following across music understanding, captioning and reasoning, but its repository does not ship trained weights. Qwen2.5-Omni provides a deployable Apache-2.0 multimodal model with an audio tower, but it is a generalist and its music localization/calibration must be evaluated separately.

The right role today is not “LLM last” or “LLM first.” It is **LLM as an evidence-aware interpreter and hypothesis generator**, with model-estimated claims explicitly distinguished from measured/localized evidence.

### 2.4 Source separation has crossed from remix feature to infrastructure candidate

RoFormer-family systems and maintained harnesses such as Music-Source-Separation-Training support modern separation architectures; commercial systems such as AudioShake expose not just 4-stem separation but lead/backing vocals, guitar types, piano, keys and strings.

This matters because mixed-audio MIR confounds sources. A drum stem can make groove analysis easier; a bass stem can expose bass/drum relationships; a vocal stem can improve melody and section-entry analysis; stem activity itself becomes arrangement evidence.

### 2.5 Commercial products validate a broader taxonomy than classical theory

Cyanite exposes valence/arousal, energy, emotion, voice, era, instrument presence/tags, mood, genre/subgenre, movement, character, captions, BPM, key and similarity. Moises combines stems, key/chords, metronome, sections and practice workflows. Hooktheory’s value is synchronized relational notation rather than raw score. Sonic Visualiser demonstrates the power of aligned layers and annotations.

The competitive signal is clear: “music understanding” in products spans **composition + performance + arrangement + production + semantics + similarity**, not only harmony/melody/rhythm.

---

## 3. Technology map

### A. Classical MIR

- **Beat/downbeat/meter:** Beat This is a strong reproducible modern baseline. MIREX 2025 reports BeatU and KG-ApolloBeats variants ahead of the Beat This baseline on its published test sets, so the bakeoff should include a reproducibility investigation of newer MIREX systems rather than treating Beat This as the ceiling. BeatNet remains useful where joint beat/downbeat/meter output matters.
- **Chords:** keep lv-chordia as hello-ai’s production baseline until matched-domain evidence shows a better option. MIREX still treats chord segmentation and vocabulary explicitly; evaluate root/maj-min/sevenths/segmentation separately.
- **Key:** global key from symbolic evidence is useful but insufficient for modulation/local tonality.
- **Structure:** do not conflate boundary detection, repeated-section grouping and semantic labels. Embedding/self-similarity approaches may be more valuable product-wise than forcing verse/chorus labels.
- **Transcription:** continue specialized transcription routing. Generic multi-instrument AMT is research, not a universal substrate.
- **Source separation:** evaluate RoFormer-family checkpoints/harnesses and commercial references.
- **Tagging/instrument/mood:** Essentia model ecosystem and MTG-Jamendo remain strong reference baselines; licensing is a first-class issue.

### B. Symbolic MIR

- **music21:** keep for computational musicology/theory operations; do not stretch into general audio perception.
- **Partitura:** preferred active score/MIDI/MEI utility candidate for robust notation-aware operations.
- **pretty_midi:** useful lightweight MIDI manipulation, but not a music-theory ontology.
- **jSymbolic:** useful descriptive symbolic feature reference; avoid blindly exposing hundreds of features.
- **LStoM:** retain as an evaluated specialized baseline despite archived upstream status; its validated domain is limited.
- **Piano_SVSep:** valuable for engraving/voice/staff separation, not melody identity.
- **Motif/form:** avoid custom interval-window product claims without corpus validation.

### C. Foundation representations

| Candidate | Main value for hello-ai | License/product caveat | Priority |
|---|---|---|---|
| CLaMP3 | audio/MIDI/score/text shared space; semantic search and cross-modal retrieval | MIT code; verify released weight terms | highest R&D |
| MERT | strong music-specific SSL baseline; broad probing literature | verify checkpoint/data terms | high |
| MuQ | modern music SSL | code MIT; common released weights are non-commercial CC-BY-NC | high research, production risk |
| MuQ-MuLan | music-text retrieval / zero-shot tags | same weight caveat | high research |
| MusicFM | music representation and structure reference | verify exact checkpoint terms | high |
| LAION-CLAP | generic audio-text baseline | less music-specific; weight/data review needed | baseline |
| Qwen audio encoder | generalist modern audio representation, already included in MARBLE | heavier/generalist | research |
| DaSheng | broad audio representation baseline | less music-specific | secondary |

A “winner” may differ by task. Do not choose one universal embedding model unless product tasks justify it.

### D. Audio-language models

Use dedicated evaluation prompts over localized clips, not whole-song vibes.

Tasks worth testing:
- instrument/source descriptions,
- broad style attributes,
- section-change descriptions,
- production attributes,
- comparative questions between two selected spans,
- evidence-conditioned explanation quality.

Tasks not safe as sole audio-language claims without validation:
- exact chord sequences,
- exact beat grids,
- precise note transcription,
- localized harmonic function,
- exact section boundaries.

### E. Source separation

Candidate families/harnesses:
- Mel-Band RoFormer / BS-RoFormer,
- HTDemucs as a durable baseline,
- modern MSST-supported architectures (SCNet, BandIt variants, BS-Mamba/Conformer etc.) where checkpoint/license quality is documented,
- AudioShake as a commercial quality/product benchmark.

Do not adopt UVR “best model” folklore as architecture. UVR is useful as an ecosystem/interface, but production decisions require exact checkpoint provenance, license and reproducible metrics.

### F. Toolkits

- **Essentia:** broadest “batteries included” MIR/model reference; strong for tags/embeddings/DSP; commercial licensing must be reviewed because open-source licensing is not equivalent to permissive embedding in a commercial backend.
- **librosa:** keep as baseline/DSP utility; not a source of semantic truth by itself.
- **madmom:** still useful academically, but dependency age/maintenance and model licensing make it less attractive as a new central production dependency.
- **mir_eval:** standard evaluation metrics; keep/use.
- **mirdata:** standard dataset loaders, validation and annotation access; strongly prefer for reproducibility when available.
- **MSAF:** research baseline/reference for structure, not obvious new production center.
- **Partitura:** active symbolic infrastructure candidate.

---

## 4. Lab / ecosystem map

- **MTG / UPF:** Essentia, large-scale tagging datasets, MIR, trustworthy/music AI. Directly relevant to tagging, embeddings, evaluation and product baselines.
- **CPJKU:** beat tracking, symbolic score/performance tooling, Partitura, madmom, piano/score work. Directly relevant to beat + symbolic architecture.
- **Queen Mary C4DM:** semantic audio, source separation, MIR, Sonic Visualiser/Vamp lineage. Relevant to layered analysis/UI and evaluation culture.
- **International Audio Laboratories Erlangen:** synchronization, structure, decomposition, FMP-style explainable MIR. Relevant to structure/education.
- **Spotify Research:** large-scale representation/retrieval and LLark-style music language reasoning. Relevant to Ask and embeddings.
- **Adobe Research:** audio editing/separation/generation and human-centered creative interfaces. Relevant to production-facing workflows.
- **CCRMA / MARL / IRCAM:** broad MIR, performance, audio, music cognition and interaction; especially relevant to performance/expression and educational framing.
- **ByteDance / Chinese MIR groups / Tencent AI Lab:** important recent contributors to transcription, melody, music foundation models and multimodal retrieval. Track repos/model cards rather than assuming company-wide availability.

No single lab supplies the complete product stack; hello-ai should deliberately compose specialized research ecosystems.

---

## 5. New user-facing analysis taxonomy

Do not make Harmony / Melody / Rhythm / Structure the top-level product IA. Those are useful backend families, but poor universal product categories.

Recommended default taxonomy:

### Overview
The shortest useful answer: style/context estimates, tempo/meter, key where meaningful, major sections, active sources, energy arc, and a handful of evidence-backed “what changes” findings.

### Composition
Melody, harmony, bass movement, rhythmic vocabulary, motives, tonal organization. This is where classical theory lives — but only when applicable.

### Groove
Beat/downbeat, subdivision, swing, drum patterns, bass/drum interaction, syncopation only when validated, loop recurrence.

### Arrangement
Source/layer entrances and exits, density, register/orchestration, stem activity, role relationships, transitions.

### Sound
Timbre, spectral balance, brightness, texture, stereo/spatial cues, production effects when estimable, source character.

### Structure
Boundaries, repeated sections, similarity groups, transitions, build/drop/breakdown, chorus/verse labels only when supported.

### Performance
Timing deviation, rubato, articulation, dynamics, phrasing, expressive execution; most valuable in performed/acoustic contexts.

### Relationships / “Why?”
Not a raw detector family. Cross-evidence statements such as “chorus 2 feels larger because drum density rises, bass enters, vocal register increases and high-frequency energy increases.”

Style/genre is **context metadata** that changes emphasis and interpretation, not a permanent top-level silo.

---

## 6. Genre/style-aware analysis matrix

| Domain/context | High-value analysis | Lower priority / caution |
|---|---|---|
| Classical piano | score, voices, harmony, form, melody, rubato, articulation, dynamics, phrasing | genre tags, stem separation usually secondary |
| Jazz | extended harmony, harmonic rhythm, ii–V/turnarounds, bass movement, swing/subdivision, form/choruses, improvisational contour | simplistic global key/Roman numeral story can mislead |
| Pop | sections, vocal melody, chords, bass/drums, arrangement entrances, energy, similarity/repetition | score often secondary |
| Rock | drums/bass/guitar activity, sections, riffs, energy, instrumentation, harmony | detailed notation rarely default |
| House/techno | beat/downbeat/bar grid, kick pattern, offbeat hats, bass groove, loops, build/drop, spectral energy, layer entrances | sheet music should be contextual, not center |
| Reggaeton / Latin urban | dembow-like rhythmic relation, percussion layers, bass/drum interaction, vocal melody, loops, sections, energy/arrangement | avoid reducing Latin styles to a single rhythm template |
| Hip-hop | drum programming, sampling/loop recurrence, bass, vocal flow/prosody, sections, texture, energy | Western tonal harmonic analysis may be low-value |
| R&B | vocal melody/runs, harmony, groove, bass/drum pocket, arrangement/texture | rigid chord labels may underspecify voicings/production |
| Orchestral / film | instrumentation/orchestration, register, dynamics, leitmotif/similarity, harmony, form, texture | generic 4-stem separation is too coarse |

Routing rule: context adjusts ranking, vocabulary and recommended views. It should not disable universal evidence or hard-route the UI.

---

## 7. Universal evidence vs contextual interpretation

This distinction should become the core architecture.

### Universal / broadly reusable evidence

- audio segments + duration,
- waveform/spectrogram/loudness/energy,
- beat/downbeat/bar candidates,
- onset events,
- pitch/note candidates,
- chord candidates,
- source-separated stems and per-stem activity,
- embeddings at work/section/segment levels,
- repetition/self-similarity,
- source/instrument/style probabilities,
- section boundary/group candidates.

### Contextual / domain interpretation

- four-on-the-floor,
- dembow-like groove,
- swing feel,
- ii–V pattern,
- augmented-sixth interpretation,
- drop/build/breakdown,
- orchestration thickening,
- rubato phrase,
- chorus “lift,”
- tonicization/modulation,
- production texture change.

The first layer should be reusable across contexts. The second should be plugin-like interpretation over evidence with explicit applicability/prerequisites.

---

## 8. What belongs to audio vs MIDI vs score vs stems vs embeddings

### Raw/mixed audio
Best source for:
- timbre,
- production,
- overall rhythm/groove,
- loudness/energy,
- spectral texture,
- broad instrumentation,
- section-change cues,
- embeddings,
- source separation.

### Stems
Best source for:
- drum groove,
- bass/drum relation,
- vocal melody/phrasing,
- instrument/source activity,
- arrangement entrances/exits,
- source-specific energy/timbre,
- improved downstream chord/melody/beat analysis where demonstrated.

### MIDI / note events
Best source for:
- pitch/timing inventory,
- piano-roll inspection,
- note density,
- symbolic melody candidates,
- pitch-class/harmonic evidence,
- note-level editing/correction.

### Score
Best source for:
- notation literacy/performance,
- measures/voices/staves,
- theory-aware symbolic structure,
- engraving,
- score following/alignment,
- performance-vs-score comparison.

### Embeddings
Best source for:
- similarity,
- repeated texture/groove/section candidates,
- semantic retrieval,
- library clustering,
- cross-modal matching,
- broad style/instrument/mood probes.

No representation is authoritative outside its competency.

---

## 9. Representation taxonomy

### Core views

1. **Timeline / waveform workspace** — universal temporal anchor.
2. **Notes view / piano roll** — available when note transcription is meaningful.
3. **Score** — promoted to core only when notation quality/domain support justifies it; otherwise contextual.

### Persistent lanes/overlays, not separate “apps”

- beat/bar grid,
- chord/harmony lane,
- section timeline,
- stem/source activity lanes,
- energy/loudness curve,
- melody contour,
- annotations/evidence.

### Contextual expert views

- spectrogram,
- chromagram/tonal-space view,
- tempogram,
- drum/pattern grid,
- self-similarity/embedding similarity matrix,
- stereo/spatial diagnostics.

Rule: views are for changing how the user inspects the same Work. Lanes/overlays are evidence aligned to time. Avoid creating a top-level view for every detector.

---

## 10. Evidence Graph: recommended shape

Do not introduce a graph database. Extend the existing domain model only after experiments define concrete requirements.

The minimum useful relational model needs:

### Nodes / entities
- Work
- TimeSpan / Segment
- SectionGroup
- Source/Stem
- Note/Beat/Chord/Boundary entities where needed
- Embedding reference
- Evidence item / Claim

### Relations
- `contains`
- `aligned_with`
- `derived_from`
- `similar_to`
- `repeats`
- `follows`
- `contrasts_with`
- `higher/lower_than`
- `denser/sparser_than`
- `enters_in` / `exits_in`
- `supports` / `contradicts`

### Example

```text
section: chorus_1 [42s, 63s]
  contains chord_sequence_7
  contains vocal_register_stats_4
  contains drum_activity_9
  contains bass_activity_2
  contains embedding_42_63

chorus_1 similar_to chorus_2 (0.91, embedding=CLaMP3-audio)
chorus_1 drum_density_higher_than verse_1 (+37%)
chorus_1 melody_register_higher_than verse_1 (+6.2 st)
chorus_1 bass_enters_relative_to verse_1
chorus_1 spectral_centroid_higher_than verse_1 (+18%)
```

The “Why does the chorus feel bigger?” answer can then be generated from relations rather than invented by the LLM.

Implementation recommendation: first prototype a computed in-memory/query-time graph over existing persisted evidence + candidate section objects. Migrate schema only when stable relation types emerge.

---

## 11. Trust model and LLM role

### Tier 1 — Measured / localized

Examples: beat time, onset, note pitch, loudness, stem energy, chord span from a validated detector.

UI: strongest wording; show exact span/source and engine provenance.

### Tier 2 — Deterministically derived

Examples: density increases, melody register rises, repeated section similarity above an evaluated threshold, four-on-floor pattern from trusted kick/downbeat evidence.

UI: state derivation and prerequisites; inherit upstream uncertainty.

### Tier 3 — Model-estimated semantic

Examples: genre/style, instrument tags, mood, production descriptors, captions.

UI: probability/confidence where calibrated; label as estimated; multi-label rather than categorical.

### Tier 4 — Interpretive synthesis

Examples: “the chorus feels more intense because…”.

UI: explanation must cite underlying evidence spans/relations. The LLM may connect Tier 1–3 evidence, compare regions and explain theory/context, but should not silently promote an interpretation to measurement.

A future Ask answer should return **claims + evidence references**, not only prose.

---

## 12. Foundation-model bakeoff design

### Candidates

Required initial set:
- MERT,
- MuQ,
- MusicFM,
- CLaMP3,
- LAION-CLAP.

Optional second wave:
- MuQ-MuLan,
- Qwen2.5-Omni audio encoder,
- DaSheng.

### Product tasks

1. track-level genre/style probing,
2. instrumentation probing,
3. mood/energy probing,
4. section similarity / repeated-section retrieval,
5. timbral similarity between spans,
6. semantic text → music retrieval,
7. music → text-label zero-shot retrieval,
8. cross-modal audio ↔ MIDI ↔ score retrieval where supported,
9. library-level nearest-neighbor sanity tests,
10. cultural/domain diversity failure probes.

### Metrics

- task-standard AUROC/mAP/F1/accuracy where appropriate,
- Recall@K / MRR / nDCG for retrieval,
- pairwise ranking accuracy for “same section vs different section,”
- correlation with human similarity judgments for product probes,
- latency CPU/GPU,
- peak RSS/VRAM,
- checkpoint + install size,
- embedding dimension,
- max segment length / temporal resolution,
- failure rate,
- Python/container/ARM compatibility,
- code/model/weights/data license.

### Datasets

- MTG-Jamendo for genre/instrument/mood research evaluation,
- GiantSteps/GTZAN-like task sets only where licensing and task match are acceptable,
- structure datasets used through mirdata where possible,
- rights-safe internal diversity clips for product ranking and semantic retrieval,
- cross-modal score/audio fixtures from legally usable aligned corpora.

### Stop condition

Do not productionize a foundation encoder unless it clearly beats simple/cheaper baselines on at least one high-value product task and has a viable production license/runtime path. It is acceptable to adopt different encoders for different tasks.

---

## 13. Source-separation bakeoff design

### Candidates

- HTDemucs baseline,
- one strong maintained Mel-Band RoFormer checkpoint,
- one strong BS-RoFormer checkpoint,
- best well-documented MSST checkpoint available under acceptable research terms,
- AudioShake commercial API reference on a small approved evaluation subset.

### Test genres/contexts

- solo piano,
- pop,
- house,
- reggaeton/Latin urban,
- jazz,
- optionally orchestral/film probe.

### Metrics

**Separation:** SDR/SI-SDR where ground truth stems exist, artifact/interference measures where standard.

**Product/downstream:**
- beat/downbeat F1 from mix vs drum stem,
- chord accuracy from mix vs harmonic/other stem,
- vocal melody F1/contour consistency from mix vs vocal stem,
- instrument activity precision/recall,
- section boundary/grouping lift using per-stem features,
- arrangement entrance/exit precision,
- runtime/VRAM/cost.

### Crucial decision rule

A separator can lose on SDR yet win for hello-ai if it materially improves downstream musical evidence with acceptable artifacts/runtime. Conversely, a state-of-the-art separator that does not improve analysis should not become infrastructure.

---

## 14. Dataset map

| Dataset | Task | Notes / restrictions |
|---|---|---|
| MAESTRO | piano audio/MIDI alignment, transcription/performance | strong piano domain; audio acquisition is large |
| ASAP | score/performance alignment, classical piano | useful for score/performance tasks |
| GuitarSet | chords/key/pitch/guitar | already used internally |
| POP909 | melody/chords/structure-ish symbolic pop | current LStoM validation source |
| DCML corpora | harmony/cadence/key regions symbolic | theory-focused, classical bias |
| When-in-Rome | Roman numeral harmony corpora | symbolic/theory |
| MTG-Jamendo | genre/instrument/mood tags | >55k tracks; metadata CC BY-NC-SA; research/non-commercial restrictions require care |
| MUSDB18-HQ | 4-stem separation | standard separation benchmark; license/data terms must be tracked |
| MoisesDB | >4-stem separation taxonomy | broader stem taxonomy; research conditions must be checked |
| Ballroom / Hainsworth / GTZAN beat annotations | beat | common MIREX-style benchmarks |
| GiantSteps | tempo/key/electronic | especially valuable EDM context |
| RWC / SALAMI-like structure corpora | structure | acquisition/license varies; use mirdata where supported |
| MedleyDB | stems/instrumentation/melody | valuable multi-track annotations; licensing per track |
| Slakh | synthetic multitrack/stems/MIDI | useful for instrument/stem experiments; synthetic-domain caveat |
| FMA | genre/music representation | metadata/audio licensing complexity |
| Song Describer / MuChoMusic / ManyMusic | music-text/caption/retrieval | promising for semantic evaluation; verify exact release terms |

Dataset policy must store dataset license separately from code/model license and mark “research usable” vs “commercial-training usable.”

---

## 15. Commercial vs self-hosted

### Tagging / semantic analysis

**OSS:** Essentia models, foundation probes.
- Pros: control, reproducibility, lower marginal cost.
- Cons: licensing complexity, evaluation/training burden.

**Commercial:** Cyanite.
- Pros: fast product learning across genre/subgenre/mood/instrument/energy/caption/similarity.
- Cons: cost, external dependency, opaque model changes, less localizable evidence.

Recommendation: use Cyanite as an evaluation/product benchmark and potentially temporary experiment API if budget/terms are acceptable; do not make it the only evidence source.

### Stems

**OSS:** Demucs/RoFormer/MSST.
- Pros: control and downstream integration.
- Cons: GPU/runtime/checkpoint provenance.

**Commercial:** AudioShake.
- Pros: fine-grained taxonomy and strong production benchmark.
- Cons: recurring cost/lock-in.

Recommendation: benchmark both; commercial API is especially useful to estimate the product ceiling before optimizing self-hosted models.

### Transcription

Keep Basic Pitch/Transkun baselines. Only evaluate commercial transcription if a concrete quality gap blocks the product.

---

## 16. Replace / augment matrix

| Subsystem | Current | Best candidates | Action | Why / evaluation |
|---|---|---|---|---|
| Transcription | Basic Pitch / Transkun routing | specialist AMT + optional generic AMT research | KEEP + RESEARCH | valuable but domain-specific; benchmark only where new genres require it |
| Notation | custom MIDI→MusicXML + music21/OSMD pipeline | Partitura, Piano_SVSep | AUGMENT | reduce bespoke symbolic/engraving glue; score is contextual |
| Beat | current librosa path | Beat This, BeatNet, reproducible MIREX-2025 winner candidates | REPLACE/RESEARCH | metrical scaffold is foundational; MIREX 2025 surpasses Beat This baseline |
| Harmony | lv-chordia + music21 + theory interpreter | task-specific chord systems; symbolic theory corpora | KEEP + AUGMENT | current chord path has internal evidence; improve local tonality and richer context separately |
| Melody | LStoM symbolic | stem-assisted vocal melody, AMT alternatives | KEEP experimental + AUGMENT | LStoM domain is narrow; stems may generalize mixed music |
| Rhythm | MIDI density/rest/beat phase | beat/downbeat + drum stem + established groove metrics | AUGMENT | current facts are safe but musically shallow |
| Structure | librosa CENS/novelty eval baseline | MusicFM/embedding self-similarity, modern MIREX systems | RESEARCH / likely REPLACE | repetition/grouping may matter more than semantic section labels |
| Genre/style | none/limited | Essentia Discogs models, MuQ/MuLan, CLaMP3, commercial Cyanite | ADD via research | context should rank analysis, not hard-route UI |
| Instrumentation | none/limited | Essentia, foundation probes, stem activity | ADD via research | essential for arrangement/general genres |
| Similarity | limited Compare | CLaMP3/MERT/MuQ/MusicFM embeddings | ADD first-class | major new product pillar |
| Ask | evidence verbalizer | evidence-conditioned LLM + optional audio-language comparison | AUGMENT | allow relational synthesis while preserving provenance |
| Inspector | capability sections | human-centered taxonomy + contextual ranking | REPLACE IA, KEEP mechanics | backend taxonomy should not dictate product IA |
| Annotations | time-aligned findings | evidence lanes + relations | AUGMENT | support cross-source/cross-section explanations |

---

## 17. Top 10 experiments

### 1. Segment embedding bakeoff
**Hypothesis:** a learned music representation provides useful section similarity and semantic retrieval beyond handcrafted features.
**Implementation:** MERT, MuQ, MusicFM, CLaMP3, CLAP on fixed 5–15s/15–30s windows.
**Data:** MTG-Jamendo research tasks + rights-safe section/similarity set.
**Metrics:** task probes, Recall@K, human pair ranking, latency/RAM.
**Effort:** 4–7 days.
**Value:** very high.
**Stop:** no candidate beats simple chroma/MFCC baselines meaningfully on product retrieval or viable license path absent.

### 2. Structure via embeddings vs CENS baseline
**Hypothesis:** learned self-similarity improves repeated-section grouping and useful boundaries.
**Implementation:** similarity matrices + novelty/grouping using top embedding candidates; compare MusicFM/MERT/CLaMP3.
**Data:** public structure annotations + rights-safe songs.
**Metrics:** boundary F1, pairwise section grouping, product navigation preference.
**Effort:** 3–5 days after #1.
**Value:** very high.
**Stop:** no grouping/boundary lift over CENS or runtime excessive.

### 3. Drum-stem beat/downbeat lift
**Hypothesis:** separation improves metrical evidence on rhythm-first music.
**Implementation:** Demucs/RoFormer candidates then beat trackers on mix vs drum stem.
**Data:** pop/house/reggaeton/jazz + stem benchmarks.
**Metrics:** beat/downbeat F1, tempo octave errors, latency.
**Effort:** 4–6 days.
**Value:** high.
**Stop:** < material improvement or separation cost dominates.

### 4. Modern beat/downbeat bakeoff
**Hypothesis:** current librosa path is materially below modern systems across styles.
**Implementation:** current baseline, Beat This, BeatNet and reproducible 2025 MIREX winner candidate(s).
**Data:** MIREX-compatible datasets + diversity probe.
**Metrics:** F1/CMLt/AMLt/downbeat/meter accuracy, runtime.
**Effort:** 3–5 days.
**Value:** high foundational.
**Stop:** current engine is within practical margin and much cheaper.

### 5. Instrument/source activity lanes
**Hypothesis:** stem energy + instrument tags provide more intuitive arrangement insight than note-density microfeatures.
**Implementation:** derive per-stem/source activation timeline and entrances/exits.
**Data:** multitrack/stem datasets + rights-safe songs.
**Metrics:** entrance/exit accuracy, human usefulness rating.
**Effort:** 3–5 days after separation.
**Value:** high.
**Stop:** artifacts make activity unreliable.

### 6. Semantic library search prototype
**Hypothesis:** text/music embeddings unlock a differentiating “find music like this / find by description” workflow.
**Implementation:** CLaMP3/MuQ-MuLan/CLAP embeddings + local vector index in research only.
**Data:** rights-safe personal-style corpus + MTG research set.
**Metrics:** Recall@K, qualitative query set, latency.
**Effort:** 3–4 days.
**Value:** very high strategic.
**Stop:** retrieval is generic/poor or licensing blocks every competitive model.

### 7. Evidence-conditioned cross-section explanation
**Hypothesis:** relational evidence can produce trustworthy YouTube-style breakdowns.
**Implementation:** fixed two-section comparator over loudness, source activity, melody register, harmony, groove, embeddings; LLM only verbalizes supplied relations.
**Data:** 10–20 diverse rights-safe songs.
**Metrics:** factual consistency, evidence citation coverage, expert preference.
**Effort:** 3–5 days.
**Value:** very high product differentiation.
**Stop:** explanations remain generic despite useful evidence.

### 8. Style/context classifier bakeoff
**Hypothesis:** multi-label context can improve prioritization without hard routing.
**Implementation:** Essentia Discogs, foundation probes, optional Cyanite reference.
**Data:** MTG-Jamendo + diversity clips.
**Metrics:** mAP/AUROC, calibration, confusion by culture/domain.
**Effort:** 3–5 days.
**Value:** medium-high.
**Stop:** insufficient calibration/generalization for UI context.

### 9. Vocal-stem melody lift
**Hypothesis:** stem-assisted melody extraction beats symbolic transcription-first melody on produced vocal music.
**Implementation:** melody/pitch system on mix vs separated vocals; compare to note-transcription-derived melody where applicable.
**Data:** MedleyDB/melody datasets + pop/R&B/Latin probes.
**Metrics:** melody F1/voicing/contour, downstream explanation usefulness.
**Effort:** 4–6 days.
**Value:** high for non-piano music.
**Stop:** separation/pitch errors compound with no net gain.

### 10. Audio-language model as Tier-3/Tier-4 helper
**Hypothesis:** a generalist audio-language model adds useful production/style descriptions if constrained to selected regions and evidence.
**Implementation:** Qwen2.5-Omni or API comparator on localized clips; prompts request claims + uncertainty + evidence pointers.
**Data:** rights-safe clips with human annotations.
**Metrics:** factuality, localization, calibration, incremental value beyond tags.
**Effort:** 2–4 days.
**Value:** medium, potentially high.
**Stop:** answers are generic, unlocalized or contradict measured evidence too often.

---

## 18. What not to build now

1. **Do not add more bespoke melody/rhythm micro-detectors** because a threshold can be coded. The recent rollback history was correct.
2. **Do not build a universal score-first experience.** Score is excellent for notation-centric domains and poor as the representation of production, timbre, stems or groove.
3. **Do not make generic multi-instrument transcription the universal middle layer.** It is expensive, error-prone and unnecessary for many questions.
4. **Do not build one hard genre router.** Use multi-label context and capability relevance.
5. **Do not hand-build dozens of tagging classifiers** before testing foundation representations and Essentia/commercial baselines.
6. **Do not build a graph database.** First prove evidence relations in existing storage/query structures.
7. **Do not expose semantic verse/chorus labels** simply because a structure model emits them; grouping/boundary confidence should be separable.
8. **Do not call simple beat-phase histograms “syncopation.”** Use established metrics or factual wording.
9. **Do not optimize source separation solely for SDR.** Optimize for downstream analysis value.
10. **Do not make an audio-language model the sole truth source** for exact temporal music facts.
11. **Defer deep cadence/key-region/voice-leading work** unless a target user workflow proves it matters; these are high-risk classical rabbit holes.
12. **Do not add textbook visualizations by default.** Chromagrams/tempograms/self-similarity matrices belong in contextual/expert views unless user testing shows broad value.

---

## 19. Three product futures

### A. Interactive Music Explainer — recommended primary direction

**Target:** musicians, learners, producers, curious listeners, educators.

**Core value:** upload any track and get an interactive, synchronized breakdown of what happens, where, and why, with audible/visual evidence.

**Technology:** beat/bar, stems, embeddings, chords/melody where appropriate, structure, source activity, relational evidence, evidence-conditioned LLM.

**Differentiation:** combines the explanatory clarity of human breakdowns with interactive localized evidence and multiple representations.

**Risk:** explanations can become generic unless relational evidence is strong; must manage genre/cultural context carefully.

### B. Music Analysis IDE

**Target:** MIR researchers, theorists, advanced musicians, educators.

**Core value:** inspect and compare aligned representations/algorithms/evidence with provenance.

**Technology:** strongest version of current workspace, many expert views, engine switching, evaluation metadata.

**Differentiation:** trustworthy/open/provenance-first.

**Risk:** smaller audience, complexity, easy to become “Sonic Visualiser + chat.”

### C. Personal Music Intelligence Workspace

**Target:** creators, A&R/music supervisors, producers with libraries.

**Core value:** organize, search, compare and understand a personal catalog using semantic/similarity/style/source evidence.

**Technology:** embeddings/vector search, tagging, stems, similarity, work-level analysis, Compare.

**Differentiation:** user-owned library + explainable similarity rather than opaque recommendations.

**Risk:** value rises with library size; rights/privacy/indexing infrastructure becomes central.

### Recommendation

Make **Interactive Music Explainer** the product north star, while building embeddings/indexing so it naturally expands into **Personal Music Intelligence Workspace**. Preserve the expert “IDE” power under contextual views rather than making it the default product identity.

Current hello-ai maps well: synchronized Work/transport/selection, representations, Inspector, Ask and provenance are strong primitives. What must change is the evidence breadth and the information architecture.

---

## 20. Product Architecture V3

```text
                            ORIGINAL AUDIO
                                  │
          ┌───────────────────────┼────────────────────────┐
          │                       │                        │
          ▼                       ▼                        ▼
   signal / MIR evidence    source separation       foundation encoders
   beat/downbeat/onsets     drums/bass/vocals/...   segment/work embeddings
   chords/pitch/energy              │                        │
          │                         │                        │
          └──────────────┬──────────┴──────────────┬─────────┘
                         │                         │
                         ▼                         ▼
                  UNIVERSAL TIME-ALIGNED EVIDENCE
                         │
             ┌───────────┼──────────────┐
             │           │              │
             ▼           ▼              ▼
        SYMBOLIC      STRUCTURE      SEMANTIC CONTEXT
        notes/MIDI    boundaries     style/instruments
        score/voices  repetition     mood/captions
             │           │              │
             └───────────┼──────────────┘
                         ▼
                 RELATIONAL EVIDENCE LAYER
          spans • sections • sources • similarities • changes
                         │
                ┌────────┴────────┐
                ▼                 ▼
          INTERACTIVE UI      ASK / EXPLAINER
          lanes/views         evidence-conditioned LLM
                └────────┬────────┘
                         ▼
                 HUMAN-CENTERED BREAKDOWN
```

Key design invariant: every user-visible claim declares **where**, **source representation**, **engine/model**, **trust tier**, **confidence/evaluation domain** where available, and **relations/evidence references** if interpretive.

---

## 21. 90-day technical roadmap

### Days 0–30 — establish evidence substrates

- Execute foundation representation bakeoff (#332) with segment-level outputs.
- Execute beat/downbeat/meter bakeoff (#335), adding MIREX-2025 reproducibility candidate review.
- Execute source-separation bakeoff (#334) with downstream metrics.
- Execute style/instrument semantic bakeoff (#333).
- Do not change product exposure during these tracks.
- Add a research-only common experiment manifest with exact model/checkpoint/license/runtime/dataset metadata.

**Decision gate:** choose one or more embeddings for next prototypes, one beat/bar path, and whether stems show downstream lift.

### Days 31–60 — prototype relational understanding

- Build research-only segment/section evidence objects.
- Prototype embedding-based repeated-section grouping and semantic retrieval.
- Prototype stem/source activity lanes.
- Prototype cross-section comparator (“what changed between A and B?”).
- Define minimal Evidence Graph relation vocabulary from real outputs.
- Run localized audio-language model comparison as Tier 3/4 helper.

**Decision gate:** if relational explanations are materially better than flat Inspector facts, finalize domain contract proposal for issue #336.

### Days 61–90 — productize only winners

- Extend persistence schema minimally for stable section/source/embedding/relation requirements.
- Introduce new user-facing taxonomy (Overview, Composition, Groove, Arrangement, Sound, Structure, Performance).
- Add contextual lanes: beat/bar + structure first; stem lanes if validated.
- Make Ask return evidence-cited relational explanations.
- Add first semantic/similarity feature: “find similar section” or text-search over the user’s Work/library depending on bakeoff results.
- Keep Score/Piano Roll as contextual strengths rather than universal center.

**Success criterion:** at least one diverse non-piano produced track yields a genuinely useful breakdown whose core value does not depend on MIDI transcription quality.

---

## 22. Open questions requiring owner decisions

1. **Primary user:** is the near-term target a musician/learner wanting explanation, a producer wanting arrangement/production insight, or a catalog/library user? The architecture can support all three, but product prioritization cannot.
2. **Commercial API budget:** are small paid bakeoffs (e.g. Cyanite/AudioShake) acceptable to establish a quality ceiling and accelerate learning?
3. **GPU posture:** should research assume occasional rented GPU/cloud execution, or must candidates fit the current Oracle free-tier CPU environment? This radically changes source separation/foundation-model feasibility.
4. **Commercialization horizon:** how soon must every selected model/dataset have production-commercial terms? Research can move faster if non-commercial weights are allowed strictly for bakeoffs.
5. **Library/search scope:** should cross-work similarity become a near-term pillar or remain secondary to single-song explanation?
6. **Educational depth:** should theory explanations assume music literacy, or progressively disclose beginner → expert layers?
7. **Human evaluation:** can the project recruit a small panel across piano/classical, jazz, electronic, Latin/urban and production backgrounds? MIR benchmark scores alone will not validate explanatory usefulness.

---

## 23. Important references checked for this review

Primary/official sources should be re-verified at experiment time because model/checkpoint/license status can change.

- hello-ai current docs: `docs/MASTER_SPEC.md`, `docs/CURRENT_STATE.md`, `docs/RESEARCH_LANDSCAPE.md`, `docs/ANALYSIS_V3_IMPLEMENTATION_PLAN.md`, `backend/config/capabilities.json`, issue #327, PR #338.
- MIREX 2025 main/results and Audio Beat Tracking / Audio Chord Estimation task pages: https://music-ir.org/mirex/wiki/2025%3AMain_Page
- MARBLE: https://github.com/a43992899/MARBLE
- CLaMP3: https://github.com/sanderwood/clamp3
- MusicFM: https://github.com/minzwon/musicfm
- MERT: https://github.com/yizhilll/MERT
- MuQ: https://github.com/tencent-ailab/MuQ
- Qwen2.5-Omni: https://github.com/QwenLM/Qwen2.5-Omni
- Spotify LLark: https://github.com/spotify-research/llark and Spotify Research publication page
- Beat This: https://github.com/CPJKU/beat_this
- Music Source Separation Training: https://github.com/ZFTurbo/Music-Source-Separation-Training
- mir_eval: https://github.com/mir-evaluation/mir_eval
- mirdata: https://github.com/mir-dataset-loaders/mirdata
- MTG-Jamendo: https://github.com/MTG/mtg-jamendo-dataset
- AudioShake developer docs: https://developer.audioshake.ai/separate-stems
- Cyanite API docs: https://api-docs.cyanite.ai/
- Moises features: https://moises.ai/features/
- Hooktheory TheoryTab: https://www.hooktheory.com/theorytab
- Sonic Visualiser: https://sonicvisualiser.org/features.html

---

## Bottom line

The central architectural correction is not “swap Basic Pitch for a newer model” or “add genre detection.” It is to stop treating a symbolic transcription as the universal intermediate representation.

The 2026 design should be:

**audio + stems + temporal MIR + symbolic evidence + learned representations → time-aligned relational evidence → context-aware interactive explanation.**

That architecture keeps the strongest work already built — synchronized representations, provenance, capability gating, persistent evidence and Ask — while making the product capable of understanding music whose most important information is groove, arrangement, timbre, production, repetition or performance rather than a clean score.