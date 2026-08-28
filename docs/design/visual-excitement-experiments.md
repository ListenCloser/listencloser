# Visual Enhancement Source of Truth

> **Status:** active design R&D for PR #405.
>
> This document is the authoritative source for visual enhancement proposals, references, decisions, guardrails, and review questions. Chat discussion and earlier #405 hero/favicon experiments are superseded when they conflict with this file.

## 0. Executive decision

The goal is **more polish, identity, and wow factor without turning hello-ai into a component-gallery demo or generic AI startup**.

Current direction:

- **SELECTED FOR FURTHER PROTOTYPING:** **Signal Landscape** — an abstract contour/spectral object with extremely slow SVG/CSS motion.
- **STRONG IMPLEMENTATION REFERENCE:** Kokonut / 21st.dev **Background Paths** — borrow path composition and motion discipline, not the stock gradient-startup aesthetic.
- **STRONG MOTION REFERENCE:** **Entropy** — borrow the organic order→structure feeling; do not run the full busy effect persistently.
- **AESTHETIC REFERENCES ONLY:** Halide Topo, Liquid Metal — borrow single-object confidence, monochrome technical depth, and negative space; reject theatrical 3D/parallax/shader identity for now.
- **REJECTED:** the first #405 miniature-workspace hero (waveform + piano roll + score + evidence cards). It was explanatory but looked like a designed mockup rather than a confident product identity.
- **UNRESOLVED:** favicon / logo. The current waveform/staff mark is not approved and should not be defended merely because it is already implemented.

The signed-out surface may be expressive. The signed-in workspace remains a calm creative instrument.

## 1. Visual evidence

### A. Ranked hero direction board

![Hero directions](./visual-rd/hero-directions.svg)

### B. Current animated Signal Landscape prototype

![Signal Landscape live prototype](../../public/landing-signal.svg)

The live prototype uses SVG/CSS only:

- 18 contour ridges;
- ~16–24 second low-amplitude drift;
- one slow brass trace;
- three very subtle evidence points;
- no pointer parallax;
- no JavaScript frame loop;
- no canvas/WebGL;
- no shader dependency;
- `prefers-reduced-motion` freezes the complete composition.

Target feeling: **slow musical respiration**, not an animated screensaver.

### C. Favicon / brand exploration board

![Brand directions](./visual-rd/brand-directions.svg)

Current preference is only a **lane**, not a final logo: derive a simple asymmetrical contour/fold from the same visual grammar, then simplify until it works in pure monochrome at 16×16.

## 2. Product-level design thesis

hello-ai should feel like an **editorial instrument**:

- precise rather than flashy;
- musically expressive rather than SaaS-generic;
- technically credible rather than mystical-AI;
- visually memorable without competing with the recording;
- dense and calm while operating;
- more art-directed while introducing the product.

The key principle is:

> **Make music, state, and causality visually interesting. Do not add visual effects simply because they are fashionable.**

A treatment earns its place when it does one or more of these:

1. explains the product faster;
2. communicates a real state change;
3. makes direct manipulation feel more physical;
4. improves orientation across representations;
5. establishes memorable identity without competing with music;
6. reduces uncertainty while work is processing.

If it only looks impressive in a component gallery, it is not enough.

## 3. Preferred visual system: Signal Landscape

### Why this is stronger than the original #405 hero

The previous mini-workspace illustration tried to explain every feature at once. It was legible but visually fragmented and literal.

Signal Landscape instead gives the first screen **one strong object**. It can imply waveform, spectral energy, self-similarity, density, topology, and time without becoming a literal fake screenshot.

That gives us:

- stronger negative space;
- one focal region instead of card soup;
- a visual language that can be genuinely product-specific;
- room for display typography without the common “serif + shiny blob” AI formula;
- a system that can decay into quieter forms throughout the product.

### Motion model

Motion should be almost subconscious:

- amplitude: a few pixels, not dramatic shape morphing;
- duration: measured in tens of seconds, not 1–3 second loops;
- no mouse chase by default;
- no scroll hijacking;
- no autoplay audio requirement;
- no animation needed to understand the page;
- all important information exists in the static frame;
- reduced-motion is a first-class static composition.

### Future data coupling

The initial version may be art-directed rather than numerically derived, but the strongest long-term version would let the visual grammar correspond to actual musical data.

Potential inputs:

- waveform envelope;
- spectral centroid / energy;
- note density;
- onset density;
- self-similarity / structural novelty;
- section boundaries;
- stem activity.

Do **not** fake a precise mapping before it exists. If data-driven behavior is added, it should be truthful and documented.

## 4. Expression should decay as the user enters the tool

The system should not be equally expressive everywhere.

| Surface | Expression budget | Recommended treatment |
|---|---:|---|
| Signed-out hero | 8/10 | animated Signal Landscape + strong typography |
| Landing body | 4/10 | sparse path fragments, real product media, restrained reveals |
| Upload/import | 4/10 | signal → real waveform continuity |
| Processing | 4/10 | real evidence becoming available; no fake progress theater |
| Empty workspace | 1–2/10 | static/faint contour fragment only |
| Active workspace | 1/10 | no ambient spectacle; state-linked micro-feedback |
| Breakdown / Inspector | 1/10 | evidence-linked pulse/jump only |
| Brand/favicons | static | simple monochrome glyph |

This is the main anti-slop mechanism: **the marketing edge gets the art direction; the work surface gets precision.**

## 5. Enhancements beyond the hero

The visual R&D is not just a hero project. These are the highest-value extensions.

### Tier A — worth building / testing

#### 5.1 Upload → waveform continuity

When a user drops an audio file, the import surface should not disappear into a generic spinner. A simple signal trace can resolve into the first **real waveform** once decoding is available.

Why it matters:

- communicates object continuity;
- makes import feel intentional;
- makes the product feel more tactile;
- creates wow through meaning rather than decoration.

#### 5.2 Processing as evidence arriving

Replace generic loading theater with truthful stages such as:

- audio available;
- timing evidence available;
- transcription available;
- notation available;
- analysis available.

A raw/loose signal can become slightly more structured as those real outputs arrive. This is where the **Entropy order→structure idea** is more appropriate than as a permanent full-page background.

Do not animate notes, chords, sections, or findings that have not actually been computed.

#### 5.3 Evidence-linked jumps

When Breakdown/Ask points to a time range and the user jumps there:

- seek the real shared transport;
- briefly emphasize the destination in the active representation;
- optionally pulse one short contour/trace cue;
- never leave an ambient animation running afterward.

This is visual polish that improves comprehension and trust.

#### 5.4 Shared playhead micro-feedback

Keep the playhead visually coherent across waveform, piano roll, score, and temporal evidence. Source/representation switches should feel like one shared musical time, not separate widgets.

#### 5.5 Landing body as product story, not feature-card grid

Below the hero, prefer 2–4 large editorial sections that show actual product behaviors:

1. **Bring in a recording** — upload/record → waveform.
2. **See the same moment differently** — waveform / piano roll / score synchronized around one playhead.
3. **Understand what changed** — one evidence-backed finding tied to a real time range.
4. **Ask about it** — one answer pointing back to the same musical evidence.

Use real product media or focused prototypes. Avoid a 6–12 card “features” bento unless hierarchy genuinely benefits from it.

#### 5.6 Tooltips / microinteraction primitives

Use high-quality OSS primitives for polish where appropriate: tooltips, disclosure, menus, segmented controls, state transitions. These should improve the existing product UI rather than introduce a new style language.

This is complementary to PR #401, which handles baseline legibility and craft.

### Tier B — prototype before committing

#### 5.7 One controlled representation morph

A single interaction could move from abstract signal → waveform → discrete notes → notation.

Good if:

- one-shot;
- short;
- understandable without motion;
- mobile-safe;
- no forced scroll choreography.

Bad if it becomes a long cinematic scroll sequence.

#### 5.8 Real music-reactive hero

A user-initiated demo recording could subtly drive the Signal Landscape.

Only pursue if:

- audio is explicitly started by the user;
- animation uses real data;
- CPU/mobile behavior is acceptable;
- the static hero remains complete;
- this tests meaningfully better than the quiet ambient version.

#### 5.9 Section/story navigation

A timeline-like landing navigation could reveal Intro → See → Understand → Ask, styled more like a playhead or chapter scrubber than conventional pills.

Prototype only; do not make navigation cryptic.

## 6. Reference matrix

These references are **construction material**, not aesthetic authority. `DESIGN.md` remains authoritative.

| Reference | Role | What to borrow | What not to borrow |
|---|---|---|---|
| [21st.dev / Kokonut Background Paths](https://21st.dev/@kokonutd/components/background-paths) | Strong implementation reference | animated SVG path composition, timing, lightweight structure | stock gradient-title/startup styling |
| [21st.dev / Entropy](https://21st.dev/@xubohuah/components/entropy) | Motion/art-direction reference | organic flow, order→structure feeling | busy persistent background / too many simultaneous elements |
| [21st.dev / Halide Topo Hero](https://21st.dev/@shivendra9795kumar/components/halide-topo-hero) | Aesthetic reference | monochrome topology, grain, technical depth | persistent mouse parallax, theatrical 3D entrance |
| [21st.dev / Liquid Metal Hero](https://21st.dev/@chowlol202/components/liquid-metal-hero) | Composition reference | one confident focal object, strong negative space | literal liquid-metal identity, shader dependency by default |
| [Motion Primitives](https://github.com/ibelick/motion-primitives) | OSS primitive pool | high-quality micro-motion, disclosure, spotlight/interaction ideas | applying motion primitives everywhere |
| [Magic UI](https://github.com/magicuidesign/magicui) | OSS pattern pool | backgrounds/reveals and polished copy-paste interaction patterns | generic “animated landing template” assembly |
| [React Bits](https://github.com/DavidHDev/react-bits) | Prototype pool | selectively explore unusual backgrounds/visualizations | broad dependency adoption; note MIT + Commons Clause terms |
| Mobbin | shipped-product pattern reference | proven navigation/interaction hierarchy | copying unrelated app visual identity |

### Licensing rule

21st.dev aggregates components from different authors/sources. Before copying an implementation into production, verify the **specific source component/package license**, not merely that it appears on 21st.dev.

Known reference-library status at time of this R&D:

- Motion Primitives: MIT;
- Magic UI: MIT;
- React Bits: MIT + Commons Clause restriction on reselling/redistributing the component library itself.

Keep licensing notes in any implementation PR that directly incorporates third-party source.

## 7. What we explicitly reject for now

These are not banned forever; they simply have poor expected value for the current product.

- generic aurora / colorful AI blobs as identity;
- generic neural-network or particle backgrounds;
- glass-card stacks;
- border beams / shiny borders everywhere;
- magnetic buttons;
- cursor-follow spotlight as a default behavior;
- text scramble/typewriter for core explanatory copy;
- marquee content;
- infinite floating cards;
- dock navigation as primary navigation;
- heavy 3D galleries;
- forced smooth scrolling / scroll hijacking;
- persistent parallax;
- autoplay media;
- multiple ambient animations in one viewport;
- full-screen shaders simply because they look impressive in isolation.

### “One effect” rule

Do not stack:

- shader + blur + glass + border beam + cursor spotlight + floating animation.

A polished composition should normally have **one dominant visual idea**, supported by typography, spacing, and restrained state feedback.

## 8. Brand / favicon SOT

### Current status

**Unresolved.** The currently changed waveform/staff favicon is not approved.

### Requirements

The next mark must:

1. work at 16×16 in pure monochrome;
2. have a recognizable silhouette without internal micro-detail;
3. not read primarily as a waveform/equalizer/music-note/AI sparkle;
4. not depend on gradients or animation;
5. feel compatible with both the expressive landing and restrained app chrome;
6. derive from the product’s signal/contour grammar without becoming a tiny illustration.

### Current preferred exploration lane

**Contour Fold:** a single asymmetrical continuous gesture that folds or crosses once.

Potential virtue: suggests signal, transformation, continuity, and musical phrasing without literally depicting any of them.

Risk: can still collapse into a generic wave if not simplified carefully.

No mark ships until desktop header, boot state, light/dark surface, 32px, and 16px comparisons are captured side by side.

## 9. Typography / color / texture guardrails

Keep:

- warm graphite/dark neutral as core product environment;
- paper-like score surface;
- restrained brass accent/identity;
- blue for playback/time-linked relationships where useful;
- editorial display typography on marketing surfaces;
- compact sans/mono in the tool;
- low gloss;
- limited radius vocabulary;
- minimal card count;
- music representation as the largest product object.

Avoid:

- purple as a generic AI accent merely because a reference uses it;
- gradient text as default branding;
- excessive serif everywhere inside the tool;
- grain so strong that it degrades legibility;
- huge hero copy that leaves no room for the actual visual/product object.

## 10. Motion budget

Global rules:

- one moving focal region at a time;
- user-triggered motion beats ambient motion;
- ambient motion belongs mostly to the signed-out edge;
- entrance motion is one-shot;
- menu/popover motion should be ~100–180ms;
- no animation is necessary to discover a control;
- reduced-motion must be fully useful;
- avoid adding Motion/GSAP/Three unless CSS/SVG cannot achieve the validated behavior;
- continuous effects must not animate expensive layout/filter properties unnecessarily;
- mobile may simplify or remove decorative motion rather than preserving desktop spectacle at all costs.

## 11. Relationship to other design work

### PR #401

#401 is the **baseline craft / legibility** lane:

- type scale;
- menu polish;
- Breakdown legibility;
- subtle control-state feedback.

It should remain conservative and is conceptually compatible with this SOT.

### PR #405

#405 is the **visual enhancement / identity R&D** lane and should remain the SOT for:

- expressive landing direction;
- visual reference evaluation;
- Signal Landscape prototype;
- marketing-to-product visual grammar;
- future meaningful visual enhancements;
- logo/favicon exploration.

Do not fold unrelated backend/product semantics into #405.

## 12. Review / handoff questions for another agent

When passing #405 to another design/product agent, ask them to challenge—not merely approve—the following:

1. Is Signal Landscape genuinely more distinctive, or does it still read as generic AI/data visualization?
2. Would Background Paths used more directly produce a more polished result than our custom SVG?
3. Is the current motion budget too subtle to create value, or appropriately restrained?
4. Which parts of Entropy’s motion language are worth borrowing without importing its busyness?
5. Does the visual grammar extend naturally into upload/processing/evidence feedback, or are we forcing a metaphor?
6. Does the landing still look like the same product when it transitions into the signed-in workspace?
7. Which OSS component should be used nearly OOTB because it is simply better executed than our bespoke version?
8. Which proposed effect is hype and should be deleted?
9. Does the Contour Fold favicon lane survive 16×16, or should brand exploration restart again?
10. Are there stronger free/OSS references—21st.dev or elsewhere—that we should add before implementation?

The reviewer should provide concrete references and, where possible, visual alternatives rather than only prose taste judgments.

## 13. Implementation / acceptance plan

Before #405 can become merge-ready:

1. #396 merge-gate/platform work lands first.
2. Rebase #405 on current `main`.
3. Keep Signal Landscape as the default prototype unless review produces a clearly stronger direction.
4. Verify source/license before adopting any third-party component code.
5. Capture real browser evidence at:
   - 1440×900 desktop;
   - ~820–980px tablet;
   - 390×844 phone;
   - `prefers-reduced-motion`.
6. Verify landing performance and no unexpected layout shift.
7. Confirm signed-in workspace has no new persistent ambient motion.
8. Confirm the shared mark/favicon direction separately; do not merge an unresolved logo merely as collateral.
9. Run the hardened exact-head merge gates.
10. Only then decide whether the visual direction earns a production merge.

## 14. Change log / superseded directions

- **Initial #405:** mini-workspace hero + simplified waveform/staff mark. **Rejected after visual review** as too literal/generic.
- **Second exploration:** more cinematic generative/sculptural mockups. **Useful for taste discovery**, but several still read as generic AI because of dark + serif + abstract glowing object conventions.
- **Current direction:** Signal Landscape informed by Background Paths / Entropy / topo references, with an intentionally much smaller motion and dependency budget.

This document should be updated whenever the design decision changes so #405 remains the single source of truth rather than accumulating contradictory artifacts.