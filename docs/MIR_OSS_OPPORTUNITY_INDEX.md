# MIR / OSS Opportunity Index

> **Status:** product/research companion, not a second roadmap.
>
> **Updated:** 2026-08-30
>
> **Canonical direction:** #458 remains the single product/music-understanding roadmap. `docs/RESEARCH_LANDSCAPE.md` remains the broad field/model landscape. PR #668 owns the OSS-first evaluation policy. This file answers a narrower question: **which existing MIR/OSS primitives look underutilized for concrete ListenCloser experiences, given decisions the repo has already made?**

## 1. Product thesis

ListenCloser should not become a dashboard of MIR outputs. Its strongest product direction is a **musical relationship navigator**:

```text
hear a recording
→ notice / select a moment
→ see what changed or repeats
→ compare it with another moment
→ inspect the evidence
→ ask a grounded follow-up
```

The highest-value product object is therefore not `tempo`, `chord`, `embedding`, `section`, or a model name. It is an **inspectable relationship between localized musical evidence**.

This is consistent with #458 and deliberately avoids reopening the broad research gates already resolved or parked in #321 (structure), #333 (style/instrument tagging), #335 (beat engine), #337 (generic AMT), and #339 (audio-language QA).

## 2. Current product gap

The current stack is comparatively strong at producing localized or global facts about notes, harmony, pulse/rhythm, and synchronized representations. The larger product gap is what happens **between facts**:

| Product question | Current posture | Opportunity |
| --- | --- | --- |
| What changed here? | some measured series/findings exist; no first-class change navigator | derive change relationships over trusted evidence |
| What repeats? | product direction exists; generic recurrence is not yet a normal interaction | deterministic recurrence / motif search before embeddings |
| How is this passage different from that one? | relation/context foundations exist, first bounded vertical in #588 | make A/B comparison a core passage action |
| Why does this moment feel larger / thinner / busier? | perceptual/rhythm evidence exists but is weakly surfaced | multi-evidence convergence, not causal prose from one metric |
| How was this performance interpreted? | weak/absent | score↔performance alignment + expressive performance descriptors |
| How do two performances of the same work differ? | absent | robust cross-recording / score synchronization |
| Can I find this kind of passage again? | foundation embeddings evaluated but not promoted | start with task-specific deterministic similarity; reopen embeddings only for a concrete missed query |
| Can I isolate the source responsible for a claim? | source-separation decision is RESEARCH | task-conditioned stems only when a source-aware claim earns them (#334) |

## 3. A better default experience

A more ambitious ordinary Work experience could look like this:

1. **Original audio is the default listening source.** Representations are synchronized lenses, not separate mini-apps.
2. A quiet shared timeline exposes a small number of **measured moments**: strong change candidates, repeated material, and supported contextual outliers.
3. Clicking a moment focuses the same span everywhere and makes **Loop** a behavior of that one visible selection.
4. Breakdown answers a compact set of questions: **what changed, what repeats, what is unusually dense/sparse, what evidence coincides here?**
5. Every important finding has actions such as **Hear**, **Loop**, **Compare**, **Show evidence**, and, only when supported, **Find another occurrence**.
6. Compare is an A/B passage workflow in shared musical time, not merely “original vs derived representation.”
7. Ask inherits the same passage/relation context and explains only what the evidence contract supports.
8. Technical provenance is progressively disclosed instead of occupying the primary reading hierarchy.

This is mainly a relation/presentation program. It should consume the active selection/loop, shared-time, Breakdown, Ask, notation, and evidence work rather than compete with it.

---

# 4. Highest-leverage underutilized OSS

## 4.1 `ruptures` — generic change-point detection over trusted evidence

- **Upstream:** https://github.com/deepcharles/ruptures
- **License:** BSD-2-Clause.
- **Owns:** offline change-point detection for univariate and multivariate signals using established algorithms/cost functions.
- **Why it fits ListenCloser:** production already has time-varying perceptual/rhythm evidence. A generic change detector can turn those series into candidate relationships without inventing “verse/chorus” labels.
- **Concrete UX:** a **Moment / Change Map**: “energy and low-band activity rise together here”; click → focus/loop → compare before/after.
- **Recommendation:** **EVALUATE SOON**, but only as a thin candidate generator over evidence already trusted in `capabilities.json`.
- **Do not:** equate a statistical change point with musical form, significance, or cause.

## 4.2 `STUMPY` — recurrence, motifs, novelty, subsequence similarity

- **Upstream/docs:** https://stumpy.readthedocs.io/
- **License:** BSD-3-Clause.
- **Owns:** matrix-profile time-series mining: motif/repetition discovery, discord/novelty discovery, semantic segmentation, snippets, chains, and multi-window profiles.
- **Why it fits:** #458 explicitly wants “what repeats”; #460/#548 anticipate recurrence/other-occurrence relationships. STUMPY can operate over existing scalar or multivariate evidence and does not require a foundation embedding layer.
- **Concrete UX:** **Find another moment like this** within the current Work; “this density/energy contour recurs around 1:42.”
- **Recommendation:** **EVALUATE SOON** on one bounded query. Define the feature representation and musical window explicitly; compare against a simple deterministic baseline.
- **Do not:** call nearest-neighbor time-series shape “same musical section” or general semantic similarity.

## 4.3 `Parangonar` — score/performance alignment, repeats, subparts

- **Upstream:** https://github.com/sildater/parangonar
- **License:** Apache-2.0.
- **Current status:** active 3.x releases; current package includes offline note matching, online matching, `TheGlueNoteMatcher`, `RepeatIdentifier`, `SubPartMatcher`, and audio-to-score matchers.
- **Why it fits:** ListenCloser already cares about score, performance MIDI, shared time, and exact provenance, but does not yet have a first-class **performance interpretation** layer.
- **Concrete UX:** with a user-supplied/trusted score, show where the performance stretches tempo, anticipates/delays notes, changes articulation, or handles repeats differently.
- **Recommendation:** **HIGH-VALUE FUTURE EVALUATION** once a trustworthy independent reference score is an actual product input.
- **Critical truth boundary:** do not present “performance vs score” analysis when the score was generated from the same performance unless that derivation is explicit; otherwise the comparison is circular.

## 4.4 `Partitura` performance analysis — an existing dependency doing more than I/O

- **Upstream:** https://github.com/CPJKU/partitura
- **Docs:** https://partitura.readthedocs.io/
- **License:** Apache-2.0.
- **Owns beyond parsing:** performance representations, score↔performance encodings, tempo/timing/articulation parameters, MIDI velocity/dynamics, pedal/control information, note/performance features.
- **Why it looks underutilized:** the repo already considers Partitura a symbolic/notation utility, but its `encode_performance` / `make_performance_features` APIs directly support an entire evidence family that the product roadmap names but barely exposes: **performance/expression**.
- **Concrete UX:** tempo/rubato curve, onset asynchrony, articulation differences, dynamics, pedal evidence — all localized and inspectable.
- **Recommendation:** **UNDERUTILIZED**. Pair with a validated alignment source such as Parangonar rather than writing bespoke performance-descriptor formulas.

## 4.5 `Sync Toolbox` — robust audio↔audio / audio↔score synchronization

- **Upstream:** https://github.com/groupmm/synctoolbox
- **License:** MIT.
- **Current package:** 1.4.x; modern Python support.
- **Owns:** feature-based music synchronization / dynamic time warping workflows for aligning different recordings and score-related representations.
- **Concrete UX:** **Compare two performances** of the same work in shared musical time; scrub one and keep the other aligned; compare tempo/phrasing/energy at corresponding passages.
- **Recommendation:** **HIGH-VALUE FUTURE PRIMITIVE** if cross-version or interpretation comparison becomes a product interaction.
- **Do not:** add merely because DTW is useful; first establish the cross-recording compare workflow and accepted input contract.

## 4.6 `music21.features` / jSymbolic-style features — use what is already installed before inventing descriptors

- **Upstream:** https://www.music21.org/
- **Relevant docs:** https://music21.org/music21docs/moduleReference/moduleFeaturesJSymbolic.html
- **License:** BSD-3-Clause for music21.
- **Owns:** many symbolic descriptors across pitch, intervals, register, rhythm, texture/instrument metadata and other corpus/statistical features; music21 documents completion status for jSymbolic-derived extractors.
- **Why it fits:** the repo is already replacing handwritten Roman-numeral/function logic with music21. The same ownership principle applies to future symbolic descriptors.
- **Recommendation:** **CHECK FIRST** whenever a new symbolic feature is proposed. Adopt only features that map to a concrete claim; do not expose a giant feature vector to users.

## 4.7 `musif` — symbolic feature extraction / computational musicology

- **Upstream:** https://github.com/DIDONEproject/musif
- **License:** MIT on PyPI; verify exact release/repository terms before production adoption.
- **Owns:** MusicXML/symbolic feature extraction, windowed feature computation, music21 integration, extensible corpus-analysis workflows.
- **Why it fits:** potentially useful for **relative/contextual symbolic analysis** and for replacing bespoke corpus-statistics code if that product direction expands.
- **Recommendation:** **RESEARCH / REFERENCE**, not a dependency by default. Compare against already-installed music21/Partitura first.

## 4.8 `jSymbolic2` — broad symbolic descriptor reference

- **Upstream:** https://github.com/DDMAL/jSymbolic2
- **License:** GPL.
- **Owns:** large statistical feature set for MIDI/MEI, intended for MIR/musicology classification and corpus research.
- **Why it fits:** excellent vocabulary/reference for “what can be measured symbolically?” and useful in offline research.
- **Recommendation:** **REFERENCE / EVALUATION**, with GPL and Java/runtime implications treated as real product constraints. Prefer music21 equivalents when they satisfy the claim.

## 4.9 `Chromaprint` — exact/near-identical recording identity, not musical similarity

- **Upstream:** https://github.com/acoustid/chromaprint
- **License:** Chromaprint source is MIT; binary/distribution licensing can depend on bundled/external FFmpeg/FFT components, so verify the exact build.
- **Owns:** compact fingerprints for full-file identification, duplicate detection, and stream monitoring. Upstream explicitly says it is **not general-purpose audio similarity**.
- **Concrete UX/infra:** detect duplicate imports or likely identical recordings before creating redundant Works/Versions.
- **Recommendation:** **LOW-RISK UTILITY CANDIDATE** if duplicate Library content becomes a real problem. Keep it entirely separate from “sounds similar.”

---

# 5. Useful OSS with a specific future trigger

## 5.1 `Matchmaker` — real-time score following

- **Upstream:** https://github.com/pymatchmaker/matchmaker
- **License:** Apache-2.0.
- **Owns:** real-time audio/MIDI score following with multiple reference algorithms; 2025 ISMIR project.
- **Trigger:** only if ListenCloser adds a true **live practice / follow-my-playing** mode.
- **Potential UX:** live cursor, automatic page following, compare performed timing to a score while playing.
- **Status:** **WATCH**, not current recording-workspace priority.

## 5.2 `Audiveris` — optical music recognition

- **Upstream:** https://github.com/Audiveris/audiveris
- **License:** AGPL-3.0.
- **Current:** active 5.x releases in 2026.
- **Trigger:** user wants to import a printed/PDF score as an independent reference.
- **Potential UX:** “Add reference score” from PDF/image → align to recording → score-grounded performance analysis.
- **Status:** **WATCH / LICENSE-GATED**. Do not smuggle it into the backend as a casual utility.

## 5.3 `torchcrepe` / `libf0` — high-resolution fundamental frequency

- **Upstreams:** https://github.com/maxrmorrison/torchcrepe and https://github.com/groupmm/libf0
- **Licenses:** MIT.
- **Owns:** continuous F0 tracking (`torchcrepe` learned CREPE implementation; `libf0` open implementations of YIN, pYIN, Melodia-inspired and SWIPE approaches).
- **Trigger:** concrete product questions about tuning, intonation, vibrato, continuous pitch, monophonic expression, or musical systems poorly represented by semitone-note events.
- **Status:** **UNDEREXPLORED EVIDENCE FAMILY**, but do not add until a user-facing claim needs continuous F0.

## 5.4 `Omnizart` — broad transcription toolbox

- **Upstream:** https://github.com/Music-and-Culture-Technology-Lab/omnizart
- **License:** MIT.
- **Owns:** general toolbox spanning pitched instruments, vocal, drum, chord, beat, and more.
- **Caveats:** broad/heavy dependency surface; upstream documents ARM macOS incompatibility caused by dependencies.
- **Status:** **REFERENCE**, not a reason to reopen generic AMT (#337). Specialized production engines should remain preferred where already validated.

## 5.5 Sonic Annotator / Vamp ecosystem

- **Reference:** https://www.vamp-plugins.org/sonic-annotator/
- **Role:** mature batch feature-extraction/plugin ecosystem and useful research reference.
- **Status:** **RESEARCH TOOLING / REFERENCE**. Licensing and plugin/runtime complexity make it less attractive than direct libraries for a narrow production primitive.

## 5.6 `libfmp` and AudioLabs reference libraries

- **Reference:** https://www.audiolabs-erlangen.de/resources/MIR/FMP/C0/C0.html
- **Role:** high-quality open reference implementations for synchronization, structure, chroma, tempo, pitch and related MIR concepts.
- **Status:** **ALGORITHM/EDUCATION REFERENCE**. Prefer production-focused packages (`Sync Toolbox`, maintained task libraries) when available, but use FMP material to avoid reinventing standard methods incorrectly.

---

# 6. Technologies already researched: do not mistake “not in production” for “forgotten”

The repo has already spent meaningful effort on several fashionable families. They are not obvious missing integrations.

| Family | Existing decision / posture | Revisit only when… |
| --- | --- | --- |
| MERT | research embedding candidate; code permissive but open weights carry non-commercial restrictions in current repo evidence | a concrete retrieval/classification query needs it and license path is viable |
| MuQ / MuQ-MuLan | strong research candidate; code MIT, released weights CC-BY-NC 4.0 | research query is worth the non-commercial constraint or a compatible checkpoint exists |
| MusicFM | evaluated foundation representation | concrete task + license/runtime justify another look |
| CLaMP3 | unusually relevant cross-modal audio/MIDI/score/text embedding; measured tiny alignment probe but not promoted | “find this passage across modalities” or text→passage has a real product contract and beats deterministic alternatives |
| LAION CLAP | generic audio-text baseline; fast in prior repo evaluation but did not justify factual style/tag exposure | bounded semantic retrieval query needs a baseline |
| MARBLE | useful upstream foundation-model evaluation framework | use upstream task definitions; do not recreate a broad internal benchmark platform |
| All-In-One / SongFormer / MSAF | structure/form research | a concrete boundary-navigation UX is blocked and a lawful benchmark can change the decision (#321) |
| Beat This / BeatNet | beat/downbeat research | current PulseGrid evidence is demonstrably inadequate; do not churn engines for BPM alone (#335) |
| BS/Mel-Band RoFormer / MSST / Demucs family | source separation research | a **specific source-aware claim** proves mixture-only evidence inadequate (#334) |
| audio-language / instruction models | architecture/reference research | Ask has a concrete grounded capability unavailable from the evidence layer (#339) |
| generic multi-instrument AMT | researched | a downstream arrangement/bass/melody claim requires better symbolic evidence (#337) |

The important product move is to **consume the decisions**, not keep the research lane alive.

---

# 7. Recommended product experiments, routed to existing direction

## Experiment A — Moment / Change Navigator

**Question:** can a user immediately find the musically consequential transitions in a Work without asking a question first?

**Inputs:** existing production-grade perceptual/rhythm/harmony series only.

**Candidate implementation:** simple deterministic deltas first; `ruptures` as the maintained generic challenger.

**Output:** localized `change` relationships with explicit contributing evidence, no semantic section label.

**UX:** sparse timeline markers → click → loop → “what changed?” Breakdown → before/after compare.

**Routing:** this is existing evidence + relation/presentation logic. It belongs under the relation/change direction of #458/#460/#461 and perceptual evidence direction of #455, not a new structure program.

## Experiment B — Other Occurrences / “Find another moment like this”

**Question:** can a selected passage lead to useful within-Work recurrence navigation?

**Inputs:** start with one trusted representation: e.g. rhythm-density/perceptual profile or normalized symbolic contour.

**Candidates:** exact/deterministic matching → STUMPY matrix profile → only then reconsider CLaMP3/other embeddings if the desired relation is genuinely semantic/cross-modal.

**Output:** candidate occurrence spans + relation strength/provenance; abstain when no robust match exists.

**Routing:** aligns with the recurrence relation direction and future `other_occurrences` behavior already described around #460/#548. Do not build a vector DB first.

## Experiment C — Performance / interpretation evidence

**Question:** “How did this performance shape the written music?”

**Required new input:** a user-supplied or otherwise independently trusted score/MIDI reference.

**Candidates:** Parangonar alignment + Partitura performance features.

**Output:** localized tempo/rubato, timing/asynchrony, articulation, velocity/dynamics, pedal evidence; comparisons between score regions or performances.

**Why ambitious:** this is a differentiated music-understanding experience that most current ListenCloser analysis barely addresses, and it uses mature MIR primitives rather than another classifier.

## Experiment D — Compare recordings of the same work

**Question:** “How does performance A differ from performance B at corresponding musical moments?”

**Candidate:** Sync Toolbox for alignment; existing relation/comparison machinery for evidence.

**Output:** aligned A/B spans with measured tempo/energy/timing/dynamic differences and direct synchronized listening.

**Trigger:** only after ordinary within-Work A/B comparison is polished; do not jump ahead of #588/selection/shared-time work.

---

# 8. Product sequencing

## Finish / consume current owners first

Do not compete with active work around:

- Ask reliability/recovery (#792 and stacked selection work);
- one visible passage / loop scope;
- notation quality (#700 / current MuseScore candidate PR);
- solo-piano transcription routing;
- pulse-grid persistence;
- within-Work grounded context into Breakdown (#588);
- shared-time visual craft (#694);
- landing/brand work (#695).

## Then prioritize

1. **Change relationships from existing evidence** — likely the fastest jump from “analysis cards” to “music navigator.”
2. **Within-Work recurrence / other occurrences** — deterministic first, embeddings only if justified.
3. **A/B compare as a first-class action** — make relations audible and inspectable.
4. **Performance/expression with independent score input** — major new capability family, strongly OSS-enabled.
5. **Cross-recording interpretation comparison** — ambitious follow-on once alignment/compare primitives are product-ready.

---

# 9. Adoption rule

Before adopting anything in this index, answer:

1. Which exact user action or musical question becomes better?
2. Can the answer be derived from evidence already in production?
3. If not, what genuinely new evidence primitive is required?
4. Is there maintained OSS that owns the generic algorithm?
5. What code, model-weight, and dataset licenses apply separately?
6. What domains were evaluated and where must the product abstain?
7. Can the result be localized in shared musical time and heard/inspected?
8. What bespoke code or conceptual machinery does adoption delete or avoid?

If there is no concrete product query, **do not integrate the technology**.
