# Evidence Jump + Shared-Time Coherence V3

**Status:** design prototype / implementation contract. This is intentionally narrower than the visual R&D SOT in PR #405 and does not choose a landing-page identity.

## Why this is next

The highest-value signed-in visual work is not another decorative layer. The workspace already contains the right primary objects — waveform, piano roll, score, Breakdown/Ask, and global Transport — but explanations and representations need to feel like views of **one musical time**.

The interaction target is simple:

> When language points to music, the user should immediately see *where* it means, remain oriented in the representation they chose, and be able to hear that exact span without the UI performing unrelated state changes.

This is the signed-in counterpart to the product-specificity test in #405: remove the copy and the behavior should still feel specific to understanding music.

## Product invariants

1. **One shared performance-time position.** Global Transport remains playback authority.
2. **One shared selection.** Breakdown, Ask, waveform, piano roll, and aligned score views refer to the same selected musical span.
3. **Representation is not playback source.** A visual jump must never silently change what audio is playing.
4. **Focus is not Show.** Focusing evidence changes position/selection. Only an explicit Show action may switch representation.
5. **No fabricated precision.** A score highlight may only claim precise performance-time alignment when mapping evidence exists. Otherwise orient to the aligned measure/system rather than drawing a fake sub-measure time rectangle.
6. **Motion explains causality and then stops.** There is no persistent pulse, glow, shimmer, or ambient animation in the active workspace.

## Interaction contract

### A. Focus / evidence-linked jump

Triggered by clicking a localized Breakdown finding, evidence jump, or Ask citation.

Required state change:

- set shared selection to `[start_seconds, end_seconds]`;
- seek shared performance time to the start of that span;
- preserve active playback source;
- preserve active representation;
- ensure the selected span is visible if the representation is scrollable/zoomed;
- show a brief orientation treatment around the *real destination*;
- return to quiet selected state automatically.

Do **not**:

- start playback automatically;
- enable looping automatically;
- switch from original audio to transcription/score audio;
- switch Waveform → Piano Roll merely because the finding was derived from pitch evidence;
- open a modal/toast whose only purpose is to announce that a jump happened.

### B. Show

Show is the explicit representation-changing action.

- Keep current selection and performance-time position.
- Change only to a representation that is actually available.
- Preserve playback source.
- Re-run the same destination-orientation cue in the newly active representation.
- If the preferred representation is unavailable, do not render Show.

### C. Loop

Loop is a Transport action, not a visual effect.

- Available only when the selected span is valid in the active playback domain.
- Loop bounds equal the evidence span unless the user subsequently edits them.
- Enabling Loop should not change representation or source.

### D. Ask

- Opens Ask using the current shared selection.
- Evidence available to Ask must still obey capability exposure/trust rules.
- The Ask answer can point back to the same span or narrower supported spans.

## Visual language

### Persistent state

- **Playback/playhead:** blue/time color.
- **Evidence selection:** restrained brass-tinted region/boundaries.
- **Selected finding:** quiet surface/border treatment in Breakdown.
- Do not give the evidence selection a permanent glow.

### Transient orientation cue

Target duration: roughly **300–600 ms** for the representation emphasis, with any tiny location label gone within ~800 ms.

The cue can use:

- a one-shot increase in selection contrast;
- one outline/ring that decays;
- a short `Evidence span · 00:18.4–00:21.2` location label when useful.

It should not use:

- repeated pulsing;
- spring overshoot;
- scale animation on music content;
- viewport-wide flashes;
- moving gradients;
- particle trails.

For `prefers-reduced-motion`, skip interpolation and show the destination immediately with a slightly stronger static selected state.

## Representation-specific behavior

### Waveform

- Selection region maps directly from performance time.
- Playhead is a distinct 1px time marker.
- On evidence jump, the selected region briefly increases contrast.
- If zoomed, pan/center only as much as necessary to reveal the full span.

### Piano Roll

- Same horizontal time mapping as waveform.
- Do not highlight unrelated notes merely because they intersect the selection unless the finding has note-level support IDs.
- In a later multi-evidence pass, supported note entities may receive a secondary, quieter highlight inside the time selection.

### Score

Score is the important exception.

- Use performance→notation alignment (`measure_starts_seconds` or stronger future alignment evidence) when available.
- Prefer highlighting/navigating the aligned measure/system over pretending arbitrary pixel widths correspond exactly to seconds.
- If alignment is missing or weak, the score may show the current notation location but must not draw a precision time-range overlay.
- Keep the product’s existing distinction between notation time and performance time visible where needed.

## Breakdown / Ask behavior

A finding row should read as an explanation first, not a toolbar.

Recommended hierarchy:

1. time/scope;
2. headline;
3. concise evidence support;
4. trust/maturity when material;
5. capability-gated actions.

The row itself may perform Focus. This makes the entire explanation navigational without adding a large extra button. Explicit actions remain small and secondary.

## Prototype

`design/mockups/evidence-jump-coherence-v3.html`

The dependency-free prototype demonstrates:

- one shared 60-second time coordinate;
- Waveform / Piano Roll / Score tabs;
- one global playhead;
- one shared evidence selection;
- three finding types (production rhythm, experimental melody, production harmony);
- finding click = Focus only;
- Show = explicit representation change while preserving time;
- Ask = selection-scoped follow-up concept;
- one-shot orientation cue;
- reduced-motion behavior;
- responsive single-column layout.

The mock is deliberately not a visual redesign of the application. It tests the causal interaction grammar.

## Acceptance matrix

| Scenario | Must happen | Must not happen |
|---|---|---|
| Click rhythm finding while on Waveform | seek + select + brief waveform orientation | source switch, auto-loop, representation switch |
| Click melody finding while on Waveform | seek + select on Waveform; maturity remains experimental | silently jump to Piano Roll |
| Click Show on melody finding | retain selection/time and open Piano Roll | change audio source |
| Switch representation manually | playhead/selection persist | reset to 0 or clear scope |
| Ask from localized finding | Ask receives selected span | expose ask-withheld evidence |
| Score with valid alignment | orient to aligned measure/system | claim finer precision than alignment supports |
| Score without alignment | preserve shared time concept, no precise range overlay | fabricate a pixel-perfect time highlight |
| Reduced motion | immediate clear destination | required animation to understand location |
| Mobile | selection/finding semantics unchanged | compressed desktop-only animation/chrome |

## Browser acceptance for an implementation PR

At minimum:

- 1440×900 desktop;
- 1024×768 tablet-ish workspace;
- 390×844 mobile;
- `prefers-reduced-motion: reduce`;
- Waveform focus;
- Piano Roll Show;
- Score alignment case;
- selected span already visible vs initially off-screen;
- original-audio playback source remains unchanged across Focus and Show.

Tests should assert **state semantics**, not animation frame timing. Visual regression should confirm the quiet resting state and the selected destination treatment.

## Relationship to #405

This is one concrete execution lane for #405’s highest-value signed-in principles, but it does not edit or compete with #405’s visual R&D SOT.

The relevant design decision is:

- landing identity remains a prototype question;
- shared-time/evidence orientation is useful regardless of which landing identity wins;
- therefore this interaction can be evaluated and implemented independently.

## References

Use these for interaction principles, not identity copying:

- Hooktheory TheoryTab — real-time playhead highlights the exact musical location while chords/melody remain synchronized.
- Moises — chords/sections are synchronized to song time and become practical actions such as looping/practice.
- Sonic Visualiser — aligned panes/layers make different representations legible as views over one time coordinate.

## Follow-on design sequence

1. implement Focus destination orientation with existing shared selection/transport;
2. preserve the same cue across capability-gated Show;
3. audit all representation playheads/selections for the same time semantics;
4. add entity-level support highlighting only after multi-evidence provenance is correct;
5. then design truthful processing/evidence-arrival transitions;
6. then upload → waveform object continuity;
7. revisit landing hero selection after signed-in behavior has a stronger product-specific visual grammar to borrow from.
