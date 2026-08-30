# MIR / Music AI Research Landscape and Adoption Matrix

> **Purpose:** Practical research reference for listencloser. This document is not a shopping list. It identifies mature OSS, current research directions, evaluation resources, commercial reference points, and adoption recommendations.
>
> **Rule:** Before building a nontrivial MIR capability, implementation agents must check this document, current web/repo status, licensing, and `backend/config/capabilities.json`.

---

## 1. Field map

Modern music understanding spans several paradigms that should coexist rather than compete for a single “winner.”

### 1.1 Signal-processing / classical MIR

Strengths:

- interpretable,
- localizable in time/frequency,
- inexpensive,
- established metrics,
- strong for beat/chroma/onset/structure primitives.

Examples:

- librosa,
- Essentia,
- Sonic Annotator / Vamp ecosystem,
- classic recurrence/novelty structure methods.

### 1.2 Symbolic / computational musicology

Strengths:

- precise pitch/rhythm/harmony relationships,
- theory-aware reasoning,
- score/notation integration,
- corpus analysis.

Examples:

- music21,
- partitura,
- symusic,
- MusPy,
- pretty_midi / miditoolkit.

### 1.3 Task-specific neural MIR

Strengths:

- best quality for many hard perception tasks,
- localizable task outputs,
- often straightforward to benchmark.

Examples:

- Basic Pitch / Transkun transcription,
- lv-chordia chord recognition,
- LStoM melody extraction,
- BeatNet beat/downbeat/meter,
- Piano_SVSep voice/staff assignment,
- RoFormer-family separation.

### 1.4 Music foundation representations

Strengths:

- broad transfer,
- similarity/retrieval,
- tagging,
- useful learned representations without one handcrafted feature per task.

Examples:

- MERT,
- MuQ,
- MusicFM,
- CLaMP3,
- DaSheng,
- CLAP-family models.

### 1.5 Multimodal/audio-language models

Strengths:

- natural-language interfaces,
- semantic captioning,
- open-ended question answering,
- cross-modal reasoning.

Risks:

- hallucination,
- weak localization/calibration,
- difficult evaluation,
- large runtime.

Examples:

- LLark research architecture,
- Qwen audio/omni encoders,
- emerging music-specific instruction models.

### 1.6 Human / corpus / relative-theory systems

Not all high-quality understanding is automatic MIR. Hooktheory is a strong product reference because it structures expert/crowd-curated harmony and melody into relative, synchronized, educational views. Its value demonstrates what the product should communicate even when our evidence is automatically inferred.

---

## 2. Research venues and communities to follow

### ISMIR

Primary dedicated MIR research conference. The 2025 program explicitly framed self-supervised learning as foundational for MIR. ISMIR 2026 tutorials include:

- **LLMs x Music**,
- **Introduction to MIR: Three Perspectives**,
- **Evaluating Music Foundation Models**,
- deployment of Music AI models into DAWs using HARP.

This strongly supports a hybrid direction: classical MIR + multimodal/foundation models + human-facing applications.

References:

- https://ismir2025program.ismir.net/tutorials.html
- https://ismir2026.ismir.net/tutorials

### MIREX

Shared task evaluation culture. Useful to identify accepted metrics/datasets and avoid inventing private evaluation conventions. 2025 includes Audio Chord Estimation and other traditional MIR tasks.

- https://music-ir.org/mirex/wiki/2025%3AMain_Page

### Other important venues

- ICASSP — audio/signal processing, source separation, MIR, multimodal audio.
- ICML / ICLR / NeurIPS — representation learning, foundation models, generative/music ML.
- CHI / DIS — human-centered music/AI interfaces and creative tools.
- DAFx — digital audio effects / processing.
- Audio Mostly / NIME — music interaction/instruments.
- Music Encoding Conference — notation/symbolic encoding.

---

## 3. Labs / research groups worth tracking

### MTG — Universitat Pompeu Fabra

Strong in MIR, sound/music computing, Essentia, datasets, trustworthy music AI, cultural heritage, creation/education.

- https://www.upf.edu/web/mtg/about

### C4DM — Queen Mary University of London

Large multidisciplinary group spanning MIR, semantic audio, machine listening, DSP, perception, education, interaction.

- https://c4dm.eecs.qmul.ac.uk/about/

### International Audio Laboratories Erlangen

Strong in semantic audio analysis, synchronization, structure, decomposition, performance, retrieval; home of the FMP ecosystem.

- https://audiolabs-erlangen.de/

### NYU Music and Audio Research Laboratory (MARL)

Music/audio AI, MIR, cognition, machine listening, sound understanding.

- https://engineering.nyu.edu/research/labs-and-groups

### Stanford CCRMA

Signal processing, computer music, music cognition, computational theory/analysis, interactive systems, HCI.

- https://music.stanford.edu/venues-facilities/facilities/center-computer-research-music-and-acoustics-ccrma
- https://music.stanford.edu/about/what-we-do/music-science-and-technology

### Spotify Research — Audio & Visual Intelligence

Commercial-scale music understanding, multimodal retrieval, recommendation, language/audio research. LLark is an important research reference for music instruction-following even though no trained model is released with the code.

- https://research.atspotify.com/audio-visual-intelligence
- https://research.atspotify.com/publications/LLARK-a-multimodal-instruction-following-language-model-for-music

### Adobe Research — Audio

Audio analysis, processing, generation, human-centered creative interfaces, multimodal audio reasoning.

- https://research.adobe.com/research/audio/

---

## 4. Foundation-model adoption matrix

### 4.1 MERT

**Type:** music-specific SSL audio representation.

**Evidence:** paper reports strong transfer across 14 music-understanding tasks; MARBLE provides evaluation support/reference.

**Code license:** Apache-2.0 according to official repo.

**Why relevant:** strong general-purpose audio embedding baseline; likely useful for similarity and downstream probes.

**Recommendation:** **benchmark**. Do not route production facts directly from embeddings without a downstream validated head.

Official repo:
- https://github.com/yizhilll/MERT

### 4.2 MuQ

**Type:** modern self-supervised music representation using Mel-RVQ targets.

**Code license:** MIT.

**Important weight restriction:** official open model weights are CC-BY-NC 4.0. This is acceptable for research/prototyping but a future commercial product would need a compatible model/training route or permission.

**Why relevant:** modern music-specific SSL; MuQ-MuLan adds audio-text alignment.

**Recommendation:** **high-priority research bakeoff**, but keep licensing in the decision table.

- https://github.com/tencent-ailab/MuQ

### 4.3 MuQ-MuLan

**Type:** joint music-text embedding.

**Use cases:** zero-shot semantic tagging, text-to-music retrieval, section/work similarity.

**License caveat:** released weights follow the MuQ CC-BY-NC weight terms.

**Recommendation:** **research/reference**, especially for UX prototypes around semantic search and style/instrument tags.

### 4.4 MusicFM

**Type:** foundation model for music informatics.

**Why relevant:** music-specific masked modeling / representation learning; MARBLE reference support.

**Recommendation:** benchmark against MERT/MuQ rather than integrating by reputation.

- https://github.com/minzwon/musicfm

### 4.5 CLaMP3

**Type:** shared embedding across text, audio, MIDI, sheet music, and images; multilingual.

**Code license:** MIT according to official repo.

**Why unusually relevant to listencloser:** our product already has synchronized audio, MIDI and MusicXML representations. CLaMP3’s cross-modal space may enable:

- audio ↔ score similarity,
- text ↔ passage search,
- MIDI ↔ audio retrieval,
- multimodal clustering,
- representation-consistency checks.

**Runtime caveat:** official setup uses a substantial PyTorch environment; practical deployment must be measured.

**Recommendation:** **top-priority R&D candidate**.

- https://github.com/sanderwood/clamp3

### 4.6 LAION CLAP

**Type:** general audio-text contrastive model.

**Code license:** Apache-style according to project metadata; verify exact weights/data terms before deployment.

**Use:** semantic baseline against music-specific MuLan/CLaMP3.

**Recommendation:** benchmark as a **generic audio-text baseline**, not necessarily production default.

- https://github.com/LAION-AI/CLAP

### 4.7 LLark

**Type:** music-focused multimodal instruction-following research system.

**Code license:** Apache-2.0.

**Critical limitation:** Spotify repo does **not** release trained model weights.

**Recommendation:** architecture/evaluation reference for Ask, not a drop-in production dependency.

- https://github.com/spotify-research/llark

---

## 5. Foundation benchmark framework: MARBLE

MARBLE is a key reference because it attempts universal evaluation of pretrained music encoders and currently lists/supports encoders including MERT, MusicFM, MuQ, MuQ-MuLan, CLaMP3, DaSheng, and audio encoders from Qwen models.

Use it to answer:

- which embeddings are genuinely strong across tasks,
- which tasks each representation supports,
- whether a larger modern model is worth its runtime/deployment cost.

Recommendation:

1. Reuse MARBLE evaluation/task definitions where practical.
2. Add a listencloser operational layer: CPU latency, memory, model download size, ARM compatibility, license, and selected-passage UX usefulness.
3. Do not reproduce the entire framework if a small upstream invocation suffices.

- https://github.com/a43992899/MARBLE

---

## 6. Audio analysis / tagging / semantic OSS

### Essentia

**Strength:** unusually broad industrial MIR toolkit with handcrafted DSP plus pretrained models.

Available model ecosystem includes Discogs-EffNet embeddings/style classifiers; one released classifier targets 400 Discogs styles.

Potential uses:

- genre/style,
- mood/theme,
- instrument classifiers,
- similarity embeddings,
- BPM/key/chroma/rhythm reference implementation,
- broad baseline feature extraction.

**License:** Essentia’s licensing must be treated carefully (AGPL / commercial licensing context). Do not silently embed it into a commercial backend later without review.

**Recommendation:** **major evaluation/reference candidate**. It can tell us which bespoke analysis code should be deleted or avoided.

- https://essentia.upf.edu/models.html

### MTG-Jamendo

Over 55k full tracks with genre, instrument, and mood/theme annotations; repository supplies standard splits and baseline scripts.

Use cases:

- style/instrument/mood classifier evaluation,
- downstream probes for foundation embeddings,
- evaluation of semantic tagging.

**Recommendation:** core dataset for Analysis V3 semantic/context bakeoff.

- https://github.com/MTG/mtg-jamendo-dataset

---

## 7. Beat / downbeat / meter

### Current listencloser path

Current code uses an audio beat path that must be verified from current main. Existing temporal rhythm features depend on its reliability.

### BeatNet

**Task:** joint beat, downbeat, tempo, and meter tracking.

**Features:** offline and real-time modes, pretrained models included, training pipeline available.

**Why relevant:** one engine can provide the metrical scaffolding needed by groove, structure, rhythmic pattern, and notation analysis.

**License:** official repo reports CC-BY-4.0; validate software/model implications before production.

**Recommendation:** **benchmark against current beat engine** across styles.

- https://github.com/mjhydri/BeatNet

### Benchmark families

Depending on task and legal availability:

- Ballroom,
- GiantSteps,
- GTZAN beat annotations,
- RWC-related annotations,
- other MIREX-style beat/downbeat datasets.

Use beat, downbeat, tempo and meter metrics separately. One “BPM correct” number is not enough.

---

## 8. Harmony / tonality

### lv-chordia

Current production audio chord foundation after internal GuitarSet evaluation. Do not restart the engine search without evidence of a concrete deficiency.

Use current internal benchmark artifacts as source of truth for its production domain.

### music21

**Role:** computational musicology, symbolic key/theory, Roman numeral interpretation, score operations.

**License:** BSD-3-Clause.

**Recommendation:** retain as theory/symbolic layer; avoid using it as general audio chord recognizer.

- https://github.com/cuthbertLab/music21

### BACHI

Previously identified research candidate for symbolic chord recognition, especially piano/classical/pop symbolic domains. Maintain as research reference if its specialization becomes relevant again; do not displace working lv-chordia without a matched-domain evaluation.

### Evaluation datasets

- GuitarSet,
- POP909-CL,
- DCML corpora,
- When-in-Rome,
- domain-specific chord corpora.

Remember: symbolic oracle theory metrics are not end-to-end audio metrics.

---

## 9. Melody / symbolic voices / notation

### LStoM

Current production-default symbolic melody extraction after internal POP909 evaluation. Official ByteDance repository is archived as of 2026, but code is MIT and the project has a clear ISMIR 2022 research basis.

Internal validation, model artifact metadata, and production compatibility are more important than repository activity now that the model is owned in our pipeline.

- https://github.com/bytedance/midi_melody_extraction

### Piano_SVSep

**Task:** voice and staff prediction for symbolic piano engraving.

**Not:** audio separation or semantic melody detection.

**Input:** quantized symbolic score.

**Output:** voice/staff assignments suitable for engraving.

**License:** MIT.

**Recommendation:** high-value notation R&D once environment/dependency fit is resolved.

- https://github.com/CPJKU/piano_svsep

### Partitura

**Role:** MusicXML/MIDI/MEI symbolic score handling; active releases through 2026.

**License:** Apache-2.0.

**Recommendation:** preferred symbolic/notation utility when its data model reduces custom score manipulation.

- https://github.com/CPJKU/partitura

### Symusic

**Role:** fast modern MIDI/ABC parsing/transformations/rendering; MIT; wheels across broad Python/platform matrix.

**Recommendation:** evaluate for performance-sensitive symbolic processing and simplification of pretty_midi/miditoolkit glue. Do not migrate solely for speed without a bottleneck.

- https://github.com/Yikai-Liao/symusic

### MusPy

**Role:** symbolic datasets, representations, generation evaluation.

**License:** MIT.

**Recommendation:** useful primarily when generation/corpus infrastructure becomes active; not a replacement for music21/partitura today.

- https://github.com/salu133445/muspy

### note-seq

Apache-2.0 symbolic utilities, but archived by Magenta in May 2026.

**Recommendation:** do not adopt as a new central dependency. Existing ideas/representations remain useful references.

---

## 10. Source separation

### BS-RoFormer / Mel-Band RoFormer family

Modern transformer-based source separation family; practical open implementations exist.

**Code license:** MIT for the widely used lucidrains implementation.

**Important caveat:** model weight licenses and training data terms must be checked independently from code.

**Recommendation:** **high-priority bakeoff** for drums/bass/vocals/other because source-specific analysis unlocks generic style-aware understanding.

- https://github.com/lucidrains/BS-RoFormer

### MSST ecosystem

Open training/inference framework supports multiple architectures including MDX, Demucs, BS-RoFormer, Mel-Band RoFormer, BandIt, SCNet.

**Recommendation:** consider as evaluation/inference harness rather than integrating many model families independently.

- https://github.com/ZFTurbo/Music-Source-Separation-Training (verify current upstream)

### Commercial reference: AudioShake

AudioShake exposes specialized production stems such as vocals, lead/backing vocals, drums, bass, guitar, piano, keys, strings.

Use as a **quality/product benchmark**, not necessarily a dependency.

- https://developer.audioshake.ai/separate-stems

---

## 11. Structure / form

### Current listencloser baseline

Evaluation-only librosa CENS/recurrence/novelty/peak-pick pipeline.

This is appropriate as a reproducible baseline, not enough evidence for product exposure.

### All-In-One

Historically integrated but runtime/dependency issues (`madmom` etc.) have prevented clean production use. Do not spend unlimited time resurrecting it.

### MSAF

Historically relevant structure-analysis framework but dependency age/runtime fit must be treated as a practical blocker on modern Python.

### Evaluation

Use established boundary metrics (`mir_eval.segment`-style conventions) and labeled datasets such as SALAMI/Harmonix where lawful audio + annotations can be obtained.

Split capability maturity:

1. boundary detection,
2. repeated-section grouping,
3. semantic labels.

Do not require semantic labels before shipping validated boundaries.

---

## 12. Product/commercial benchmarks

### Hooktheory TheoryTab

What to learn:

- relative notation can be better for understanding than conventional score,
- Roman numerals support cross-key pattern recognition,
- chord/melody synchronized playback,
- section-aware analysis,
- theory concepts tied to actual songs,
- corpus-relative metrics can make “complexity/novelty” interpretable.

Notable metrics include chord complexity, melodic complexity, chord-melody tension, progression novelty, and bass-motion characteristics. These are product inspirations, not direct formulas to copy blindly.

- https://www.hooktheory.com/theorytab/
- https://www.hooktheory.com/song-metrics/about

### Sonic Visualiser

What to learn:

- aligned waveform/spectrogram/MIDI,
- annotation layers,
- feature-extraction plugin model,
- multiple time resolutions,
- synchronized playback.

listencloser should be more opinionated, persistent, accessible, and explanatory.

- https://sonicvisualiser.org/features.html

### Moises

What to learn:

- source separation is a user-facing capability, not just backend preprocessing,
- synced metronome, key/BPM, pitch/speed manipulation fit musician workflows,
- stem playback is a representation/control surface.

- https://moises.ai/products/moises-app/

### Cyanite

What to learn:

- commercial analysis uses multi-label genre/mood taxonomies,
- segment-level outputs matter,
- product APIs separate versioned model outputs,
- semantic/style analysis is useful even when not theory-centric.

- https://api-docs.cyanite.ai/docs/audio-analysis-v6-classifier/

### Spotify Research

What to learn:

- audio understanding increasingly connects to description, similarity, search, recommendation, and natural language,
- multimodal instruction-following is a credible long-term interface pattern,
- evaluation must be a first-class research area.

- https://research.atspotify.com/audio-visual-intelligence

---

## 13. Courses / textbooks / domain learning path

### Computational MIR foundation

1. **Meinard Müller — Fundamentals of Music Processing (2nd ed.)**
   - representation,
   - Fourier analysis,
   - synchronization,
   - structure,
   - chords,
   - beat/tempo,
   - retrieval,
   - decomposition.

2. **Audio Signal Processing for Music Applications** — Xavier Serra + Julius O. Smith / Stanford.
   - practical music DSP,
   - spectral models,
   - transformations,
   - open Python material.

3. **Stanford CCRMA curriculum**
   - MUSIC 258A Computational Music Theory & Analysis,
   - MUSIC 320A/B audio signal processing,
   - MUSIC 251 Psychophysics and Music Cognition,
   - MUSIC 220A/B/C computer-generated/computational music.

### Western tonal theory / analysis

1. MIT OCW Harmony & Counterpoint I.
2. MIT OCW Harmony & Counterpoint II — includes chromatic harmony, Neapolitan and augmented-sixth chords, chromatic modulation.
3. MIT OCW Musical Analysis — rhythm/form, harmony, line, motivic relationships at local and large scales.
4. Aldwell & Schachter, *Harmony and Voice Leading*.
5. Open Music Theory as an accessible online reference.

### Important limitation

These theory resources heavily represent Western common-practice tonal frameworks. They are not sufficient for culturally broad analysis. Before implementing genre/culture-specific explanatory modules, add authoritative style-specific musicology / ethnomusicology / production literature to the research issue and identify whose theory vocabulary is being used.

---

## 14. Immediate recommendation matrix

| Area | Current | Next action |
|---|---|---|
| Transcription | Basic Pitch + Transkun routing | keep; continue notation/transcription eval |
| Chords | lv-chordia | keep; broaden domain eval, no engine churn |
| Key/theory | music21 + gated theory | keep; evaluate richer claims separately |
| Melody | LStoM | keep; domain validation and human-facing interpretation |
| Rhythm | current beats + deterministic measurements | benchmark beat/downbeat layer; avoid heuristic syncopation |
| Structure | librosa baseline eval-only | obtain lawful benchmark; no exposure yet |
| Spectrogram | client-side synchronized representation | keep |
| Style/instrument | missing/weak | benchmark Essentia + foundation probes |
| Foundation embeddings | missing | top-priority bakeoff: MuQ/MERT/MusicFM/CLaMP3 |
| Source separation | missing/legacy | top-priority RoFormer-family bakeoff |
| Audio-text semantics | missing | benchmark MuLan/CLaMP3/CLAP; keep low-trust until evaluated |
| Similarity/search | missing | build after embedding bakeoff |
| Ask | grounded evidence architecture | evolve toward Evidence Graph + education |
| Generation | future | defer until understanding layer is strong |

---

## 15. Research issue template

Every research/bakeoff issue should include:

```markdown
# Capability
What user question does this enable?

# Task definition
Exactly what is predicted / represented?

# Candidates
OSS / model / baseline.

# Licensing
Code + weights + dataset separately.

# Evaluation data
Dataset, split, domain, lawful access.

# Metrics
Established metrics where possible.

# Operational metrics
CPU/GPU, latency, RAM, model size, install size, ARM/container fit.

# Baseline
Current production or simple reference.

# Product gate
What result is good enough to expose?

# Output contract
Canonical evidence type + provenance.

# Decision
Adopt / research / reject / revisit.
```

This prevents “interesting repo found → production dependency” decisions.
