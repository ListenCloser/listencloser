# Visual Excitement Experiments

This is an R&D queue, not a mandate to make the product louder.

The product should feel contemporary because **music, state, and causality are visible**, not because the interface accumulates trendy effects.

## Decision rule

A visual treatment earns its place when it does at least one of these:

1. explains the product faster;
2. makes a state change easier to perceive;
3. makes direct manipulation feel more physical;
4. creates memorable identity without competing with music;
5. reduces uncertainty during waiting or processing.

If it only looks impressive in a component gallery, it is not enough.

## Tier A — worth building / testing

### 1. One recording, many representations
**Status:** implemented as a lightweight landing study in PR #405.

Use one musical moment across waveform, piano roll, score, and evidence-backed interpretation. This is stronger than feature cards because it demonstrates the product model directly.

**Why it adds value:** comprehension + differentiation.

### 2. Upload → waveform continuity
When a user drops a file, let the drop surface transition directly into the first waveform rather than disappearing into a generic progress state.

Keep the transition short and deterministic. The purpose is to communicate “your recording is now the object in the workspace.”

**Why it adds value:** continuity + confidence during import.

### 3. Processing as evidence arriving
Instead of a generic spinner, progressively reveal the kinds of evidence that have actually become available: audio ready, beat grid ready, transcription ready, score ready, analysis ready.

Do not fake intermediate results and do not animate notes that have not actually been computed.

**Why it adds value:** reduces uncertainty; exposes pipeline truthfully.

### 4. Evidence-linked Ask response
When an Ask answer cites a time range, briefly emphasize that same range in the active representation and offer a direct jump/loop affordance.

No ambient animation. Motion happens only as a consequence of the answer or user action.

**Why it adds value:** trust + causal connection between language and music.

### 5. Shared playhead micro-feedback
Keep the playhead visually consistent across waveform, piano roll, score, and section/evidence lanes. When a user jumps from an insight, the destination can use a brief pulse/fade to explain where they landed.

**Why it adds value:** orientation across representations.

### 6. Brand motion identity
The resonance mark can have one short loading/entry animation where the continuous trace resolves against the staff/grid. Never loop it continuously in normal app chrome.

**Why it adds value:** identity without persistent distraction.

## Tier B — prototype before committing

### 7. Representation morph on the landing page
A scroll or tap interaction could transition a single passage from waveform → notes → notation → evidence.

Prototype this only if it remains understandable with reduced motion and without scroll-jacking. Prefer CSS/SVG or a tiny state machine before Motion/GSAP.

**Risk:** easy to turn into a marketing gimmick; mobile can become vertically expensive.

### 8. Hover/tap signal exploration
On the landing demo, pointer/touch position could reveal the aligned moment across the four representations.

**Risk:** must still make sense without hover; should not introduce a fake transport that users mistake for a functioning player.

### 9. Subtle music-reactive landing hero
A real demo recording could drive a restrained waveform/spectrum treatment.

**Risk:** autoplay/audio permissions, CPU cost, accessibility, and a strong temptation to overproduce the landing page. Only worth doing with real audio and an explicit play action.

### 10. Section timeline as editorial storytelling
A horizontal section lane could become a visually strong navigation surface: Intro · Verse · Chorus etc., with density/energy changing underneath.

**Risk:** depends on trustworthy structure analysis; do not make speculative labels look authoritative.

## Tier C — current hype, low product value

Avoid unless a future use case proves otherwise:

- WebGL shader backgrounds
- particle fields
- aurora blobs as primary identity
- magnetic buttons
- cursor-follow spotlights everywhere
- dock navigation
- glass-card stacks
- animated border beams
- shiny text
- text scramble/typewriter for core copy
- marquee content
- infinite floating cards
- 3D galleries
- scroll-jacking / forced smooth scrolling
- persistent parallax in the editor

These can look contemporary in isolation while making a dense creative tool feel less trustworthy and less direct.

## Motion budget

The default product rule should be:

- one moving focal region at a time;
- user-triggered motion beats ambient motion;
- entrance motion is one-shot;
- no animation is required to understand a control;
- reduced-motion is fully usable, not a degraded fallback;
- avoid adding Motion/GSAP/Three until a prototype demonstrates value that CSS/SVG cannot provide;
- do not animate expensive filters or layout properties during continuous interaction.

## Visual language guardrails

Keep:

- warm graphite workspace;
- paper-like notation surface;
- restrained brass identity/accent;
- blue reserved for playback/score-time relationships;
- editorial display typography at the marketing edge;
- compact, precise sans/mono typography in the tool;
- low radius, low gloss, low card count;
- the music representation as the largest visual object.

The landing page may be more expressive than the editor, but it should feel like the same instrument before and after sign-in.

## Current reference pool

Useful pattern sources to study, not copy wholesale:

- https://21st.dev/community/components/explore/hero-scroll-animation
- https://21st.dev/community/components/explore/sticky-scroll-reveal
- https://21st.dev/community/components/explore/hero-scroll
- https://21st.dev/community/components/explore/audio-player-ui
- https://21st.dev/community/components/s/waveform
- https://21st.dev/blog/react-scroll-animation-components

The most reusable lesson from these references is not “add more animation.” It is that modern landing pages often make the **product itself the hero media** and use motion to explain transitions. That principle fits this product better than importing their visual effects literally.
