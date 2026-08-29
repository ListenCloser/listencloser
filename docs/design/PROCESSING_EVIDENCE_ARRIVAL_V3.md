# Processing / Evidence Arrival V3

**Status:** design prototype / implementation contract. This is a signed-in product-interaction lane derived from the product-first priorities in visual R&D PR #405. It does not choose a landing-page identity.

## Problem

Today the processing UI behaves too much like a generic job modal:

- a newly uploaded source is durably saved, then the UI stays behind a blocking operation layer while the full understand job runs;
- a saved Work with an active job waits for that job before hydrating the representations that may already be available;
- a numeric progress bar becomes the dominant object even though the user cares about *what they can use now*;
- disconnect/failure states can visually replace the workspace even when the original recording is still safe and playable.

This makes the product feel like “submit a task and wait” instead of a music workspace whose evidence becomes richer over time.

## Design thesis

> **Block only until the recording is safely in the workspace. After that, reveal real capabilities as they actually become available.**

The source recording is the durable object. Processing enriches it; processing is not the object itself.

## Truth rules

1. **Never show an artifact before it exists.** No fake notes, score pages, chords, sections, or findings while those outputs are still unavailable.
2. **Job progress is not artifact availability.** A percentage or lifecycle message may describe backend work; it must not imply that a specific representation is ready.
3. **The original source becomes usable as soon as it is durably saved and a signed URL can be loaded.** Do not wait for transcription/analysis merely to expose playback.
4. **Availability comes from the actual Work bundle / representation availability contract.** UI readiness derives from persisted artifacts/evidence, not local timers.
5. **Partial success is a valid workspace state.** Audio can be ready while score, analysis, or transcription is missing/failed.
6. **A processing failure must not erase completed outputs.** Preserve and expose everything that is already durable.
7. **Reconnect is about observing the job, not recovering the user’s recording.** If source audio is saved, say so.

## Interaction phases

### Phase A — local file chosen / uploading

This is the one phase that may remain blocking because the Work/source is not yet guaranteed durable.

Show:

- filename;
- upload state;
- byte/upload progress if it is real;
- cancel/dismiss only if the upload contract safely supports it.

Do not show:

- transcription progress;
- notes/chords/score placeholders that look like computed results;
- fake multi-stage completion percentages.

Transition condition:

> upload API returns the durable source artifact/version and Work ID.

### Phase B — source saved / workspace opens

Immediately transition into the real Work.

Required visible state:

- Library contains/selects the new Work;
- Waveform tab becomes available as soon as its signed source can load;
- original playback source is available;
- Transport is usable;
- processing status becomes **non-blocking**.

Recommended copy:

- `Recording saved`
- `Understanding audio…`

The first line communicates durability; the second communicates enrichment still in progress.

### Phase C — evidence arrives

As durable outputs become available, they join the workspace naturally.

Examples:

- transcription artifact + note entities → Piano Roll becomes available;
- rendered transcription audio → corresponding playback source becomes available;
- MusicXML / rendered score + alignment metadata → Score becomes available;
- exposed insights → Breakdown gains context/findings;
- spectrogram remains available from source audio without pretending it is an analysis result.

A representation may appear without stealing focus. Do **not** switch the user away from what they are currently viewing when a new tab becomes available.

### Phase D — processing completes

Completion is intentionally quiet.

- status changes to `Understanding complete` briefly or disappears;
- newly available tabs remain where they appeared;
- do not show a celebratory modal;
- do not reset playback position or active representation;
- do not auto-open Breakdown.

### Phase E — processing fails

If source audio exists:

- keep the Work open;
- keep all completed representations/evidence usable;
- show a compact persistent/retryable failure notice;
- name what failed at the workflow level without claiming all outputs are lost;
- offer `Retry` when supported.

Recommended hierarchy:

**Couldn’t finish understanding this recording**  
`Your recording is saved. Available views still work.`  
`Retry`

If workflow creation failed *after* upload:

- keep the source Work open;
- expose `Process saved audio` as the primary recovery action.

### Phase F — observation disconnected

If the frontend lost job observation but the source is durable:

**Processing status interrupted**  
`Your recording is saved. Reconnect to check the current processing state.`

Actions:

- `Reconnect`;
- continue listening/browsing available representations.

Do not display language that implies the recording itself is disconnected or lost.

## Visual hierarchy

### 1. Music remains the largest object

Once Phase B begins, the Canvas must regain visual dominance. Processing status should not cover Waveform/Piano Roll/Score.

### 2. Use a compact availability/status surface

Preferred location:

- small status row beneath the representation tab strip **or**
- compact workspace notice anchored above Canvas/Inspector;
- on mobile, a compact inline status block, not a full-screen overlay.

Content should be short:

- durable state (`Recording saved`);
- current workflow state (`Understanding audio…`);
- recovery action when needed.

### 3. Artifact availability is shown by the real UI

The strongest readiness signal is not a checklist — it is that the actual tab/action appears and works.

Do not duplicate every capability into a permanent “pipeline dashboard.” A small disclosure may summarize progress for users who want detail, but the default workspace stays focused on music.

### 4. If detailed progress is shown, make it factual

A disclosure can list **available now** versus **still processing**, but only from known state.

Example:

```text
Understanding audio…
Available now
✓ Original recording
✓ Piano Roll
Working
  More analysis may appear as processing completes
```

Avoid claiming ordered stages such as `Harmony 62%` unless the backend exposes a real stable contract for that exact stage.

## Percent progress policy

The current understand workflow exposes numeric progress. It may remain useful in secondary detail, but should not be the primary visual promise after the source is saved.

Rules:

- upload progress may be primary while uploading;
- understand-job percentage should be secondary/muted;
- do not derive artifact readiness thresholds from percentage;
- do not animate “evidence arriving” merely because progress crossed a number;
- if backend progress semantics are too coarse/unstable, omit the percentage rather than overstate precision.

## Current implementation audit

### `handleFile`

Current sequence is effectively:

```text
upload source
→ start understand job
→ wait for terminal job
→ refresh works
→ select/open Work
```

Design target:

```text
upload source
→ select/open durable Work immediately
→ start/observe understand job without blocking Canvas
→ refresh/hydrate Work as durable outputs appear
```

The exact engineering mechanism may vary, but the source Work should not remain hidden solely because enrichment is running.

### `loadWork`

Current active-job path waits for the active job before building representation state from the bundle.

Design target:

1. authorize/fetch Work bundle;
2. hydrate all artifacts already present **immediately**;
3. if an active job exists, observe it in parallel;
4. refresh the Work bundle on meaningful job changes/completion (or a safe cadence/event mechanism);
5. merge newly durable outputs into Workspace without resetting current source/position/representation.

### Existing progressive hydration worth preserving

Once `loadWork` reaches representation construction, it already has a useful pattern:

- playable original audio is installed first;
- then entities, insights, and MusicXML hydrate in parallel;
- partial failures become warnings instead of destroying the whole Work.

That is the correct product direction. The main design change is to move this behavior **before** waiting for a running workflow.

## State model

Do not add a second product model for processing.

Use existing facts:

- Work/source artifact existence;
- current Work bundle artifacts/versions;
- Workflow/Job lifecycle;
- representation availability derived from those artifacts;
- analysis state derived from available insights + job state.

Conceptually expose a view model such as:

```ts
type ProcessingPresentation = {
  sourceDurable: boolean;
  jobState: "none" | "queued" | "running" | "disconnected" | "failed" | "cancelled" | "succeeded";
  message: string | null;
  progress: number | null;
  availableRepresentations: RepresentationId[];
  canRetry: boolean;
  canReconnect: boolean;
};
```

This is presentation derivation, not new persisted truth.

## Capability arrival behavior

When a new representation becomes available during the session:

- add the tab without switching to it;
- preserve current representation;
- preserve Transport source/position;
- optionally give the *new tab label* one subtle one-shot availability cue;
- never pulse the entire Canvas;
- no toast is needed unless the output is otherwise hard to discover.

When Breakdown gains its first localized finding:

- do not force-open Inspector;
- if Inspector is already open, content can update in place;
- a tiny one-shot count/update cue is acceptable if it does not compete with playback.

## Motion rules

User-triggered / state-causal only.

Good:

- upload card collapses into/open Work once durability is confirmed;
- new tab fades/slides in 100–180ms;
- status copy cross-fades on real job-state change;
- reduced-motion shows state changes instantly.

Avoid:

- fake particles assembling notes;
- waveform morphing into MIDI before MIDI exists;
- indefinite shimmer around unavailable tabs;
- perpetual “AI thinking” gradients;
- stage-completion confetti;
- repeated bouncing badges.

## Mobile

After source durability:

- do not occupy the screen with a blocking processing sheet;
- keep Transport and active representation usable;
- status should fit as a compact two-line surface with one recovery action;
- detailed job info can be a disclosure.

## Accessibility

- job updates use a polite status region; do not re-announce every percent tick;
- errors/disconnects can use alert semantics once per meaningful state transition;
- newly available tabs must remain keyboard reachable in normal tab order;
- progress values need accessible names if retained;
- reduced-motion must not remove readiness information.

## Acceptance scenarios

| Scenario | Expected experience |
|---|---|
| Fresh upload, source not durable yet | blocking upload state is acceptable |
| Upload returns durable Work | workspace opens immediately; source playback becomes primary goal |
| Understand job running, only source exists | Waveform/Transport usable; compact non-blocking status |
| MIDI appears while user listens to Waveform | Piano Roll tab appears; Waveform remains active; playback source/position unchanged |
| Score appears later | Score tab appears without stealing focus |
| Insights appear | Breakdown updates if open; no forced Inspector opening |
| Job succeeds | status quietly completes/disappears; no workspace reset |
| Job fails after MIDI exists | source + Piano Roll remain usable; retry notice is non-blocking |
| Job observation disconnects | available workspace remains usable; Reconnect checks job state |
| Workflow creation fails after upload | source Work remains open; `Process saved audio` recovery is available |
| Reopen Work with active job | already-durable outputs render before waiting for the job |

## Prototype requirement

The accompanying prototype must include at least these switchable states:

1. uploading source;
2. source saved / understanding running;
3. transcription available while job still running;
4. more evidence available;
5. disconnected but source usable;
6. failed but partial outputs preserved;
7. complete.

The prototype should show the same workspace becoming richer; it must not swap through unrelated full-screen loading scenes.

## Browser acceptance for an implementation PR

- desktop 1440×900;
- 1024×768;
- mobile 390×844;
- reduced motion;
- source playback during running job;
- representation arrival without active-view/source reset;
- partial failure preserving available output;
- reconnect path;
- active job on saved Work hydrates existing artifacts before terminal state.

## Relationship to other design work

- #405 remains the visual/identity R&D SOT.
- #433 defines evidence-jump/shared-time coherence.
- This document covers **truthful capability arrival** only.
- It intentionally avoids choosing a new landing hero, logo, pipeline visualization, or analysis taxonomy.

## Follow-on

After this behavior is validated:

1. implement non-blocking source-saved processing flow;
2. test artifact arrival with the real stack;
3. design upload → waveform object continuity as a small transition on top of the truthful state model;
4. only then consider more expressive processing visuals that are driven by real intermediate data.
