# Visual Excitement Experiments

This is an R&D queue, not a mandate to make the product louder.

The product should feel contemporary because **music, state, and causality are visible**, not because the interface accumulates trendy effects.

## Current recommendation: Signal Landscape

After visual review, the original PR #405 miniature-workspace hero was rejected as too literal and visually generic. The current direction is the **Signal Landscape**: an abstract contour field that feels halfway between signal processing, topography, and musical phrasing.

The implementation prototype lives at `public/landing-signal.svg` and is intentionally lightweight SVG/CSS rather than a shader or 3D scene.

### Motion

The Signal Landscape is not meant to be static, but it also should not behave like an animated screensaver.

Current prototype motion budget:

- contour layers drift vertically by only a few pixels on 16–24 second cycles;
- one restrained brass trace moves slowly across a ridge;
- a few evidence points breathe subtly;
- no pointer parallax;
- no scroll-jacking;
- no JavaScript frame loop;
- no canvas/WebGL dependency;
- `prefers-reduced-motion` freezes the landscape into a complete static composition.

The desired feeling is **slow musical respiration**, not visible animation for its own sake.

### Why this direction is stronger

1. It provides one compelling object instead of a miniature dashboard.
2. It is abstract enough to create identity without becoming a generic waveform logo.
3. It can eventually be driven by real musical evidence, but does not need fake analysis to look complete.
4. It gives the product a reusable visual grammar beyond the hero.
5. It stays compatible with the calm signed-in workspace because the same language can reduce down to static lines, a playhead trace, or a small evidence pulse.

## Reference position

We should use good OSS/component work more directly when its execution is already polished, but treat it as a **construction kit, not an aesthetic authority**.

### Strong references

#### Kokonut UI / Background Paths

Use: **yes, strongly as implementation/motion reference.**

Why:
- animated SVG paths;
- no canvas and no custom frame loop;
- visually polished with relatively low implementation complexity;
- easy to reduce or recolor;
- its line/path vocabulary maps naturally to signal and musical structure.

What to change:
- no generic gradient-title treatment;
- fewer paths;
- slower motion;
- warm neutral / brass palette;
- shapes should imply signal structure rather than arbitrary decorative waves.

#### Entropy by xubohuah

Use: **motion/art-direction reference, not direct product component.**

Why:
- the compelling idea is order emerging from apparent chaos;
- organic movement feels more musical than conventional SaaS animation;
- useful inspiration for processing/transformation moments.

Risk:
- too busy as a persistent background;
- can quickly read as generative-AI art rather than music software.

Best use: a short transformation or processing sequence, not the entire application background.

#### Halide Topo Hero

Use: **aesthetic reference, not implementation.**

Why:
- monochrome technical landscape;
- depth and grain without generic gradient blobs;
- strong single-object composition.

Reject from the reference:
- persistent mouse parallax;
- dramatic 3D perspective as a primary interaction;
- long theatrical entrance.

#### Liquid Metal Hero

Use: **composition reference only.**

The single-object confidence is excellent. The literal liquid-metal/shader material is probably wrong for hello-ai and carries more rendering/dependency cost than the value it adds.

## Extending the visual system beyond the hero

The hero should be the richest expression. The same ideas can continue elsewhere at much lower intensity.

### 1. Landing-page section transitions

Contour/path lines can continue below the fold as sparse separators or connective traces instead of introducing a different decorative motif for every section.

**Intensity:** 3/10.

### 2. Import / upload

A dropped recording can begin as one simple signal trace and resolve into the real waveform when decoding finishes.

This is not decorative continuity: it communicates that the uploaded file has become the musical object in the workspace.

**Intensity:** 4/10, short and state-driven.

### 3. Processing states

Use the line grammar to show real evidence becoming available:

- source audio;
- timing/grid;
- detected events;
- notation;
- analysis.

Do not fabricate intermediate results. The visual should only become more structured as actual pipeline states complete.

**Intensity:** 4/10 while processing; stops when complete.

### 4. Empty canvas / onboarding

A very faint, fully static fragment of the contour field can give empty states identity without another illustration or card stack.

**Intensity:** 1/10.

### 5. Evidence jumps and selection

The workspace should not inherit the hero landscape. Instead, reuse only its smallest behavior: when an insight jumps to a musical region, a thin trace/pulse can briefly identify the destination.

**Intensity:** 1–2/10, user-triggered only.

### 6. Brand motion

The eventual mark can be derived from a single contour fold / resonance gesture. On boot it may resolve once from a line into the static mark, then remain still.

**Intensity:** 2/10, one-shot.

## Decision rule

A visual treatment earns its place when it does at least one of these:

1. explains the product faster;
2. makes a state change easier to perceive;
3. makes direct manipulation feel more physical;
4. creates memorable identity without competing with music;
5. reduces uncertainty during waiting or processing.

If it only looks impressive in a component gallery, it is not enough.

## Tier A — worth building / testing

### 1. Signal Landscape landing hero
**Status:** prototype implemented in PR #405.

Use a restrained SVG contour field as the landing focal object. It should feel derived from musical signal/structure even before we make it literally data-driven.

**Why it adds value:** identity + differentiation + establishes a reusable visual grammar.

### 2. Upload → waveform continuity
When a user drops a file, let the drop surface transition directly into the first waveform rather than disappearing into a generic progress state.

Keep the transition short and deterministic.

**Why it adds value:** continuity + confidence during import.

### 3. Processing as evidence arriving
Instead of a generic spinner, progressively reveal the kinds of evidence that have actually become available: audio ready, beat grid ready, transcription ready, score ready, analysis ready.

**Why it adds value:** reduces uncertainty; exposes pipeline truthfully.

### 4. Evidence-linked Ask response
When an Ask answer cites a time range, briefly emphasize that same range in the active representation and offer a direct jump/loop affordance.

**Why it adds value:** trust + causal connection between language and music.

### 5. Shared playhead micro-feedback
Keep the playhead visually consistent across waveform, piano roll, score, and section/evidence lanes. When a user jumps from an insight, the destination can use a brief pulse/fade to explain where they landed.

**Why it adds value:** orientation across representations.

## Tier B — prototype before committing

### 6. Real-data Signal Landscape
Drive contour geometry from real musical evidence (for example spectral energy, density, section novelty, or a downsampled self-similarity representation) rather than purely illustrative coordinates.

**Risk:** do not imply a direct scientific mapping unless the mapping is real and explainable.

### 7. Representation morph
A tap or one controlled scroll transition could move from abstract signal → waveform → detected events → notation.

**Risk:** easy to become marketing theater; mobile/reduced-motion must remain first-class.

### 8. Entropy-inspired processing transition
Use an order-from-chaos motion vocabulary during analysis/transcription, but only while the system genuinely moves from raw input to structured evidence.

**Risk:** visual busyness and generic generative-art feel.

## Tier C — current hype, low product value

Avoid unless a future use case proves otherwise:

- full-screen WebGL shader identity;
- particle fields;
- aurora blobs as primary identity;
- magnetic buttons;
- cursor-follow spotlights everywhere;
- dock navigation;
- glass-card stacks;
- animated border beams;
- shiny text;
- typewriter for core copy;
- infinite floating cards;
- 3D galleries;
- scroll-jacking;
- persistent parallax in the editor.

## Motion budget

- one moving focal region at a time;
- user-triggered motion beats ambient motion;
- ambient hero motion is extremely slow and low-amplitude;
- no animation is required to understand a control;
- reduced-motion is fully usable, not a degraded fallback;
- prefer SVG/CSS before Motion/GSAP/Three/WebGL;
- do not animate expensive layout properties during interaction.

## Visual language guardrails

Keep:

- warm graphite workspace;
- paper-like notation surface;
- restrained brass identity/accent;
- blue reserved for playback/score-time relationships;
- expressive typography at the marketing edge;
- compact, precise typography in the tool;
- low gloss and low card count;
- the musical object as the largest visual element.

The landing page may be more expressive than the editor, but it should feel like the same instrument before and after sign-in.
