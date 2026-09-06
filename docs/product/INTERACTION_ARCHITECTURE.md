# Listen Closer interaction architecture

## Authority

This document is the human-facing interaction-architecture contract for Listen Closer. It refines the durable product constitution in `docs/product/PRODUCT.md` and the visual/application conventions in `DESIGN.md` without replacing either.

It owns the stable user-facing grammar for how a Work, representations, alternate interpretations, analysis layers, playback, selection, and Inspector compose into one product.

Technical truth remains with the focused owners:

- representation/Version authority: #613;
- evidence projection precision/focus: #807;
- Score↔performance alignment: #1083;
- Inspector hierarchy: #1161;
- explicit analysis discovery: #1173/#1258;
- melody/harmony object-first interaction: #1194;
- correction: #1193;
- UI tokens/primitives: #1211.

When this interaction contract changes an assumption in one of those owners, update that owner explicitly. Do not create a parallel state or authority system.

## North star

> **One piece of music. One playhead. One selection. Many synchronized views, interpretations, and layers.**

A user should be able to form a small stable theory of the product. New capabilities should extend that theory rather than introduce a new top-level mode, panel, or dashboard by default.

The ordinary product loop remains:

```text
hear → inspect → select → understand → verify → relate/compare → act
```

## Stable user-facing grammar

| Concept | User question | Canonical home |
| --- | --- | --- |
| **Work** | What music am I working on? | Library |
| **View** | How am I looking at it? | Music canvas |
| **Interpretation** | Which note/score interpretation is this View based on? | Contextual control on that View |
| **Layer** | What additional musical information is projected here? | View-local overlay/lane/control, often automatic |
| **Playback** | What am I listening to? | Transport |
| **Selection** | What passage/object am I operating on? | Shared workspace state |
| **Inspector** | What should I understand about this Work/selection/object? | Right contextual surface |

### Invariants

1. **Views change what the user sees.**
2. **Playback changes what the user hears.**
3. Changing View must not silently change Playback.
4. Selection is shared across compatible Views and Inspector/Ask.
5. A View remains stable while alternate interpretations are selected within it.
6. A model/engine does not earn permanent UI merely because it exists.
7. An analysis result goes to its natural musical geometry before prose.
8. Internal Work/Version/Artifact/provenance detail remains exact but secondary unless it is needed for control or trust.
9. First-use value must not require engine knowledge.
10. Feature count may grow quickly; permanent concept count must grow slowly.

## Source material is not a user-facing pipeline

Audio, MIDI/performance notes, and MusicXML/written score can each be first-class material for a Work. The processing graph may derive one from another, but the UI must not imply that every Work conceptually flows through `Audio → MIDI → Score`.

```text
                         WORK
                          │
           ┌──────────────┼──────────────┐
           │              │              │
        AUDIO           NOTES          SCORE
      recording       MIDI/events      MusicXML
           │              │              │
       imported         imported        imported
          or               or              or
       generated        derived         derived
```

Expected journeys:

| Starting material | Immediately useful | Optional later derivation |
| --- | --- | --- |
| Audio | Waveform + Original playback | performance notes, Score, analyses |
| MIDI | Piano Roll + synthesized playback | Score, analyses, later audio relation |
| MusicXML | Score + synthesized playback | Piano Roll/note projection, analyses, later audio relation |
| Audio + MIDI | both native Views | explicit alignment/relation |
| Audio + MusicXML | both native Views | explicit Score↔performance alignment |
| all three | all native Views | richer exact relations |

Belonging to one Work does not establish exact cross-source alignment. #1083/#807 remain authoritative for mapping precision.

## Representation admission rule

A primary View is a materially different coordinate system or reasoning task, not simply another renderable capability.

A new permanent View should require most of:

- a distinct reasoning job that is repeatedly useful;
- value that cannot be expressed adequately as an overlay/lane/contextual reduction;
- native interactions worth persistent navigation;
- stable mapping to shared selection/playback;
- a clear verification/escape path to neighboring Views.

Prefer, where adequate:

```text
annotation/styling
→ overlay
→ synchronized lane
→ contextual reduction
→ Inspector
→ primary View only when earned
```

## Current-main product audit

This is the explicit disposition for the current product as of the #1281 audit. `PROBE` means preserve current behavior until the named product question is answered; it does not authorize a parallel implementation.

### Import and source management

| Current behavior | Disposition | Target rule |
| --- | --- | --- |
| Upload recording | **KEEP** | Primary acquisition action for audio. |
| Public recordings | **KEEP** | Secondary acquisition route under Import. |
| Attach MusicXML inside the Import menu | **MOVE** | `Import` adds material; attaching/replacing Score material belongs contextually with the Work/Score View. |
| Choose score source inside the Import menu | **MOVE** | Interpretation selection belongs on Score, not acquisition. |
| Mandatory pre-import transcription choice (`Auto` / `Solo piano`) | **HIDE_BY_DEFAULT** | Use the best default. Put advanced processing options behind an explicit secondary disclosure when genuinely needed. |
| Mandatory pre-import Score-engine choice (`MuseScore` / `PM2S`) | **HIDE_BY_DEFAULT** | Engine selection is alternate interpretation/testing detail, not a prerequisite to importing audio. |
| Direct MIDI import | **ADD / focused missing path** | MIDI should be valid first-class Work material and immediately open Piano Roll + synthesized playback. Reuse #613 authority; do not revive historical Transform-mode IA. |

`Import` means **add source material**, not “configure the processing graph.”

### Primary Views

| View | Disposition | Rationale |
| --- | --- | --- |
| Waveform | **KEEP** | Native audio/performance-time navigation and the clearest grounding in the source recording. |
| Piano Roll | **KEEP** | Native performed/detected note objects and timing. |
| Score | **KEEP** | Native written/notation semantics; source and reconstructed Scores remain alternate interpretations inside the same View. |
| Spectrogram | **DEMOTE after current UI convergence** | The coordinate system is legitimate, but current ordinary product jobs do not yet justify equal peer navigation weight. Keep it reachable through a secondary `More`/audio-detail route until timbre/production/spectral interactions earn peer status. Do not delete its renderer. |

This demotion is a product-navigation decision, not a renderer-performance decision.

### Alternate interpretations / View basis

Current Piano Roll behavior is the reference pattern: the View remains `Piano Roll`, and a compact interpretation chooser appears only when multiple safe performance-domain interpretations exist.

Target vocabulary describes musical meaning:

```text
Original transcription
Edited transcription
Imported MIDI
Creative take
Attached score
Automatic score
```

Do not create `Piano Roll A / Piano Roll B / Score A / Score B` tabs. Engine/package names stay in Details or an explicit compare/alternate-interpretation action.

Score should converge on the same grammar: stable `Score` View, contextual `Based on`/interpretation selection for attached source vs generated interpretations.

### Analysis result geometry

| Analysis/result | Product home | Disposition |
| --- | --- | --- |
| Chords/harmony spans | Score symbols; Piano Roll harmony lane; temporal labels elsewhere; selected-object Inspector detail | **KEEP + deepen native projection** |
| Melody note interpretation | Piano Roll/Score note emphasis; optional reduction playback; Inspector detail | **KEEP + deepen native projection** |
| Beat/downbeat/pulse | Guides/ruler/beat grid where mapping is exact/adequate | **KEEP as layer** |
| Structure Map | Synchronized navigation lane/map | **KEEP**, not a primary View |
| Pitch Contour | Synchronized auxiliary lane | **KEEP**, not a primary View |
| Similar Moments | Contextual selected-passage operation + linked candidates | **KEEP contextual** |
| Measured Changes | Inspector/navigation destinations | **KEEP**, but do not present a read-only relation as if it required a new analysis job |
| Stems/Layers | Playback source choices; optional activity visualization later | **KEEP in Transport**, generation remains explicit |
| Lyrics alignment | Synchronized text lane/panel when available | **KEEP as future lane** |
| Performance expression | Compact synchronized lane set after exact alignment | **KEEP as future layer family** |
| Provenance/method/version | Lightweight disclosure | **DEMOTE from primary IA** |

### Inspector / Breakdown / Evidence

**KEEP Inspector.** It is the contextual understanding/action surface.

**KEEP Breakdown as an overview mode, but demote it as the universal destination for analysis.** The canvas should already expose useful musical objects and relations in context; Inspector explains the current Work, passage, or selected object.

**Evidence is proof, not navigation.** Use it when the user asks “why should I believe this?” rather than as the first route to the musical result.

Preferred hierarchy:

```text
musical object / useful claim
→ Hear / Loop / Focus / Compare
→ concise explanation
→ Evidence / provenance on demand
```

### Transport

**KEEP** Transport as the single home for what the user hears.

Examples:

- Original recording;
- transcription synthesis;
- Score rendering;
- edited/corrected interpretation render;
- stems;
- Melody solo/reduction;
- creative takes.

**KEEP Compare in Transport** when the comparison changes what is heard. View/representation switching must remain independent.

## Computation policy is independent from maturity

Do not infer execution policy from `Experimental` vs `Established`.

Use three computation policies:

### AUTOMATIC

Cheap, broadly useful information that makes the ordinary Work substantially better. Compute during normal hydration/understanding when operationally reasonable.

### LAZY

Useful but non-trivial information that should be computed only when the related musical surface is requested. Opening a View/layer can trigger it without forcing a separate capability-management ritual.

### EXPLICIT

Expensive, specialist, generative, privacy/external-service-sensitive, or intentionally optional operations that should require a deliberate user action.

### Current target classification

| Capability | Target computation policy | Notes |
| --- | --- | --- |
| Core performance notes / basic timing / existing ordinary harmonic evidence | **AUTOMATIC** | These are foundational to normal Piano Roll/Score/contextual understanding. |
| Chord/harmony projection | **AUTOMATIC presentation** | Projection should appear from already-admitted evidence; no second run action. |
| Melody object from the default bounded melody path | **AUTOMATIC or LAZY** | Do not require engine knowledge; use LAZY if runtime cost materially harms first-use. Maturity may remain Experimental. |
| Beat/downbeat projection | **AUTOMATIC presentation** | Existing admitted pulse should simply render where useful. |
| Measured Changes | **AUTOMATIC/contextual** | It is a read-only relation over available evidence; `Open` may navigate, but it is not conceptually a computation request. |
| Similar Moments | **EXPLICIT contextual action** | Requires an exact user-selected passage and represents an intentional relation query. |
| Structure Map | **EXPLICIT for now** | Optional whole-Work analysis; revisit LAZY only if cost/latency becomes low enough. |
| Pitch Contour | **LAZY candidate** | A user requesting the lane has already expressed intent; a separate Add-analysis step may be unnecessary if cost is acceptable. Preserve current explicit path until tested. |
| Stems / source separation | **EXPLICIT** | Expensive and changes available playback material. |
| Symbolic-detail breadth / specialist analysis | **EXPLICIT or LAZY by surface** | Do not expose a feature catalog merely because the backend can compute it. |
| Alternate model/engine comparisons | **EXPLICIT** | Preserve current output and generate/select another interpretation deliberately. |
| Generative transforms | **EXPLICIT** | Generated proposals are new artifacts, never source evidence. |

`Add analysis` therefore remains the discovery/run surface for the **explicit subset**. It is not the universal gateway for every derived musical layer.

#1173/#1258 remain valid for product-owned explicit capability discovery. Their implementation must not be generalized into an automatic plugin/result registry.

## Canonical end-to-end journeys

### Audio-first

```text
Import recording
→ Original is playable as soon as durable
→ default Views/layers hydrate progressively
→ select a passage
→ Waveform ↔ Piano Roll ↔ Score preserves playhead/selection where mapping permits
→ contextual musical objects are visible in the canvas
→ Inspector explains/acts on the current context
```

### MIDI-first

```text
Import MIDI
→ Piano Roll is immediately useful
→ synthesized playback is available
→ optional Score can be generated later
→ later attaching audio creates a relation/alignment problem, not a replacement of MIDI authority
```

### MusicXML-first

```text
Import/attach MusicXML
→ Score is immediately useful
→ synthesized playback is available
→ a note/Piano-Roll projection may be derived honestly
→ later attached audio/performance remains a separate source until aligned
```

### Multiple interpretations

```text
open one stable View
→ choose Based on / interpretation
→ preserve playhead/selection where the mapping is adequate
→ compare alternatives explicitly when desired
→ ordinary use does not require model names
```

### Analysis-first interaction

```text
chord / melody / beat / structure information is visible in its natural geometry
→ select/click the musical object
→ Hear / Loop / Focus / Compare
→ Inspector explains it
→ proof/provenance only when wanted
```

### Expensive optional capability

```text
user explicitly requests capability
→ ordinary listening remains usable
→ local progress/failure state
→ result appears in its native musical surface
→ retry/provenance remain local
```

## Visible concept budget

A feature may add data and actions without adding a permanent concept.

Target persistent mental-model vocabulary:

```text
Work
View
Interpretation
Layer
Selection
Listening
Inspector
```

Before adding a new tab/panel/mode ask:

> Can this be expressed as an interpretation, layer, contextual action, playback source, or Inspector detail instead?

If yes, use the existing concept.

## Current implementation sequencing

Several active PRs overlap the physical frontend surfaces but not this product decision:

- #1245 / #1276 — visual-system and workspace-chrome convergence;
- #1259 — product-owned explicit `Add analysis` discovery;
- #1277 — monorepo rewrite / path convergence.

Do not create a competing workspace rewrite while those are active. The safe sequence is:

1. land/consume the current UI-system and discovery convergence;
2. carry this document through the monorepo rewrite without reintroducing retired UI strata;
3. implement bounded #1281 behavior slices against the settled tree;
4. each slice deletes/moves an old concept rather than adding a parallel one.

Highest-leverage behavior slices after the convergence point:

1. **Import simplification:** default audio import without mandatory transcription/Score-engine choice; move Score source/interpretation controls to Score context.
2. **Direct MIDI-first Work:** accept MIDI as source material and open Piano Roll + synthesized playback without pretending it came from audio.
3. **Stable Score interpretation control:** attached vs generated Score selection directly on Score using the same mental model as Piano Roll interpretation.
4. **Spectrogram demotion:** preserve renderer, reduce peer-navigation weight until a repeated spectral/production job earns it back.
5. **Analysis projection:** make Chords + Melody directly useful across at least two Views from one underlying result before adding more analysis families.
6. **Inspector contextualization:** make selected object/passage the default explanation/action context; keep Breakdown useful but stop routing every result through prose first.

## Verification contract

For each product slice, verify user-visible semantics rather than only component structure:

- View switch does not steal playback;
- playhead/selection survives where mapping permits;
- interpretation changes bind to exact authority and clear incompatible object selection;
- approximate/unsupported mappings do not look exact;
- provenance remains reachable without occupying primary space;
- no engine/model jargon is required in first-use;
- responsive/mobile staging preserves the same mental model;
- keyboard/focus interaction remains valid;
- concept count decreases or remains flat when capability count increases.

## Non-goals

Do not build from this contract:

- a generic plugin/capability registry;
- a universal layer framework before repeated implementation earns one;
- a generic result renderer;
- a detector/model dashboard;
- a second Version/authority resolver;
- a second client state system;
- a DAW or notation editor;
- one giant UX rewrite PR.

The product should become more capable while feeling conceptually smaller.