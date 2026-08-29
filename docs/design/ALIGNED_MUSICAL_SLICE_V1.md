# Aligned Musical Slice V1

**Status:** competing landing/identity prototype for adversarial comparison with PR #405’s Signal Landscape. This is not a recommendation to merge production UI.

## Hypothesis

A hero can feel contemporary and art-directed **without becoming generic abstract tech art** if its dominant object is one clearly musical moment shown through multiple aligned representations.

The visual should pass #405’s hard test better than Signal Landscape:

> If logo and marketing copy disappear, does the object still plausibly belong to a product about recorded music, musical representations, and evidence-backed understanding?

## Composition

One continuous 8–15 second musical slice, not a dashboard/card grid:

1. **Audio envelope** — one waveform strip.
2. **Detected notes** — one sparse piano-roll lane aligned to the exact same horizontal time axis.
3. **Notation** — a score/staff fragment aligned conceptually to the same passage.
4. **Shared playhead** — one blue time marker crossing the whole object.
5. **Evidence bracket** — one restrained evidence span / label tied to a production-safe observation such as note-onset density.

The object should read as **one piece of music observed several ways**, not three widgets stacked together.

## What makes this different from the rejected mini-dashboard hero

The earlier literal direction was rejected because it looked like product cards/screenshots placed inside a marketing hero.

This prototype intentionally removes:

- card chrome;
- buttons;
- tab controls;
- mini navigation;
- fake app window frames;
- multiple independent modules.

The representations share a single coordinate system and are composed as one visual artifact.

## Truth / production rules

The V1 HTML is an **illustrative design fixture**, not claimed product output.

If this direction advances toward production:

- use a known demo excerpt or captured real product data;
- waveform geometry must come from that excerpt;
- note events must come from a real/transcribed MIDI artifact;
- notation must correspond to the same excerpt where alignment supports it;
- evidence bracket must correspond to a real supported finding;
- experimental melody must not be presented as unqualified fact;
- do not imply note-level score alignment beyond the available alignment evidence.

## Motion

V1 should prove the composition primarily **static**.

If motion is added later, only meaningful options should be considered:

- one slow/shared playhead preview;
- one brief evidence-span emphasis;
- one-shot entrance revealing the layers as the same object.

Avoid ambient oscillation, particles, cursor parallax, and multiple independent loops.

## Relationship to signed-in design

This direction deliberately borrows the real visual semantics now being specified in:

- #433 — shared time + evidence orientation;
- #437 — real capabilities appearing as available;
- #438 — the real recording becoming a waveform.

That creates landing → workspace continuity: the marketing object uses the same conceptual grammar as the actual tool.

## Comparison criteria vs Signal Landscape

Score each direction 1–5 on:

1. **No-copy/no-logo product specificity** — can the product category be inferred from the visual alone?
2. **Truthfulness path** — can the prototype become real-data-driven without redesigning its concept?
3. **Landing → workspace continuity** — does the visual grammar exist in the signed-in product?
4. **Memorability** — does it feel specific enough to recognize later?
5. **Visual restraint** — can it remain expressive without distracting from the CTA/copy?
6. **Mobile legibility** — does the main idea survive narrow widths?
7. **Performance / accessibility** — can it be complete without heavy JS/WebGL/motion?

## Expected weakness

This direction can become too literal or educational if every lane is labeled heavily. It should remain editorial and sparse.

If it starts resembling a DAW screenshot, product card, or tutorial diagram, simplify it rather than adding more chrome.

## Prototype acceptance

The accompanying HTML should:

- remain recognizable with the left marketing copy visually ignored;
- use one dominant aligned object;
- show no fake interactive controls;
- use blue only for shared time/playhead semantics;
- use warm/brass only for evidence emphasis;
- remain legible at 390px without turning into stacked feature cards;
- work fully with no animation.

## Review outcome options

After comparison with #405:

- **KEEP Signal Landscape** if it becomes convincingly music/product-specific and clearly wins on identity.
- **REPLACE with Aligned Musical Slice** if the aligned representation object is substantially more native to hello-ai.
- **HYBRID / MODIFY** only if the landscape can be truthfully generated from the same real musical slice without obscuring the representation/evidence concept.
- **DELETE BOTH** if another prototype materially outperforms them; neither direction is sacred.
