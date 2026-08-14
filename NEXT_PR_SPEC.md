# Next PR Spec: Transkun Production Integration

**Objective:** Integrate Transkun as the `solo_piano` production transcription engine. Do not globally replace Basic Pitch.

## Routing
Use existing transcription engine seam/registry.

- `solo_piano` → Transkun
- `general` / `unknown` → Basic Pitch (existing path)
- **No new classifier** — if no trustworthy automatic instrument/genre classifier exists, do not invent one.

Introduce explicit transcription profile/capability:
```
auto          # retains existing general engine unless trustworthy solo-piano evidence exists
solo_piano    # explicitly uses Transkun
general       # explicitly uses Basic Pitch
```
Make routing deterministic.

## Provenance
Persist in artifact/job provenance:
- requested transcription profile
- selected engine
- engine version/configuration
- routing reason

## Production Behavior Comparison (MANDATORY)
Run `real-piano.m4a` through both engines, then full downstream pipeline:

```
audio → transcription → corrected/notation MIDI → grand-staff MusicXML → rendered score → analysis
```

Compare:
- raw note count
- isolated high-register notes
- pitch range
- short-note count (<150ms)
- polyphony
- notation tie count
- measures
- score systems
- accidental count
- analysis output
- transcription runtime

Visual evidence (mandatory, identical-viewport, side-by-side):
1. Basic Pitch piano roll
2. Transkun piano roll
3. Basic Pitch score
4. Transkun score

Synthesized playback for both transcription outputs.

## Regression Requirements (prove all)
- general/default transcription still uses Basic Pitch
- `solo_piano` explicitly uses Transkun
- artifacts retain correct parentage/provenance
- score playback works
- cursor follow works
- click-to-seek works
- Analysis completes
- delete/reload persistence works

Extend real-stack E2E using canonical piano fixture.

## Scope Guardrails
Do NOT change in this PR:
- quantization
- notation algorithms
- Analysis algorithms
- FE design
- genre classification

## Publish and STOP FOR REVIEW

## Broader Direction
Don't try to solve remaining bad sheet music with more home-grown cleanup yet. Run Transkun through existing score pipeline first — many Basic Pitch compensation heuristics may now be unnecessary/harmful.

Order:
1. Transkun production integration
2. Visual/audible audit of resulting score
3. Simplify downstream heuristics where OSS made them unnecessary
4. Then revisit analysis OSS

This follows the architectural direction: use empirical evaluation to replace bespoke compensation logic with stronger OSS components, keeping genre/instrument behavior behind explicit routing.