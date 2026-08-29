# Upload → Waveform Object Continuity V3

**Status:** design prototype / implementation contract. This sits on top of the truthful processing model in design PR #437; it does not replace it.

## Goal

Make import feel like the user is placing **one recording** into the workspace, not submitting a file to a job system and later receiving an unrelated screen.

The visual idea is object continuity:

> file → durable recording → decoded waveform → progressively enriched musical object

The important constraint is truth:

> **Do not draw a waveform before the actual source audio has been decoded.**

A fake waveform may feel polished for a moment, but it teaches the wrong causal model and undermines the evidence-led product.

## What continuity means

Continuity does **not** require a literal morph animation.

The user should experience these states as the same object through stable anchors:

- filename/title;
- Work identity in Library;
- Canvas location;
- persistent Transport location once playback exists;
- source label (`Original` / uploaded recording);
- actual decoded waveform replacing a neutral source placeholder.

The interface may move between layouts, but these anchors should make the causal chain obvious.

## Entry contexts

### A. Empty workspace

Current empty Canvas already says `Import a recording`.

Target flow:

1. user chooses/drops a file;
2. the empty import surface becomes a compact **saving source** state in the same Canvas region;
3. until upload durability is confirmed, do not show a fabricated waveform;
4. once durable Work/source returns, Library gains/selects the Work and the workspace shell becomes the real saved Work;
5. the Waveform surface shows a source-decoding placeholder only until real peaks are available;
6. decoded peaks appear in place;
7. Transport becomes usable when the source playback URL is ready;
8. non-blocking understanding status continues per #437.

### B. Import while another Work is open

Do not destroy the current Work before the new source is durable.

Target flow:

1. current Work remains visible beneath/alongside the upload state;
2. upload confirms durability;
3. Library gains the new Work;
4. selection moves to the new Work;
5. new source hydrates into Waveform;
6. if upload fails before durability, the previous Work remains selected and usable.

This makes import failure recoverable without making the workspace feel erased.

### C. Reopen a source-only Work

No import transition is needed. The Work already exists.

- open directly into the source/Waveform loading state;
- decode/render real waveform;
- if enrichment is running, show #437’s compact non-blocking status.

## Visual states

### 1. Empty import

Quiet Canvas, one strong action.

Keep:

- `Import a recording`;
- transcription settings secondary;
- supported formats/size as metadata.

Avoid decorative audio visualizers before the user has supplied audio.

### 2. Saving source

The source is **not yet durable**.

Show:

- filename;
- truthful upload progress if available;
- copy such as `Saving recording…`;
- the same Canvas footprint the new Work will occupy where practical.

Do not show:

- waveform bars;
- Piano Roll / Score / Breakdown placeholders;
- fake processing stages.

### 3. Source durable, waveform decoding

The Work exists; this is now the real workspace.

Show:

- Library Work selected;
- title/header from the saved Work;
- Waveform tab available;
- neutral waveform loading surface with source label;
- Transport may show source availability/loading as appropriate;
- compact `Recording saved · Understanding audio…` status from #437.

Recommended neutral loading visual:

- center line / quiet audio-track frame;
- no oscillating fake peaks;
- optional subtle one-shot skeleton fade;
- accessible `Loading waveform from saved recording` status.

### 4. Real waveform ready

When decode completes:

- replace the neutral track frame with **actual peaks**;
- keep geometry stable so the content appears rather than the whole layout jumping;
- allow a ~120–180ms opacity transition;
- do not replay the transition every time the user returns to the Waveform tab if peaks are already cached for that component/session.

This is the product-specific “wow” moment: the recording itself becomes visible.

## Motion contract

The motion should communicate *object continuity*, not spectacle.

### Allowed

- filename/source label maintains position or moves a short, legible distance;
- upload card collapses into saved Work shell after durability;
- real waveform fades into a stable track frame after decode;
- newly saved Library row appears with a short one-shot entrance;
- 120–220ms transitions, no spring overshoot.

### Avoid

- fake waveform growing from zero before decode;
- particles flowing from upload button into Canvas;
- morphing generic bars into notes/score;
- progress rings around the brand mark;
- indefinite shimmer while backend analysis runs;
- large zoom transitions between Library and Canvas;
- forced animation on every Work switch.

### Reduced motion

- state swaps are immediate;
- no information is lost;
- layout anchors remain stable.

## Waveform component implications

Current `Waveform` internally fetches and decodes the source, then computes peaks.

That gives a truthful local lifecycle:

```text
idle → loading → ready | error
```

The design should reuse that real state rather than introducing a fake global waveform progress percentage.

Recommended production seam:

- expose/render a stable neutral track frame while Waveform status is `loading`;
- render real peaks at `ready`;
- render a local non-destructive error at `error` while preserving the saved Work and any playable source path available elsewhere.

Do not move decoded peaks into global Workspace state solely to power an animation unless another real product need justifies caching/sharing them.

## Library behavior

When durability is confirmed:

- the Work row appears exactly once;
- it is selected if this import is the user’s current action;
- processing state may be a small secondary status (`Understanding…`);
- the row should not oscillate between temporary/local and server-owned duplicates;
- deletion/rename semantics remain server-state-owned.

The row itself is another continuity anchor between import and the saved workspace.

## Transport behavior

- playback source becomes `Original` as soon as the durable signed source is usable;
- do not auto-play after import;
- initial position is 0;
- later processing output must not silently replace `Original` as the active source;
- when transcription/score audio becomes available, source choices appear without changing current playback unless the user chooses them.

## Failure behavior

### Upload fails before durability

- no new Work is presented as saved;
- if another Work was open, it remains usable/selected;
- show concise retry/dismiss feedback near the import action;
- do not leave a phantom Library item.

### Source saved but understand workflow fails to start

This is **not an upload failure**.

- open the saved Work;
- show real Waveform/Original source;
- recovery is `Process saved audio` per #437.

### Waveform decode/render fails

- do not equate visualization failure with source loss;
- if playback can still work, keep it available;
- say `Waveform could not be rendered` rather than `Recording unavailable`;
- other representations remain independent.

## Mobile

- file chooser returns into the same workspace, not a full-screen “processing” takeover after durability;
- source-saved state keeps Transport reachable;
- waveform decoding placeholder uses fixed height to prevent major layout shift;
- no horizontal motion choreography that depends on desktop Library/Canvas columns.

## Accessibility

- announce `Recording saved` once when durability is confirmed;
- announce `Waveform ready` only if useful; avoid noisy progress updates;
- upload progress has an accessible label/value;
- waveform loading state has `aria-busy`/status semantics without trapping focus;
- focus moves only when necessary; do not programmatically send keyboard focus into Canvas just because a file finished uploading.

## Current implementation implications

### `handleFile`

The key architecture change comes from #437: select/open the Work once upload returns the durable artifact/version rather than waiting for the entire understand job.

This design then adds only continuity polish around that truthful transition.

### `RepresentationStack`

Its empty state and mounted-representation behavior are already compatible with this direction.

- empty state can host the saving-source transition;
- Waveform remains a normal representation, not a bespoke post-upload page;
- once visited, mounted representation state avoids unnecessary remount choreography.

### `Waveform`

Already computes real peaks from decoded source audio. Keep that source of truth.

The main visual improvement is to make its loading/ready transition intentional and stable rather than trying to precompute a decorative waveform elsewhere.

## Acceptance matrix

| Scenario | Must happen | Must not happen |
|---|---|---|
| Empty workspace import starts | filename + truthful saving state | fake waveform / notes / analysis |
| Upload succeeds | saved Work appears/selects; real workspace opens | wait for full understand job |
| Waveform still decoding | stable neutral track frame | invented peaks |
| Decode completes | actual peaks appear in-place | layout reset / autoplay |
| Understand continues | source remains usable + non-blocking status | blocking modal returns |
| Import over existing Work fails pre-save | previous Work remains | blank/cleared workspace |
| Workflow start fails post-save | saved source remains; recovery offered | label import itself failed |
| Transcription later arrives | source/position stay unchanged | silent playback source switch |
| Reduced motion | immediate truthful state transitions | information dependence on animation |

## Prototype principles

The accompanying mock should demonstrate:

- empty import;
- saving source without fake waveform;
- durable Work with neutral waveform-decoding frame;
- real waveform visible;
- understanding still running after waveform is usable;
- later Piano Roll availability without stealing Waveform focus;
- pre-durability failure versus post-durability processing failure as visibly different situations.

## Relationship to #405 / #437 / #433

- #405: visual/identity R&D SOT; this is a concrete product-specific interaction lane.
- #437: defines the durability boundary and non-blocking processing behavior this transition relies on.
- #433: defines shared-time/evidence orientation once the Work is usable.

Together these provide a stronger product-specific visual grammar than adding more ambient landing effects:

```text
recording enters → becomes real waveform → gains representations/evidence → language jumps back to the same musical time
```

That sequence should eventually inform the landing story, rather than the landing inventing a separate metaphor first.
