# Evidence Jump / Shared-Time Current-State Audit

**Scope:** current `main` implementation seams relevant to the V3 evidence-jump prototype. This is a design-engineering audit, not a request for a new timeline architecture.

## Executive finding

The product already has almost all durable state required for coherent evidence jumps:

- Transport owns playback position/source/loop;
- Workspace owns one `MusicalSelection`;
- Waveform, Piano Roll, Spectrogram, and Score already read those shared states;
- representation canvases remain mounted after first visit, so switching views does not need to destroy/recreate expensive visual state.

The missing layer is **not another source of truth**. It is one consistent user-intent primitive — “orient me to this evidence” — plus a short-lived visual request so the active representation can make the destination obvious and then become quiet again.

## Current behavior by surface

| Surface | What already works | Current mismatch / opportunity |
|---|---|---|
| `RepresentationStack` | One active representation; previously visited canvases stay mounted. | This is a good base for Show. Preserve it; do not add transition-specific remounting. |
| `MusicalSelection` | Carries performance/notation time range, note IDs, measure range, and precision provenance. | Sufficient durable selection contract. Do not add a second “evidence selection” object. |
| Waveform | Reads shared performance position; draws selection; focused analysis annotations get stronger bands. | Annotation click currently selects a span but does not seek. There is no one-shot destination emphasis distinct from persistent selection. |
| Piano Roll | Reads shared position; auto-centers playhead; draws time selection and selected notes; focused annotations strengthen. | Annotation click selects but does not seek. Time-range selection currently highlights *all overlapping notes*; future evidence-specific note emphasis must wait for true support IDs. |
| Spectrogram | Reads shared position/selection and analysis annotations. | Same semantic opportunity as Waveform: evidence reference should use the same Focus primitive. |
| Score | Uses `measureStarts` to locate playback; renders a blue cursor/highlight; performance-time selections map to approximate measure ranges; direct score selection is exact on notation timeline. | Keep playback orientation, but do not make a performance-evidence span look note/pixel exact when only cross-domain measure mapping is justified. Strengthen the existing approximate measure highlight instead. |
| Breakdown | A localized finding currently `seek()`s to its start and sets a performance-time selection. | Good base behavior, but its current provenance marks the performance span `timeExact:false` and `measureApproximate:true`; that should be corrected at implementation time. No transient destination cue exists. |
| Ask references | Time ref seeks; representation ref switches view; note ref switches to Piano Roll and selects notes. | Related evidence intents are split into different ad-hoc mutations. Range references should be able to Focus; Show should remain explicit. |
| Ask suggested actions | Seek, loop, and show-representation are capability validated and user-triggered. | Preserve this separation. Do not make clicking a citation silently execute suggested actions. |

## Important correction to the first mockup hypothesis

The first design pass was too conservative about Score by hiding the playhead entirely.

Current `SheetMusic` already derives a playback measure from `measureStarts`, interpolates a cursor within that measure, and scrolls the measure into view. That blue playback cursor is useful **orientation**, not an evidence-confidence claim.

Therefore the production design should distinguish:

- **playback orientation:** may remain a blue cursor driven by Transport and available score timing/alignment;
- **evidence selection precision:** must remain measure-level / explicitly approximate when a performance-time span is projected onto notation without finer alignment evidence.

The static prototype uses a snapped coarse score cursor to make this distinction obvious, but production should preserve the useful existing playback cursor.

## Durable truth vs transient attention

### Durable truth — keep existing owners

**Transport**

- current playback source;
- current position;
- duration;
- loop bounds / enabled state.

**Workspace**

- active representation;
- `MusicalSelection`;
- Inspector mode;
- available representations/evidence.

Do not copy these into animation state.

### Missing transient state

A repeated click on the same finding should be able to re-orient the eye even when selection and position are unchanged. At the same time, manually dragging a selection should **not** trigger an evidence-jump flash.

Add the smallest possible ephemeral signal, conceptually:

```ts
type OrientationReason = "breakdown" | "ask-reference" | "show";

type OrientationRequest = {
  id: number;       // monotonically increasing nonce
  reason: OrientationReason;
};
```

The request intentionally does **not** duplicate a time range, representation, or source. The active components read the durable selection/transport state they already own and use the nonce only to replay a short attention treatment.

It may live in Workspace UI state or behind a small hook; it must never be persisted to the backend.

## Recommended user-intent primitives

### `focusPerformanceSpan(start, end, origin)`

Conceptual behavior:

1. validate `end > start`;
2. seek Transport to `start`;
3. set exact performance-time `MusicalSelection`;
4. preserve playback source;
5. preserve active representation;
6. issue `OrientationRequest("breakdown" | "ask-reference")`.

For Breakdown findings derived directly from measured evidence windows/spans, the selection should normally be:

```ts
{
  timeRange: { start, end, domain: "performance" },
  provenance: {
    origin: /* inspector/evidence origin if type is extended */,
    timeExact: true,
    measureApproximate: false,
  },
}
```

The *cross-domain Score projection* is approximate; the source performance range itself is not.

### `showRepresentation(representationId)`

1. require representation availability;
2. preserve Transport source/position;
3. preserve selection;
4. change active representation;
5. issue `OrientationRequest("show")` after/in the same state transition.

Do not seek again unless the user also invoked Focus.

### Ask time reference

Ask references already distinguish a point/range:

```ts
{ type: "time", start, end?, domain }
```

Therefore:

- range reference in performance domain → Focus the supported range;
- point reference → seek only + brief playhead orientation;
- notation-domain reference → use score/measure mapping rules, do not relabel it as exact performance time.

A citation click should still **not** enable Loop or switch playback source.

## Representation response to an orientation request

### Waveform

Reuse the existing selection rectangle. On request nonce change, temporarily raise its contrast/outline for ~300–600ms. No new overlay geometry is needed.

### Piano Roll

Reuse the existing time selection. Do not add note-level evidence glow unless support note IDs exist. The current generic behavior of including all notes overlapping the selected range is useful for selection but is not evidence provenance.

### Spectrogram

Reuse the same performance-time selection grammar as Waveform.

### Score

- keep current blue playback cursor;
- derive selected measures using existing performance→measure mapping;
- keep approximate projected selection visibly different (the existing dashed treatment is appropriate);
- on orientation request, briefly strengthen the real measure highlight rather than drawing a freeform second-based rectangle over notation;
- direct score/measure selections remain exact in notation domain.

## Where not to add new state

Do **not**:

- put animation flags into backend/domain models;
- add `focusedFindingId` as a second selection authority;
- store a copied playhead position in Workspace;
- change playback source as a side effect of Focus/Show;
- create per-representation “current evidence time” stores;
- use a timeout to clear the actual musical selection after the visual cue ends.

The cue ends; the user's selection remains.

## Minimal implementation order

### Slice 1 — semantic unification

- introduce a small shared Focus/orientation helper or hook;
- correct Breakdown Focus selection provenance;
- use it for Breakdown localized findings;
- add orientation nonce/state;
- make Waveform/Piano Roll/Score respond visually without changing their durable geometry semantics.

### Slice 2 — Ask references

- route range time references through Focus;
- keep point refs seek-only;
- preserve separate explicit Show/Loop actions;
- verify Ask capability/trust filtering remains intact.

### Slice 3 — representation consistency audit

- annotation clicks on Waveform/Piano Roll/Spectrogram use the same Focus semantics when they identify a real span;
- Score annotation behavior remains notation-domain honest;
- repeated click on an already-selected finding replays orientation cue;
- view switching never resets Transport position/selection.

## Test contract

State tests should prove:

1. Focus changes `transport.position` + shared selection, not active source/representation.
2. Focus on the same range twice emits two orientation request IDs.
3. Show changes representation only and preserves source/position/selection.
4. Performance range selection maps to Score as approximate measure selection.
5. Score playback cursor remains independent from evidence-selection precision.
6. Ask performance range reference Focuses; point ref only seeks.
7. A capability-blocked reference/action performs no mutation.
8. Reduced-motion changes animation treatment, not orientation semantics.

Browser/visual tests should prove the resting destination state, not hard-code animation frame timing.

## Design consequence for future #405 work

This interaction grammar is a stronger source of future product identity than an unrelated ambient effect. If it works well, the eventual landing prototype can borrow its real visual semantics — shared blue time, one musical span across representations, evidence brackets/measure highlighting — rather than inventing a separate marketing-only visual language.
