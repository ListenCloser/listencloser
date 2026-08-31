# MIR / Music AI research reference

> **Status:** discovery reference, not production or roadmap authority.
>
> Use this page to discover relevant MIR fields, OSS projects, datasets, research communities, and product references. Before adopting anything, verify the current upstream project, code/weight/data licenses, runtime fit, and the repository's current evidence.
>
> **Current decisions live elsewhere:** `../EVALUATION_DECISIONS.md`, `../EVALUATION_METHODOLOGY.md`, `backend/config/capabilities.json`, focused GitHub issues, and production code/config. A candidate appearing here does not mean it should be evaluated or adopted next.

## Why this exists

Music understanding spans several technical traditions. Listen Closer should reuse mature research and OSS instead of reinventing generic MIR, but it should also avoid turning a technology catalog into a permanent implementation plan.

Use this document for **discovery**. Use focused evaluation for **decisions**.

## Field map

| Area | Typical strengths | Representative references |
| --- | --- | --- |
| Signal processing / classical MIR | interpretable, localizable, inexpensive primitives | librosa, Essentia, Vamp/Sonic Annotator |
| Symbolic / computational musicology | precise pitch/rhythm/theory/score relationships | music21, Partitura, Symusic, pretty_midi, MusPy |
| Task-specific neural MIR | strong bounded performance on a named perception task | Basic Pitch, Transkun, Beat This, BeatNet, lv-chordia, LStoM, Piano_SVSep |
| Music foundation representations | transfer, retrieval, similarity, tagging | MERT, MuQ, MusicFM, CLaMP3, CLAP-family models |
| Source separation | source-aware analysis and stem interaction | BS-RoFormer / Mel-Band RoFormer families, MSST ecosystem |
| Audio-language / multimodal | semantic description, open-ended language interaction | LLark research architecture, Qwen audio/omni families, emerging music-specific models |
| Human/corpus systems | expert or crowd-grounded analytical communication | Hooktheory, musicological corpora, educational references |

These approaches are complementary. A low-level descriptor, a symbolic relation, an embedding, and a language-model explanation are not interchangeable evidence classes.

## Research communities and labs

Useful places to watch when a concrete capability question opens:

- **ISMIR** — primary MIR research conference; tutorials and proceedings are useful for current task framing and evaluation practice.
- **MIREX** — shared-task culture and established task metrics.
- **ICASSP / DAFx** — audio, signal processing, separation, enhancement, and machine listening.
- **ICML / ICLR / NeurIPS** — representation learning and foundation-model work.
- **CHI / DIS / NIME / Audio Mostly** — music interaction and human-centered creative systems.
- **Music Encoding Conference** — symbolic notation and encoding.
- **MTG / Universitat Pompeu Fabra** — MIR, Essentia, datasets, trustworthy music AI.
- **C4DM / Queen Mary University of London** — MIR, semantic audio, DSP, perception and interaction.
- **International Audio Laboratories Erlangen** — synchronization, structure, decomposition, retrieval and the FMP ecosystem.
- **NYU MARL** — music/audio AI, cognition and machine listening.
- **Stanford CCRMA** — DSP, computer music, cognition, computational analysis and HCI.
- **Spotify Research** and **Adobe Research Audio** — commercial-scale music understanding, multimodal retrieval and creative interfaces.

When a research question matters enough to reopen, prefer the latest primary paper/repository/dataset page over a frozen statement here.

## OSS and model index

### Evaluation and data plumbing

- **mir_eval** — task-standard scoring utilities for several MIR tasks. Prefer its established semantics over custom matching where applicable.
- **mirdata** — dataset access/metadata conventions that can reduce bespoke corpus adapters when the target dataset is supported.
- **MARBLE** — reference framework for comparing pretrained music encoders across downstream tasks. Useful as an upstream benchmark source; do not reproduce its whole framework unless a focused product decision requires it.

### Signal / feature toolkits

- **librosa** — dependable general-purpose audio analysis primitives and reference baselines.
- **Essentia** — broad DSP plus pretrained model ecosystem. Treat licensing/commercial-use implications as a first-class gate before production use.
- **Sonic Annotator / Vamp ecosystem** — mature feature-extraction/plugin references and useful comparison points for analysis tooling.

### Symbolic and computational musicology

- **music21** — symbolic theory, key/harmony interpretation, score operations and corpus-oriented musicology.
- **Partitura** — MusicXML/MIDI/MEI handling and symbolic score analysis.
- **Symusic** — modern symbolic parsing/transformation option when performance or simpler MIDI/ABC handling becomes a measured need.
- **pretty_midi / miditoolkit** — practical MIDI utilities; use the smallest library that owns the required behavior.
- **MusPy** — useful for symbolic datasets/representations and generation-oriented evaluation when those become active product needs.
- **note-seq** — historical Magenta symbolic utility reference; verify maintenance status before considering new adoption.

### Transcription / pitch

- **Basic Pitch** — general-purpose audio-to-MIDI reference and production fallback in the repository's current bounded routing.
- **Transkun** — piano-specialized transcription reference; current production decisions and limits belong in the evaluation ledger, not here.

Do not infer current routing from this list; inspect the capability/engine registry and decision evidence.

### Beat / downbeat / meter

- **Beat This** — current repository evidence has already produced a bounded production decision; consult the ledger before reopening generic beat-engine selection.
- **BeatNet** — useful joint beat/downbeat/tempo/meter research reference when a concrete unmet meter/bar-phase requirement exists.
- Classical beat/downbeat datasets and MIREX conventions remain useful for independent validation, subject to lawful data access.

Separate beat-event recovery, downbeat recovery, tempo accuracy and meter/bar-phase quality. A correct BPM alone is not sufficient evidence for beat-relative claims.

### Harmony / tonality

- **lv-chordia** — current audio-chord production reference; do not restart engine selection without a concrete observed deficiency.
- **music21** — symbolic tonal/theory layer; symbolic-oracle metrics do not substitute for end-to-end audio evaluation.
- **BACHI** and other specialized symbolic systems remain references when a matching domain-specific question appears.

Useful corpus families include GuitarSet, POP909-related chord resources, DCML corpora, When-in-Rome and other task-specific annotated corpora, subject to licensing and domain fit.

### Melody / voice / notation

- **LStoM** — current symbolic melody reference; consult current production/evaluation evidence for its validated domain.
- **Piano_SVSep** — voice/staff prediction for symbolic piano engraving. This is not audio source separation and not semantic melody identification.
- **Partitura / music21 / Symusic** — prefer mature symbolic libraries where they replace custom score/MIDI manipulation cleanly.

Keep these tasks distinct:

```text
voice/staff assignment
≠ melody extraction
≠ phrase segmentation
≠ motif/recurrence analysis
≠ engraving
```

### Structure / form

Relevant references include:

- librosa recurrence/novelty baselines;
- MSAF and related historical segmentation frameworks;
- modern learned structure systems when their runtime/dependency/data contracts fit the actual question;
- SALAMI, Harmonix and other labeled structure corpora where lawful access is available.

Treat boundary detection, repeated-section grouping and semantic form labels as separate capabilities.

### Foundation representations / retrieval

- **MERT** — music-specific self-supervised representation reference.
- **MuQ / MuQ-MuLan** — music representation and audio-text alignment references. The evaluated released weights carried noncommercial constraints; re-check current code/weight terms before use.
- **MusicFM** — music foundation representation reference.
- **CLaMP3** — especially relevant research reference because it spans audio, text and symbolic modalities.
- **LAION CLAP / CLAP-family models** — generic audio-text baseline family.

The completed generic foundation bakeoff did **not** justify building production vector/search infrastructure by default. Reopen only for a concrete similarity/retrieval product question and use current decision evidence.

### Style / instrumentation / semantic tagging

- **Essentia pretrained models** and **MTG-Jamendo** are useful references for genre/style/instrument/mood evaluation.
- Foundation-model probes can be compared against task-specific classifiers.
- Raw model scores are not calibrated confidence and a genre/style label should not become a hard architecture router without evidence.

The completed context/style research did not promote a factual production tagging system. Consult the evaluation ledger before reopening.

### Source separation

Useful implementation/research families include:

- **BS-RoFormer / Mel-Band RoFormer**;
- **MDX / Demucs** families;
- **MSST (Music Source Separation Training)** as a multi-architecture training/inference ecosystem.

Code, model weights and training-data terms must be checked separately.

The completed source-separation research track did not establish a universal production-preprocessing requirement. Reopen only when a named product claim or interaction requires source-aware evidence and the downstream value can be measured.

### Audio-language / semantic reasoning

- **LLark** — useful architecture/evaluation reference for music instruction following; the evaluated release did not provide a drop-in trained model.
- **Qwen audio/omni families** and other multimodal systems are useful comparison points as the field evolves.

Language-model output should remain a lower-trust semantic/hypothesis layer unless a task-specific evaluation proves stronger authority. Exact musical facts remain owned by specialized evidence.

## Dataset families to consider

Choose datasets by the **task and validated domain**, not by convenience. Useful families include:

- **MAESTRO / ASAP** — piano performance/transcription/symbolic alignment;
- **GuitarSet** — guitar notes/chords/beat-related evaluation;
- **POP909** and related symbolic annotations — pop symbolic melody/harmony/form questions;
- **Slakh / BabySlakh** — synthetic multitrack mixtures for selected source-aware tasks;
- **MTG-Jamendo** — genre/instrument/mood multi-label work;
- **SALAMI / Harmonix** — structure/segmentation;
- **DCML / When-in-Rome** — symbolic tonal/harmonic musicology;
- task-specific MIREX/ISMIR benchmark datasets where licensing and acquisition permit.

Record dataset version, split, licensing, acquisition method, exclusions and overlap risk in the actual evaluation result.

## Product and interaction references

These are references for **information architecture and interaction**, not implementations to clone.

### Hooktheory / TheoryTab

Useful lessons:

- relative notation can communicate relationships more directly than conventional performance notation;
- synchronized chord/melody views make theory inspectable;
- theory concepts become more useful when anchored to actual passages;
- corpus-relative statistics need explicit repertoire context.

### Sonic Visualiser

Useful lessons:

- synchronized waveform/spectrogram/MIDI layers;
- annotation layers and multiple time resolutions;
- plugin-based analysis;
- playback remains central while inspecting evidence.

### Moises / AudioShake

Useful lessons:

- source separation can be a user-facing interaction, not merely hidden preprocessing;
- stem playback and manipulation can provide direct musical verification;
- commercial stem quality is a useful external benchmark when a source-aware feature becomes important.

### Cyanite / Spotify Research

Useful lessons:

- style/context outputs are naturally multi-label and segment-aware;
- music understanding increasingly connects analysis to search, similarity, recommendation and language;
- evaluation and model-version provenance matter at product scale.

## Music/domain learning references

For general MIR and DSP foundations:

- Meinard Müller, *Fundamentals of Music Processing*;
- the FMP notebooks/ecosystem;
- Audio Signal Processing for Music Applications;
- Stanford CCRMA coursework and references.

For Western tonal analysis:

- MIT OCW Harmony & Counterpoint / Musical Analysis;
- Aldwell & Schachter, *Harmony and Voice Leading*;
- Open Music Theory.

These are not universal musical ontologies. Genre/culture-specific explanatory work should identify the framework and use appropriate musicological/ethnomusicological/production sources rather than extrapolating common-practice tonal theory.

## Licensing and adoption checklist

Before a candidate becomes a production dependency, separately record:

1. code license;
2. model/checkpoint/weight license;
3. training/evaluation dataset terms;
4. commercial-use constraints;
5. model/download size;
6. CPU/GPU/RAM requirements;
7. container/architecture compatibility;
8. maintenance/release status;
9. task-standard evaluation evidence;
10. the concrete product capability or user problem it enables.

Do not treat `pip install` success, a permissive code license, or an impressive paper table as sufficient production evidence.

## Focused research issue template

A new research question should be bounded like this:

```markdown
# User/product question
What concrete user capability or failure motivates this work?

# Task
Exactly what is predicted, represented, or compared?

# Baseline and candidates
Current production behavior plus the smallest credible candidate set.

# Licensing
Code, weights and data separately.

# Evaluation data
Dataset/version/split/domain, lawful access, overlap risks.

# Metrics
Established task metrics and tolerances where possible.

# Operational evidence
CPU/GPU, latency, RAM, model size, install/container fit.

# Product gate
What result would justify changing production or exposing the capability?

# Output contract
Evidence/provenance/abstention behavior.

# Decision
ADOPT / KEEP / REPLACE / REJECT / REVISIT.
```

The durable output of research is the smallest decision/evidence surface needed to answer the question. Completed one-shot harnesses and candidate-ranking prose should not remain permanent repository authorities.