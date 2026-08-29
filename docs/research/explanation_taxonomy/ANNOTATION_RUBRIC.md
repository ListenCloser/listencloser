# Explanation Capability Taxonomy — annotation rubric

Issue: #456  
Roadmap: #458  
Downstream consumer: #457 / #460

## Objective

Annotate **how strong musical explanations are constructed**, not merely which theory topics they mention.

The unit of analysis is a paraphrased explanatory claim or demonstration. Do not copy creator scripts, captions, textbook prose, or article passages into the dataset.

## Core annotation unit

Each row should answer:

```text
What is the listener/user trying to understand?
What musical entities or spans are involved?
What relationship is being asserted?
What evidence would be required to support that relationship?
What contextual/theoretical assumptions are required?
How does the source make the claim convincing?
When should hello-ai abstain from making the analogous claim?
```

## Required fields

### `source_id`
Stable ID from `source_manifest.json`.

### `scope`
One of:
- `event`
- `passage`
- `section`
- `work`
- `cross_section`
- `cross_work`
- `corpus/style`

### `question_class`
The perceptual/editorial question being answered, paraphrased.

Examples:
- what changed here?
- why does this passage feel unstable?
- where does this idea return?
- how do these two players interact?
- what makes these examples sound related?

### `claim_family`
Start with this controlled vocabulary and revise from corpus evidence:
- `identification`
- `change`
- `contrast`
- `repetition`
- `transformation`
- `coordination`
- `timing_alignment`
- `function`
- `expectation`
- `salience`
- `style_context`
- `perceptual_production`
- `generalization`
- `pedagogical`
- `counterfactual_recreation`

### `relation`
Prefer a compact relation operator over a bespoke English sentence.

Seed vocabulary:
- `repeats`
- `returns`
- `similar_to`
- `varies`
- `transforms`
- `transposes`
- `fragments`
- `precedes`
- `follows`
- `overlaps`
- `enters`
- `exits`
- `increases`
- `decreases`
- `contrasts_with`
- `aligns_with`
- `offsets_from`
- `anticipates`
- `delays`
- `supports`
- `fills`
- `doubles`
- `responds_to`
- `converges_with`
- `diverges_from`
- `contains`

Framework-specific operators such as `resolves_to`, `prolongs`, or `dominant_function` must also set an explicit analytical framework.

### `entities`
Musical objects involved, such as:
- span / section
- beat / downbeat / bar
- onset / event
- melody / motif
- chord / tonal center
- source / instrument / voice
- timbre / spectral region
- lyric / syllable
- performer
- representation

### `required_evidence`
Evidence families that must exist before hello-ai can support the claim.

Canonical families for the first pass:
- `metric_grid`
- `events_activity`
- `pitch_notes_melody`
- `harmony_tonality`
- `structure_sections`
- `repetition_similarity`
- `source_layer_activity`
- `perceptual_audio`
- `performance_timing`
- `spatial_mix`
- `text_lyrics`
- `context_style`
- `symbolic_score`

### `optional_evidence`
Independent evidence that strengthens but is not mandatory for the core relation.

### `interpretive_tier`
- `measured_detected`
- `derived_relational`
- `context_model_estimated`
- `interpretive_hypothesis`

### `framework`
`null` for broadly descriptive relations. Otherwise name the theory/context required, e.g. `western_functional_tonality`, `rap_flow_beat_alignment`, `jazz_motivic_interaction`.

### `localization_requirement`
- `exact_event`
- `tight_span`
- `section_level`
- `aggregate_only`
- `cross_work`

### `proof_mode`
How the source makes the claim inspectable/convincing:
- replay exact span
- loop
- isolate layer
- slow down
- score/piano-roll/beat-grid highlight
- A/B section comparison
- compare recurrence
- normalized/transposed comparison
- reharmonize/change one variable
- recreate in style
- corpus/style comparison

Multiple proof modes are allowed.

### `salience_signal`
Why this claim was worth editorial attention:
- large change
- repetition with transformation
- expectation violation
- convergence of independent changes
- structurally important location
- style-atypical event
- foreground audibility
- high explanatory leverage

### `abstention_condition`
Concrete condition under which an analogous product claim should be withheld.

Examples:
- downbeat/bar phase is not trusted;
- comparison span cannot be localized;
- chord/key evidence conflicts;
- source identity is unavailable;
- style/theory framework does not apply;
- only a semantic model suggests the claim with no structured support.

## Annotation depth

Each row carries `review_depth`:
- `metadata_only` — title/description/abstract supports only a coarse pattern hypothesis;
- `partial_review` — a relevant excerpt/section was reviewed;
- `full_review` — complete artifact reviewed for this claim.

**Metadata-only rows must never be counted as final corpus evidence.** They exist to bootstrap the rubric and identify what needs full annotation.

## Inter-annotator discipline

Before scaling to 30–50 artifacts:

1. annotate the same 3–5 sources independently twice;
2. compare disagreements in claim family, relation, evidence prerequisites, and interpretive tier;
3. revise definitions where disagreements reflect rubric ambiguity;
4. preserve legitimate multiple readings rather than forcing false consensus;
5. only then expand the corpus.

## Product mapping

Every stable recurring claim family should eventually map to:

```text
claim family
→ evidence prerequisites
→ relation implementation candidate
→ sufficiency/error sensitivity (#457)
→ proof/action UI
→ supported / experimental / withheld
```

The taxonomy is successful only if it changes engineering priorities or product behavior; a descriptive list of music-theory topics is insufficient.
