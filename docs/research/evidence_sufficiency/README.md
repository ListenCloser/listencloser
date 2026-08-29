# Evidence sufficiency — provisional seed

Issue: #457  
Roadmap: #458  
Inputs: current `backend/config/capabilities.json`, #321, #332–#339, #455, #456

## Purpose

Turn “evidence quality is foundational” into a claim-specific engineering map.

This seed is intentionally provisional: it uses the current production capability registry plus existing Analysis V3 decisions before the full #456 explanation corpus and #455 perceptual evaluation are complete.

## Initial result

The current bottleneck is **not a general lack of analysis code**. It is a small set of high-leverage evidence gaps that block many relational explanations.

### Highest-leverage blockers

#### 1. Trusted metric grid / downbeat / bar phase — #335

Blocks or weakens:
- beat-relative onset timing;
- anticipation/delay claims;
- groove comparisons;
- rap flow ↔ beat analysis;
- rhythm-pattern alignment;
- some notation/structure consumers.

A correct global tempo is not enough. Claims about musical position within a bar are highly sensitive to phase/localization error.

#### 2. Perceptual audio series — #455

Blocks or weakens:
- low-end entry/dropout;
- energy/dynamics comparison;
- spectral redistribution;
- broad texture/activity contrast;
- multi-dimensional transition explanations.

This looks high leverage because the underlying evidence can be cheap, time-localized, and applicable to music where MIDI/score is weak or irrelevant.

#### 3. Trusted structure / repetition — #321 + future similarity work

Blocks or weakens:
- automatic section A/B comparison;
- formal narrative;
- repeated-section analysis;
- transition salience;
- arrangement comparison.

However, **user-selected spans can substitute for automatic structure** for some comparison claims. This is an important product shortcut and should be encoded in sufficiency policy rather than waiting for perfect segmentation.

#### 4. Source/layer identity and activity — #334 / #337

Blocks or weakens:
- source entry/exit;
- arrangement/layer changes;
- performer interaction;
- drum/bass/vocal-specific relations;
- isolate-backed proof actions.

Possessing a separated stem file is not itself enough; claims need trustworthy source/activity semantics.

#### 5. Motif/recurrence evidence

Blocks or weakens:
- “this idea returns”;
- transposed recurrence;
- motivic interaction;
- variation/transformation claims.

Current `melody_motif` is correctly `evaluation_only`; this should not be solved by simply exposing the existing custom matcher.

## What is already useful today

The registry already supports some narrow evidence-backed relationships:

- experimental melody register peak/low within the validated LStoM domain;
- deterministic MIDI/beat note-density and rest measurements;
- trusted chord/key evidence with explicit downstream prerequisites;
- Roman numeral / harmonic function when trusted key+chord prerequisites hold.

The important constraint is **scope**. A MIDI note-density comparison is not equivalent to full audio texture density, and oracle theory-interpreter accuracy does not erase upstream chord/key error or framework applicability.

## Example sensitivity classes

### Exact-event sensitive
Examples:
- onset anticipates downbeat;
- rap syllable is behind beat;
- cadence at a precise location.

Small timing/phase errors can invalidate the claim.

### Localization tolerant
Examples:
- broad section energy increases;
- melody register is generally higher in span B;
- a section is denser over several seconds.

Moderate boundary error may not materially change the relation.

### User-selection substitutable
Examples:
- compare energy/density between two spans;
- compare harmony/activity between user-chosen sections.

Automatic structure is helpful but not required when the user supplies the scopes.

### Multi-evidence corroboration
Examples:
- several dimensions change together at a transition;
- one player responds to another motif.

No single detector output should be promoted as the complete explanation.

### Framework required
Examples:
- dominant function;
- prolongation;
- named style/cultural convention.

The evidence may be factual while the interpretation is framework-dependent.

### Semantic hypothesis only
Examples:
- “this is exciting because…”;
- “this sounds nostalgic because…”.

Measured changes may support an interpretation, but no low-level descriptor should directly become subjective/causal truth.

## Immediate next work

1. Replace provisional claim families with stable rows from the expanded #456 corpus.
2. Add perturbation tests for the top sensitive relations:
   - beat/downbeat shifts;
   - section-boundary shifts;
   - note/melody deletions;
   - chord/key corruption;
   - stem/source leakage;
   - perceptual-series normalization changes.
3. Add alternative evidence paths where one claim can be supported multiple ways.
4. Compute a qualitative upstream priority ranking based on claims unlocked × quality gap × cross-style applicability × operational feasibility.
5. Feed the resulting gates into #459/M1 promotion decisions and #460 relation contracts.

## Current recommendation

Do **not** wait for every evidence family to become perfect before shipping better relational analysis.

Instead:
- promote high-leverage evidence when its specific downstream claims are robust;
- allow explicit user selections to bypass weak automatic structure where valid;
- preserve experimental/domain labels;
- abstain for exact-event or framework-specific claims until their prerequisites clear the relevant gate.
