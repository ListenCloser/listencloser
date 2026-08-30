# Product learning + contextual reasoning contract

Status: product interaction extension over the existing Analysis V3 / Evidence Graph / Breakdown architecture.

Authority remains with `MASTER_SPEC.md`, #458, `EVIDENCE_GRAPH_V3.md`, #460, and #461. This document narrows two additive product directions that emerged from computational-musicology / music-pedagogy review without creating a parallel analysis architecture:

1. **within-Work contextual reasoning** — make measurements meaningful relative to the music around them;
2. **optional learning interactions** — let users actively hear and discover why a grounded finding matters, without forcing pedagogy on people who only want immediate insights.

Tracking issues: #548 and #547.

---

## 1. Product default: insight first

The default listencloser experience remains fast and editorial:

```text
open Work
→ useful grounded findings appear
→ focus / hear / compare / inspect evidence
→ Ask when useful
```

A user should not have to complete a tutorial, answer a question, reveal a hint, or enter a special educational mode before seeing the analysis.

The product should work well for at least three intents:

- **just tell me what is interesting** — immediate concise findings;
- **help me understand why** — explanation + inspectable evidence;
- **teach me through this music** — optional interactive learning path.

These are presentation depths over the same evidence and relations, not different analysis pipelines.

### Non-goals

Do not introduce by default:

- a permanent Education tab;
- course/chapter navigation;
- quizzes gating analysis;
- scores, XP, streaks, badges, or gamification;
- a learner model or persistent curriculum state;
- a second claim/evidence store for teaching.

Those should require later user evidence, not architectural enthusiasm.

---

## 2. The product object remains a grounded musical finding

The reusable pipeline remains:

```text
promoted evidence
      ↓
validated relation / observation
      ↓
claim-specific sufficiency gate
      ↓
grounded finding
      ↓
Breakdown / Compare / Ask / optional Learn
```

Learn mode must consume the exact same grounded finding and support references that ordinary Breakdown consumes.

Teaching changes **how the user encounters a valid finding**. It must never strengthen the truth status of that finding.

Example:

```text
Grounded finding
  “Median RMS amplitude is 28% higher in B than A.”

Default
  show the finding immediately

Learn
  hear A
  hear B
  ask “Which passage sounds stronger?”
  show the relevant evidence
  reveal the same grounded finding
```

The prompt is pedagogical. The evidence and relation are unchanged.

---

## 3. Contextual reasoning: prefer relations over isolated numbers

Many absolute MIR measurements are technically correct but musically weak on their own.

```text
1.8 events / beat
spectral centroid = 2840 Hz
RMS = 0.14
```

A more useful analytical question is often:

> Relative to what?

The preferred progression is:

```text
absolute evidence
→ explicit A/B comparison
→ within-Work context
→ repeated-occurrence context
→ user-library context
→ named reference-corpus context
```

Only the first three should be near-term product assumptions.

### 3.1 Near-term reference populations

#548 owns the first implementation contract.

Useful reference populations include:

- **explicit comparison span** — user or validated relation selects A and B;
- **local context** — a bounded region before/after a selected passage;
- **rest of Work** — compatible complete evidence outside the selected span;
- **other occurrences** — only once recurrence/similarity evidence is validated.

This enables literal findings such as:

- “This passage has higher measured event density than most of the Work.”
- “RMS amplitude is lower here than in the surrounding 20 seconds.”
- “This occurrence has the highest low-band energy of the three linked returns.”

It does **not** automatically permit:

- “This is the most exciting part.”
- “This is the chorus.”
- “The producer intentionally creates tension here.”

Those require additional context, framework, or interpretation.

### 3.2 Avoid false universals

A within-Work percentile means only “relative to this Work.”

A future reference-corpus percentile must always identify the corpus and its scope. The product must not turn a convenience sample of Western pop, classical piano, or any other repertoire into an implied universal musical norm.

Prefer:

> “Unusual relative to the selected reference corpus.”

not:

> “Unusual in music.”

---

## 4. Representation adequacy is claim-specific

Waveform, audio, Piano Roll, Score, spectrogram, beat grid, stems, and future representations are **related views of the same Work, not interchangeable truth**.

For every product action that says `Show`, `Evidence`, `Compare`, or `Learn`, distinguish:

1. **authoritative evidence representation** — what supports the claim;
2. **useful presentation representation** — what helps the user perceive or understand it;
3. **known-lossy / inappropriate representations** — views that could mislead for this claim.

Examples:

### Performance timing

Claim: “The melody attack arrives late relative to the pulse.”

- authoritative: source-aligned onset + MetricGrid evidence;
- useful presentation: waveform, onset lane, Piano Roll if transcription is sufficiently accurate;
- potentially misleading: readable Score if its purpose is intentionally to normalize performance timing.

### Notated spelling

Claim: “This pitch is spelled as G-sharp rather than A-flat in the readable score.”

- authoritative: symbolic / score-interpretation evidence;
- useful presentation: Score;
- insufficient by itself: raw audio, which can support pitch class but not editorial spelling.

### Source entry

Claim: “The bass layer enters here.”

- authoritative: validated source/stem activity evidence;
- useful presentation: stem lane + original mixture playback;
- insufficient: possession of a bass stem artifact without validated activity evidence.

The UI does not need to display these categories as jargon. They are an action-selection rule.

---

## 5. Evidence disagreement can itself be informative

Current fail-closed behavior should remain the default when evidence is insufficient for a requested claim.

But when two evidence paths are individually valid and meaningfully disagree, the product should eventually be capable of representing that disagreement rather than silently choosing one.

Examples:

- audio chroma supports A7 while note transcription misses the seventh;
- performed onset is measurably late while readable Score normalizes it to the beat;
- source-aware evidence suggests a bass event that mixture transcription does not recover;
- two validated analytical frameworks support different interpretations of the same event.

This should not become a noisy “models disagree” dashboard. Only surface disagreement when it is musically or epistemically useful.

Conceptually useful relations include:

```text
AGREES_WITH
CONFLICTS_WITH
UNDERDETERMINED_BY
NORMALIZED_BY
```

No generic conflict relation should be implemented until a concrete product claim needs it and the compared evidence is actually commensurate.

---

## 6. Optional Learn interaction

#547 owns the bounded product implementation.

The first Learn experience should be a **transient presentation state over one already-working grounded finding**.

### 6.1 Recommended interaction sequence

Not every finding needs every step. The available sequence is:

```text
OBSERVE
  ↓
COMPARE (when a grounded comparison exists)
  ↓
PREDICT (optional)
  ↓
HINT (optional)
  ↓
REVEAL
  ↓
TRANSFER (when recurrence exists)
  ↓
EXPERIMENT (only when a real counterfactual exists)
```

#### Observe

Focus or loop the exact primary musical span. The user should first encounter the music, not a paragraph.

#### Compare

Use real A/B spans when the finding already has a comparison relation. Preserve shared musical time and make switching or looping inexpensive.

#### Predict

An optional prompt that asks the listener to notice something before revealing it.

Examples:

- “Which passage is more active?”
- “What changes in the low end?”
- “Does the second entrance happen earlier or later relative to the beat?”

A prediction prompt may only ask about distinctions supported by the underlying relation.

#### Hint

Reveal one real supporting representation/evidence family without giving away the final wording.

Examples:

- show the two evidence curves;
- highlight onset positions against the beat grid;
- highlight corresponding pitch contours.

Never fabricate a clue.

#### Reveal

Show the ordinary grounded finding. `Reveal` must not invoke a looser model that adds unsupported factual content.

#### Transfer

Once recurrence/similarity is trustworthy:

> “Can you find another occurrence where this changes?”

This is pedagogically valuable because the user applies the concept to another real passage rather than merely reading an explanation.

#### Experiment

Longer-term: let the user hear a validated counterfactual.

Examples:

- original timing vs snapped-to-grid timing;
- original vs isolated/muted validated source;
- original contour vs transposed recurrence;
- performance notes vs readable-score normalization.

A counterfactual must be an explicitly derived alternate artifact/rendering. Do not synthesize fake evidence solely to make a teaching interaction look complete.

---

## 7. Explanation depth should eventually be user-controlled, not user-classified

Avoid requiring the system to decide that someone is a “beginner” or “advanced musician.”

A better future interaction is user-selected explanation depth, for example:

```text
Quick
Student
Advanced
Evidence
```

These change wording and disclosure depth, not underlying facts.

Possible behavior:

### Quick

One concise finding and immediate musical action.

### Student

Explain one relevant concept in plain language and connect it to the heard passage.

### Advanced

Allow technical terminology, framework assumptions, alternate readings, and more detailed measurements.

### Evidence

Expose exact support refs, spans, provenance, units, engine/version, maturity, and applicability.

Do not implement this preference system until the first Learn path proves useful.

---

## 8. Editorial salience: teach the interesting relationship, not the detector catalog

Learning interactions should inherit Breakdown’s editorial ranking rather than creating lessons for every available descriptor.

Good candidates are findings with one or more of:

- a large contextual change;
- repetition with transformation;
- contrast between linked passages;
- multiple evidence dimensions changing together;
- a structurally salient position;
- a clear relation that can be demonstrated by listening;
- strong explanatory leverage — one relationship explains several audible observations.

Bad candidates are merely available measurements.

Do not produce a Learn action for every key, BPM, centroid, chord, or density result just because the data exists.

---

## 9. Sequencing / parallel-agent contract

This extension deliberately sits behind the active M2/M3 vertical slice.

### Current active contracts

- #529: grounded relation → product finding composer;
- #538/#535: rhythm-density A/B relation;
- #461: relation payload → Breakdown / shared-time product integration.

### Required sequence

1. **Finish one relation end-to-end.**
   - real production evidence;
   - validated relation;
   - grounded finding;
   - API/product payload;
   - Breakdown rendering;
   - focus / A-B compare / evidence interaction on a real Work.

2. **Validate the vertical slice on materially different music.**
   - do not treat one demo as product proof;
   - verify truthfulness, absence/withholding, shared-time behavior, and representation choice.

3. **Implement #548 on the settled relation contract.**
   - within-Work contextual comparison;
   - no new detector;
   - explicit reference-population coverage and sufficiency.

4. **Implement the first #547 Learn path over that same real finding.**
   - likely Observe / Compare / optional Prompt / Reveal first;
   - no persistence or Education IA needed.

5. **Add Transfer only after recurrence/similarity clears its own gate.**

6. **Add Experiment only after a real counterfactual rendering/artifact contract exists.**

Agents must not fork `RelationObservation`, `GroundedFinding`, Breakdown support semantics, or evidence persistence merely to implement this document.

---

## 10. First vertical product acceptance scenario

The most useful next product proof is not another architecture diagram. It is one complete grounded comparison experience.

A valid first scenario should demonstrate:

```text
Work opens
→ Breakdown surfaces a real supported comparative finding
→ click finding focuses the correct primary span
→ Compare exposes the real comparison span
→ user can hear A and B cheaply
→ Evidence shows only adequate supporting representation(s)
→ wording remains literal and support-resolvable
→ optional Learn enters without hiding/removing the ordinary finding
→ Learn exits back to the same musical context
```

Test at minimum:

- normal supported finding;
- insufficient/withheld relation;
- partial/progressive analysis state;
- a source where Score is not the right support representation;
- a narrow viewport;
- reduced motion.

The success criterion is not that the app displays more analysis. It is that a user can **notice a musical difference, hear it, see credible support, understand it, and optionally learn from it without leaving the music**.

---

## 11. What not to build yet

Do not let the computational-musicology/pedagogy direction create another infrastructure cycle.

Specifically defer:

- global music-knowledge graph;
- learner profile database;
- curriculum engine;
- cross-user corpus statistics;
- universal “normal music” baselines;
- vector database solely for pedagogy;
- generated counterfactual audio without a validated transformation contract;
- educational content generation detached from a real finding;
- a fixed beginner/intermediate/advanced user classification;
- detector expansion merely to make more lesson types.

The near-term product advantage should come from **better use of the evidence and relations already being built**.

---

## 12. Product north star

The end state is not a dashboard of extracted features and not primarily an automated music-theory textbook.

It is an environment where the user can move fluidly between:

```text
What stands out?
→ Where is it?
→ Let me hear it.
→ What changed?
→ Show me why you believe that.
→ Explain it.
→ Teach me through this example, if I want.
→ Where else does this happen?
→ What would it sound like if that feature changed?
```

Immediate insight remains the default. Active learning is an optional depth of interaction.

That preserves listencloser’s core direction: trustworthy evidence first, musical relationships second, explanation and pedagogy grounded back in the sound.