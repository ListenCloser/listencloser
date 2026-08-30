# Visual / Interaction Identity Contract

Status: **durable design direction**. This document preserves the useful design conclusions from the historical visual R&D lane (#405) in a mergeable repository artifact. Prototype images and branch-specific implementation state are intentionally not the source of truth.

> **Shared musical time, representation continuity, and evidence-linked interaction are the product identity.**

The target is contemporary and distinctive without generic AI/startup chrome or maximum visual effects. The signed-out edge may be expressive; the signed-in workspace should behave like a calm creative instrument.

## Product-specific visual grammar

1. **One recording becomes the object.** Upload/recorded media is the durable center of the experience; processing state must not replace it.
2. **Everything refers to the same musical time.** Audio, waveform, Piano Roll, notation, selections, evidence, Breakdown, and Compare should feel like related views of one moment.
3. **Representations are related views, not interchangeable truth.** Original audio, transcription, score, stems, and derived evidence have different provenance and failure modes.
4. **Explanation returns to evidence and action.** Findings should point to supported spans and make useful actions—focus, compare, listen, inspect—obvious when those actions are actually available.
5. **The workspace is quiet when idle and clear when state changes.** Prefer stable composition and meaningful transitions over ambient animation.
6. **Unavailable is a truthful state, not a dead control.** Explain capability/evidence/timeline reasons where useful without fabricating readiness.
7. **Help is earned by ambiguity.** Terse/icon-only controls may deserve deliberate help; visible self-explanatory labels should not accumulate tooltip chrome.
8. **Progressive understanding must preserve usability.** Once durable audio exists, enrichment should reveal around it without turning the product into a blocking job monitor.

## Shipped interaction foundations

The following work established the baseline this document builds on:

- baseline craft / legibility — #446;
- actionable Breakdown — #439;
- grounded Ask starters — #448;
- multi-evidence provenance — #449;
- evidence-linked Focus / Show orientation — #450;
- truthful waveform decode continuity — #464;
- non-blocking progressive evidence arrival — #463;
- shared Transport tooltip craft — #479;
- product-native empty workspace / first-use identity — #489;
- explained fail-closed Ask actions — #496;
- focused Library / transcription help craft — #499;
- deterministic import / processing lifecycle — #494.

Historical visual experiments and replaced implementation PRs should remain historical references, not competing product specifications.

## Current production bridge

### Signed-out product story — #503

The signed-out page should explain the actual product before authentication without inventing demo evidence.

Direction:

- preserve Google OAuth behavior and obvious CTA/privacy affordances;
- use an editorial composition rather than an auth-card-only page;
- communicate the structural relationship `Audio / Notes / Notation / Evidence` around a shared time idea;
- make the narrative legible as **Listen → See → Explain**;
- avoid fake waveform peaks, notes, timestamps, findings, confidence values, playback state, or selected evidence before a real recording exists;
- use a deliberately simplified phone composition rather than shrinking desktop detail below legibility;
- keep motion restrained, one-shot, and optional; reduced-motion must remain complete;
- do not let landing-page expressiveness leak into a noisy signed-in workspace.

#503 owns the production implementation and its visual/browser evidence. This document owns only the durable direction.

## Progressive evidence arrival

The lifecycle dependency that originally blocked this direction (#494) has landed. Future signed-in refinement may now build on the real current lifecycle rather than the old prototype.

Contract:

- saved/original audio remains the dominant usable object;
- existing representations remain usable while enrichment continues;
- reveal capability state only when backed by real persisted artifacts/evidence;
- `Recording / Waveform / Transcription / Evidence / Notation` may communicate durable availability, not speculative internal job stages;
- do not manufacture a single synthetic completion percentage for heterogeneous downstream understanding;
- once durable audio exists, avoid blocking job-modal behavior as the primary product narrative;
- errors/disconnects preserve already-usable views and expose recovery where possible;
- operational job internals should remain secondary to what the user can hear, see, inspect, and compare;
- progressive arrival must not steal the user's active representation or playhead/selection state.

Any implementation should be validated against the canonical real import journey rather than a static prototype.

## Shared time / evidence interaction

The stable object is **musical time / supported span**, not a literal animated morph from waveform → MIDI → score.

Prefer interactions where:

- selecting a span is visible across compatible representations;
- playback and selection are related but not conflated;
- evidence can orient the user to the exact supported region;
- Compare preserves a common transport/time context where semantics permit it;
- unavailable mappings fail explicitly instead of visually implying false alignment;
- source changes preserve position when the representations genuinely share the timeline.

This is more important to product identity than decorative waveform, neural, or spectrum motifs.

## Color truth rules

Color communicates state, not decoration:

- **blue** — current playback/time relationships;
- **brass/accent** — identity, evidence, and selected/focused emphasis;
- **neutral graphite/white** — structural scaffolding, unavailable/empty state, ordinary chrome;
- never use active-state color to imply evidence, playback, readiness, or selection that does not exist.

If the concrete palette evolves, the semantic distinction should remain.

## Motion rules

- one moving focal region at a time;
- user-triggered or state-linked motion beats ambient motion;
- motion may orient or confirm, never carry required meaning alone;
- avoid continuous decorative motion in the signed-in workspace;
- preserve playhead/selection continuity across representation changes;
- reduced-motion must remain fully understandable and usable.

## Anti-slop gate

A visual treatment earns its place only when it does at least one of these:

1. explains the product;
2. communicates real state;
3. improves manipulation/orientation;
4. establishes identity without competing with the music;
5. reduces uncertainty.

Reject by default unless a concrete use case overcomes the cost:

- generic aurora / AI blobs;
- neural or particle fields;
- glass stacks as a default surface language;
- border-beam effects everywhere;
- magnetic buttons;
- typewriter/scramble animation for core copy;
- marquees;
- primary dock-style navigation merely because it is fashionable;
- persistent parallax;
- heavy 3D galleries;
- forced smooth scrolling;
- autoplay media;
- several ambient animations competing in one viewport.

The question is not whether an effect looks current in isolation; it is whether it makes the music-understanding workflow clearer, more trustworthy, or more memorable.

## Real-data rule

Do not use decorative examples that look like measured musical evidence when no measured evidence exists.

A richer landing/demo storyboard may use real waveform/note/notation/evidence content only when one canonical excerpt truthfully supports every visible layer and redistribution/use rights are clear. Until then, structural neutral rails are more honest.

## Brand / favicon

Brand exploration is secondary to interaction identity. Do not force a logo/favicon replacement merely to signal redesign progress. Revisit when there is a coherent product mark that reinforces, rather than distracts from, the shared-time/evidence model.

## CSS / implementation boundary

Design-system cleanup is a separate engineering concern from visual experimentation. Global/versioned CSS consolidation is owned by #523 and requires regression evidence. Do not mix a broad cascade refactor into a product-design PR just because both touch appearance.

Similarly, visual work must not silently change:

- evidence maturity/provenance;
- representation availability rules;
- playback-source semantics;
- auth behavior;
- persisted analysis lifecycle;
- API contracts.

## Decision labels

Use these labels for significant visual recommendations so prototypes are not mistaken for product commitments:

- **KEEP** — current treatment is appropriate;
- **MODIFY** — preserve concept, change execution;
- **REPLACE** — current concept should give way to a stronger one;
- **DELETE** — treatment adds noise/confusion without compensating value;
- **PROTOTYPE** — useful to explore, not production direction yet;
- **BUILD** — sufficiently grounded to implement and validate;
- **SHIPPED** — landed on `main` with relevant evidence.

## Current order of work

1. Finish the production-neutral signed-out story in #503 with exact-head visual/browser evidence.
2. Re-evaluate progressive evidence arrival on the **post-#494 current lifecycle**, preserving representation/transport continuity and real persisted availability.
3. Replace neutral demo structure with real content only when one rights-safe canonical excerpt supports every visible layer.
4. Keep CSS-layer consolidation isolated under #523.
5. Let interaction identity mature before forcing standalone brand ornament.

## Repository lifecycle

Direction belongs in versioned docs/issues; PRs should remain mergeable integration units.

#405 is the historical visual R&D workspace from which this contract was distilled. Once this document lands, #405 should be treated as historical prototype context rather than the active source of truth. Future updates to design direction should edit this document or a focused canonical issue, not keep a non-merge production PR open indefinitely.
