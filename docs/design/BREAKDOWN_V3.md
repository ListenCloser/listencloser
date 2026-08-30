# Breakdown V3 — Evidence-grounded music understanding

> **Status:** Product / UX design for #340. Design and validation first; no detector, schema, or production-capability changes in this document.
>
> **Builds on:** UX V3 #328, Evidence Graph V3 #336, Analysis V3 #327, audio-language evaluation #339, `DESIGN.md`, and the current Library / Canvas / Inspector / Transport workspace.

---

## 1. Product decision

The primary Inspector experience should evolve from **analysis categories** into a **Breakdown of the current musical context**.

The user should not need to know which MIR subsystem produced a result. The default object is a localized, evidence-backed musical relationship that answers one of a few human questions:

- What is happening here?
- What changed?
- What is repeating or related?
- What is driving what I hear?
- Why might this matter musically?
- Where can I hear something similar?

The interaction loop is:

```text
ARRIVE AT / SELECT A PASSAGE
        ↓
HEAR
play · loop · source A/B · isolate when available
        ↓
SEE
synchronized representation + focused evidence
        ↓
UNDERSTAND
ranked relationship / change / repetition / organization
        ↓
LEARN
plain-language interpretation with framework/scope when needed
        ↓
FOLLOW UP
show evidence · compare · find similar · Ask
```

The current product shell remains stable:

```text
Library | Canvas | Breakdown/Ask Inspector | Transport
```

This is deliberately not another workspace redesign.

---

## 2. Design read

**Mode:** Operate.

The product is a focused music inspection desk: compact, predictable, canvas-first, and evidence-led. It should feel closer to a creative/editor tool than a dashboard or chatbot.

Design dials for this surface:

| Dial | Setting | Reason |
|---|---:|---|
| Density | 7/10 | Serious listening/analysis needs compact information without dashboard cards. |
| Motion | 2/10 | Motion should preserve context when focusing a span or opening detail; playback itself already supplies movement. |
| Visual variance | 4/10 | Findings need hierarchy, but the canvas and transport remain the dominant stable geometry. |

Do not solve product ambiguity with more panels, badges, tabs, or decorative cards.

---

## 3. Reference-to-decision matrix

References are inputs to judgment, not visual authorities. We synthesize patterns into the existing `DESIGN.md` system.

| Reference | What we take | What we explicitly do **not** take |
|---|---|---|
| **Mobbin** | Shipped-product interaction patterns: docked inspectors, selection context, bottom sheets, overflow actions, progressive disclosure, stable editor/navigation geometry. Use multiple examples to identify recurring patterns before designing a component. | Copying a single app screen or importing an unrelated aesthetic. Mobbin is evidence that a pattern works, not a theme. |
| **21st.dev** | Searchable component ideas for disclosure, compact action rows, tabs, tooltips, sheets, timelines, and responsive controls. Components are structural cues; any adopted primitive must be restyled to local tokens and accessibility requirements. | Pasting visually flashy community components into the product, importing gradients/glass/marketing motion, or allowing component choice to determine information architecture. |
| **Impeccable** | Treat this as an **Operate** surface: stable navigation, density, readable state, quiet motion. Keep `DESIGN.md`/product context as agent-readable constraints. | Generic AI defaults such as purple gradients, glassmorphism, card grids, oversized headings, or marketing-page composition. |
| **Taste Skill / redesign protocol** | Audit the existing interface before replacing it. Preserve working URLs/state/interactions, identify generic patterns, declare the redesign mode, and run a hard pre-flight check before shipping. | Greenfield rewrite behavior. Breakdown must reuse the existing workspace/selection/transport architecture. |
| **Emil Kowalski design-engineering guidance** | Motion must have a purpose; use it mainly to explain focus/context changes. Favor predictable controls, generous hit targets, fast feedback, and restraint. Prototype genuinely different interaction variants when a component decision is uncertain. | Animation as polish by default, hover-scale effects, long ornamental transitions, or continuously animated analysis during playback. |
| **Hooktheory TheoryTab** | Synchronized playback + explanation, relative/key-aware theory where justified, and section/local navigation. | Assuming notation/classical tonal theory is universally valuable. |
| **Moises** | Treat analysis as an action surface: loop, isolate, compare, hear the claim. | Making stems/chords permanent dashboard categories for every piece. |
| **Sonic Visualiser** | Time-aligned evidence layers and inspectable annotations. | Exposing expert visualization density as the beginner default. |
| **Cyanite / commercial music intelligence** | Segment-level context/similarity and free-text retrieval are useful product primitives. | Reducing the product to whole-track tagging, mood labels, or opaque catalog scores. |

### Practical agent rule

When implementing a Breakdown component:

1. identify the user task and evidence requirement first;
2. inspect existing local primitives and `DESIGN.md`;
3. use Mobbin / comparable shipped products to confirm interaction patterns;
4. optionally use 21st.dev to find a component implementation pattern;
5. adapt the pattern to local tokens and state semantics;
6. run audit / accessibility / viewport / state checks before merge.

This order prevents reference libraries from turning into a collage.

---

## 4. Current Inspector problem

The current Inspector has already improved substantially: it is docked, selection-aware, confidence-gated, time-linked, and Ask can act on references. Those behaviors must be preserved.

The remaining product limitation is hierarchy:

```text
Overview
Notable moments
Supporting evidence
  Harmony
  Rhythm
  Melody
```

This still implies that the user should understand and browse analysis categories. It also makes future layers — stems, timbre, sections, similarity, context, production, semantic hypotheses — either another disclosure group or another taxonomy problem.

Breakdown V3 changes the hierarchy to:

```text
Current scope
What stands out
  Finding 1
  Finding 2
  Finding 3
Explore / ask questions that are actually supported
Evidence details on demand
```

Domain labels become **secondary lenses**, not top-level navigation.

---

## 5. Core object: Breakdown Finding

A Breakdown Finding is a presentation object assembled from Evidence Graph-compatible inputs. It does not require a new persistence table.

```typescript
type BreakdownFinding = {
  id: string
  scope: EvidenceLocator | "whole_work"

  // Human-facing claim. Must be decomposable into evidence-backed clauses.
  headline: string
  explanation?: string

  // Evidence Graph refs: measured evidence, observations, relations, context.
  supportRefs: EvidenceRef[]
  contradictionRefs?: EvidenceRef[]

  trustClass:
    | "measured"
    | "calibrated_estimate"
    | "deterministic_derived"
    | "heuristic_candidate"
    | "context_estimate"
    | "semantic_hypothesis"

  maturity: "evaluation_only" | "experimental" | "production"
  verification?: "unverified" | "evidence_consistent" | "evidence_conflicted"

  primaryRepresentation?: "waveform" | "piano_roll" | "score" | "spectrogram" | "stems" | "timeline"
  availableActions: Array<"focus" | "loop" | "show" | "compare" | "isolate" | "similar" | "ask">
  lensHints?: Array<"pulse" | "pitch" | "layers" | "form" | "sound" | "relations" | "context">
}
```

A finding can be assembled client-side from current Insights initially. This contract is a UI adapter over existing evidence, not a demand for new schema.

---

## 6. Finding anatomy

### Default collapsed state

```text
0:42–0:56
The passage opens up as the texture becomes denser.
Drums enter · bass activity rises · high-frequency energy increases

[Loop] [Show] [Compare] [Ask]
```

Rules:

- one sentence headline;
- one compact evidence line, preferably 2–4 supports;
- time/span is interactive;
- no engine/model name in the default row;
- actions only appear when valid;
- a finding must have at least one direct action or strong explanatory value to be promoted.

### Expanded state

```text
Why this is shown

Drums enter                 detected at 0:43
Bass activity rises         +28% vs previous passage
Upper-spectrum energy       higher across this span

Interpretation
These changes coincide, which is why the section reads as a larger texture.

Evidence / alternatives
[show source details]
```

Expanded detail may expose:

- evidence references;
- confidence only when calibrated;
- neutral scores with their actual names;
- experimental maturity;
- alternative/conflicting observations;
- engine/model/checkpoint/provenance in a second disclosure level.

---

## 7. Breakdown summary behavior

### Whole-work scope

Show **at most 3–5** promoted findings.

Useful finding families include:

- largest section/texture change;
- strongest repeated/related passage;
- salient pulse/groove behavior;
- stable tonal/pitch organization when actually supported;
- meaningful layer entry/exit;
- unusual contrast or transition;
- one context statement only if it changes how the user can use/understand the piece.

Do not fill slots to create a balanced dashboard.

### Selection scope

A 10–20 second user selection should immediately outrank whole-work findings. The Inspector header shows the selected range and the Breakdown answers the selection first.

Preferred questions become:

- What changed in this selection?
- What is driving the sound here?
- What repeats inside or around this passage?
- How is this different from the previous/next section?
- What is happening with pitch/harmony here? — only when supported.

### Playhead-only scope

When no explicit selection exists, the playhead may softly focus the containing section/passage, but it should **not** constantly reorder the entire Inspector every frame. Re-rank only when the active structural region changes or the user explicitly asks for "here".

---

## 8. Ranking and promotion policy

There is no ML requirement for V1. Use a deterministic policy whose components are inspectable.

### 8.1 Hard eligibility gates

A candidate is not promotable if:

- required evidence is missing;
- its capability is not exposed at the appropriate maturity;
- it relies on a semantic hypothesis that is `evidence_conflicted`;
- its localized span cannot be resolved well enough for the promised action;
- its claim would require presenting an uncalibrated score as confidence;
- the user cannot hear, see, compare, or meaningfully learn anything from it.

### 8.2 Conceptual ranking

```text
promotion =
  scope_relevance
× musical_salience
× evidence_maturity
× evidence_breadth
× actionability
× novelty
- redundancy_penalty
- uncertainty_penalty
```

Do not expose the numeric score to users.

Suggested discrete policy for the first implementation:

1. selection-overlapping findings first;
2. direct measured/deterministic relationships before context estimates;
3. findings supported by multiple independent evidence types before single weak signals;
4. relational/change findings before static metadata;
5. findings with Loop / Show / Compare actions before prose-only observations;
6. suppress near-duplicates from the same span;
7. cap context/style findings to avoid label soup;
8. semantic hypotheses cannot displace stronger factual findings merely because the prose is fluent.

### 8.3 "Interesting" is not a trust class

Musical salience may be heuristic, but factual support must still obey trust semantics. A very interesting weak hypothesis should be clearly presented as interpretation, not promoted as a detected fact.

---

## 9. Trust presentation

The default UI should communicate trust primarily through wording and disclosure, not badge spam.

### Production measured / calibrated / deterministic

Default appearance: normal finding.

Example copy:

> The drum pattern becomes denser after 0:43.

No `AI` or `High confidence` badge is necessary.

### Experimental capability

Use one restrained state label near the supporting detail, not the headline.

> **Experimental** · Instrument labels are model-estimated.

### Context estimate

Phrase as context, not fact:

> The texture is most consistent with an electronic/dance production profile in this passage.

Expose ranked alternatives on demand.

### Semantic hypothesis

Never visually merge it with measured evidence.

Evidence-consistent example:

> **Interpretation**
> This may feel like a lift because several measured changes happen together: drums enter, the register rises, and the spectrum brightens.

Unverified example:

> **Possible interpretation**
> The model suggests this passage functions like a transition, but there is not enough structured evidence to verify that yet.

Evidence-conflicted example:

> **Conflicting interpretation**
> A semantic model described this as a drop, but the measured layer/activity evidence does not support that reading. It is not shown as a main finding.

### Unavailable / withheld

Do not render empty category panels.

If the user explicitly asks for an unavailable capability:

> I can’t make a reliable instrumentation claim for this recording yet.

or

> There isn’t enough stable evidence in this passage to make that comparison.

---

## 10. Actions are part of the finding

Every promoted finding should advertise only actions it can actually fulfill.

### Focus

Clicking time/headline:

- sets the shared selection;
- seeks to the start if useful;
- synchronizes canvas highlight;
- retains the current playback source unless the user chooses otherwise.

### Loop

One-click loop of the exact evidence span using the global Transport.

### Show

Choose the most useful existing representation for the claim:

| Claim | Preferred view |
|---|---|
| note / contour / harmonic event | Piano roll or Score, depending evidence maturity |
| beat / groove / transient timing | Waveform + beat/grid overlay |
| timbre / spectral change | Spectrogram |
| layer entry/exit | Stem/timeline view when available; waveform otherwise |
| repeated section / similarity | Timeline / compare selection |
| score-specific theory | Score |

`Show` changes what the user sees; it does not silently change what they hear.

### Compare

For relational findings, populate Compare with source span A and related span B while preserving global transport semantics.

### Isolate

Only when an actual stem artifact exists. Never display a disabled fake stem action to advertise future capability.

### Ask

Ask opens with the finding/span and support refs already in context.

---

## 11. Question affordances instead of permanent lenses

Under the top findings, show a small set of questions dynamically selected from evidence availability.

Examples:

```text
Explore
What changed here?
What is repeating?
What is driving the groove?
What is happening with the harmony?
Where does this happen again?
```

Rules:

- 2–4 prompts maximum;
- do not show a prompt if current evidence cannot support a useful answer;
- lens words may appear in prompt copy, but there are no permanent Pulse/Pitch/Layers/Form tabs by default;
- prompt result should reuse the same BreakdownFinding presentation rather than open a separate dashboard.

---

## 12. Five required prototype states

### A. Solo/acoustic pitched

Evidence available:

- score/piano-roll alignment;
- note/chord/key evidence;
- expressive timing;
- phrase/register observations.

Promoted example:

> The melody reaches its highest register while the accompaniment thins out.

Actions: Loop · Show score · Show piano roll · Ask.

Avoid: forcing production/stem cards.

### B. Dense produced work

Evidence available/prototyped:

- waveform/spectrum;
- section boundaries;
- stem references;
- context/instrument estimates;
- energy/layer observations.

Promoted example:

> This section gets larger because drums enter, bass activity rises, and the upper spectrum fills out.

Actions: Loop · Show waveform · Isolate drums · Compare previous section.

Avoid: making Score the default representation.

### C. Rhythm-first work

Evidence available:

- beat/downbeat grid;
- onset/activity evidence;
- repeated groove relation;
- optional drum stem.

Promoted example:

> The groove stays stable across this transition even though the other layers change.

Actions: Loop · Show beat grid · Compare · Ask.

Avoid: inventing a harmonic narrative because the UI has a Harmony area.

### D. Ambiguous / low-confidence work

Few capabilities pass eligibility gates.

UI:

```text
Breakdown
There is not enough stable evidence for a strong musical summary yet.

Available
• A steady pulse is detected near 102 BPM.
• Two passages have similar overall texture, but the match is experimental.

[Ask about what is available]
```

The sparse state is a success condition, not an empty dashboard failure.

### E. User-selected 10–20s passage

Inspector scope becomes explicit:

```text
Selected · 0:42–0:56      ×

What changed here
The texture opens up immediately after the selection begins.
...

Compare with 0:18–0:31
[Loop] [Compare] [Ask why]
```

Clearing the selection returns to whole-work Breakdown without resetting playback.

---

## 13. Wireframes

### Desktop

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Music Lab / active piece                                                        account │
├──────────────┬───────────────────────────────────────────────────┬──────────────────────┤
│ Library      │ Waveform  Piano roll  Score  Spectrogram          │ Breakdown    Ask      │
│              ├───────────────────────────────────────────────────┤──────────────────────┤
│ recording A  │                                                   │ Selected 0:42–0:56 ×  │
│ recording B  │                 MUSIC CANVAS                      │                      │
│              │                                                   │ WHAT CHANGED          │
│ + Import     │           focused evidence highlight              │ Texture opens up      │
│              │                                                   │ drums · bass · highs  │
│              │                                                   │ Loop Show Compare Ask │
│              │                                                   │                      │
│              │                                                   │ ALSO HERE             │
│              │                                                   │ Groove stays stable…  │
│              │                                                   │                      │
│              │                                                   │ EXPLORE               │
│              │                                                   │ What is repeating?    │
├──────────────┴───────────────────────────────────────────────────┴──────────────────────┤
│ Listening to Original   Play   Loop       scrub / selection          time      Compare │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Narrow laptop

Inspector remains ~300px; Library may collapse according to existing UX V3 rules. Finding actions wrap onto a second compact row before the canvas is compressed below usability.

### Mobile

```text
┌──────────────────────────────┐
│ active piece          ☰  ◇  │
├──────────────────────────────┤
│ Wave  Piano  Score  More     │
├──────────────────────────────┤
│                              │
│       MUSIC CANVAS           │
│       selected region        │
│                              │
├──────────────────────────────┤
│ Original     ▶      0:48     │
└──────────────────────────────┘

Analysis button → bottom sheet:
┌──────────────────────────────┐
│ Breakdown              Ask   │
│ Selected 0:42–0:56       ×  │
│                              │
│ Texture opens up…            │
│ drums · bass · highs         │
│ Loop  Show  Compare  Ask     │
│                              │
│ What is repeating?           │
└──────────────────────────────┘
```

Do not shrink the desktop three-column layout onto mobile.

---

## 14. Interaction states

### Finding focused

- finding row gets restrained accent/surface state;
- canvas highlight becomes the strongest analysis highlight after the playhead/selection hierarchy;
- transport loop state changes only if user presses Loop;
- no auto-play.

### Finding expanded

- use inline disclosure, not modal;
- evidence detail pushes subsequent findings down;
- 160–200ms height/opacity transition only if it remains stable and respects reduced motion.

### Ask from finding

- switch Inspector mode to Ask;
- preserve scope/finding context;
- prefill contextual chips/reference state, not necessarily the text box;
- answer references resolve back to the same canvas/selection actions already used by Breakdown.

### Compare from finding

- transport becomes the authoritative Compare controller;
- Inspector explains A/B relation;
- canvas visualizes the currently relevant representation(s);
- exiting Compare preserves the active selection when possible.

---

## 15. Evidence prerequisite map

| UI element | Minimum prerequisite | Current / V3 |
|---|---|---|
| selection scope chip | shared workspace selection | current |
| time-linked finding | Insight/entity span resolvable to performance time | current |
| Loop | valid time span + playable active source | current |
| Show score/piano roll | representation exists + alignment usable | current |
| Ask about finding | Ask configured + support refs/context | current, richer with #336 |
| compare previous/related passage | two resolvable spans + relation or deterministic pairing | partial/current Compare; relation V3 |
| beat/groove finding | evaluated pulse evidence | V3 candidate (#335) |
| isolate stem | actual stem artifact version | V3 research (#334) |
| style/instrument context | evaluated ContextEvidence | V3 research (#333) |
| similar passage | evaluated EmbeddingReference/relation | V3 research (#332) |
| semantic interpretation | SemanticHypothesis + verification/support contract | evaluation only (#339) |

Prototype-only controls for V3 research capabilities must be visually marked as prototype states and must not be shipped as active production affordances before capability promotion.

---

## 16. Implementation sequence for #328

Keep implementation PRs bounded and independently revertible.

### PR A — Breakdown adapter + ranking, no new capability

- rename Inspector primary mode from `Analysis` to `Breakdown` in UI copy;
- add a client-side `deriveBreakdownFindings()` adapter over currently exposed Insights/findings;
- rank/suppress duplicates using deterministic policy;
- render 3–5 relationship-first findings;
- keep current supporting evidence as expanded detail;
- preserve existing selection/seek behavior;
- add focused tests for confidence/maturity withholding.

No new backend/API/schema work.

### PR B — finding actions and representation focus

- standardized Loop / Show / Ask actions;
- relational Compare only where current data can resolve two spans;
- useful-representation selection policy;
- preserve Representation != playback source;
- browser tests for selection → Loop/Show/Ask/Compare transitions.

### PR C — question affordances + responsive polish

- dynamic evidence-supported prompts;
- selection-specific prompts;
- mobile Breakdown sheet refinement;
- expanded evidence/provenance disclosure;
- Argos snapshots for five designed states using deterministic fixture/mock data.

### Later capability PRs

Add stems, similarity, context, semantic hypotheses only after their Analysis V3 promotion gates. Do not bundle those candidates into the initial Breakdown implementation.

---

## 17. Browser acceptance matrix

Every implementation slice must test real behavior, not only static mockups.

| Scenario | 1440×900 | 1024×768 | 390×844 | Required checks |
|---|---:|---:|---:|---|
| solo/acoustic pitched | ✓ | ✓ | ✓ | finding → selection → score/piano roll → loop |
| dense produced fixture/mock evidence | ✓ | ✓ | ✓ | no forced score; layer/sound finding hierarchy |
| rhythm-first fixture/mock evidence | ✓ | ✓ | ✓ | pulse/groove finding; beat/grid representation when available |
| low-confidence | ✓ | ✓ | ✓ | unavailable findings withheld; no empty categories |
| 10–20s selection | ✓ | ✓ | ✓ | scope chip; selection-ranked findings; clear restores whole-work view |
| Ask from finding | ✓ | ✓ | ✓ | support refs retained and navigable |
| Compare relational finding | ✓ | ✓ | optional | A/B transport remains source authority |

Also assert:

- no horizontal page overflow;
- 40px minimum primary action targets on touch;
- keyboard focus order follows finding → actions → evidence disclosure;
- status/trust is not encoded only by color;
- reduced-motion mode retains all context changes without animation dependence.

---

## 18. Design pre-flight gate

Do not merge Breakdown implementation if any answer is **yes**:

- Does the Inspector still require browsing Harmony/Melody/Rhythm/Structure to understand the piece?
- Are empty categories rendered to maintain a dashboard grid?
- Is model/engine provenance visually louder than the musical claim?
- Can a semantic hypothesis look identical to a measured fact?
- Does `Show` silently switch playback source?
- Does selecting a finding auto-play unexpectedly?
- Are future stem/similarity/context capabilities presented as if they already exist?
- Does mobile compress desktop columns instead of using the existing sheet model?
- Are generic cards/pills/gradients being added because a reference component looked attractive?
- Is animation present without a context-preserving purpose?
- Can a finding be promoted with no useful action and no meaningful explanation?

Do not merge if any answer is **no**:

- Can the user hear the finding?
- Can the user see its span/support when relevant?
- Can the user tell when a statement is tentative or interpretive?
- Does the strongest current selection outrank unrelated whole-work metadata?
- Does clearing selection preserve playback/context appropriately?
- Can an implementation agent trace every prototype control to a current or gated prerequisite?

---

## 19. Success criterion

A person unfamiliar with MIR terminology should be able to choose or hear a passage and answer:

1. **What is happening here?**
2. **What changed or repeats?**
3. **Can I hear the claim directly?**
4. **Can I see why the product believes it?**
5. **Can I compare it to the related passage?**
6. **Can I ask a useful follow-up without losing context?**
7. **Can I distinguish detected evidence from interpretation when it matters?**

If the UI instead teaches the user listencloser's detector taxonomy, Breakdown V3 has failed.
