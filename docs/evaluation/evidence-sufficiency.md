# Evidence Sufficiency V3 — executable claim gates

Status: **research / architecture contract**. This document and its machine-readable companion govern readiness policy; they do not themselves expose a product claim.

Related: #457, #458, #456, #336, #340, #468, #472, #474, #487, #476.

## Why this exists

Evidence quality is meaningful only relative to a downstream claim. A global tempo estimate can support a tempo display while being insufficient for a statement about an onset anticipating a downbeat. A stable spectral descriptor can support a literal A/B measurement while being insufficient for a claim that a passage became "brighter," "more exciting," or a "drop."

The checked-in source of truth is:

`backend/evaluation/analysis_v3/claim_sufficiency.json`

`claim_sufficiency.py` validates that contract against the capability maturity registry and fails closed when a readiness label overstates the maturity of its required evidence.

## Readiness vocabulary

- `SUPPORTED_NOW` — every required checked-in capability is production and the claim is restricted to its declared domain, locator requirements, and abstention rule.
- `SUPPORTED_EXPERIMENTAL` — every required capability is production or experimental, at least one is experimental, and the claim is restricted to a declared validated domain. This is not equivalent to production-safe generalization.
- `BLOCKED_BY_EVIDENCE_QUALITY` — the relevant evidence family exists, but a required capability is still experimental, evaluation-only, or withheld for this stronger claim.
- `BLOCKED_BY_MISSING_EVIDENCE` — one or more required evidence primitives are not yet represented by a usable capability.
- `STYLE_SPECIFIC_RESEARCH` — the claim requires an explicit analytical framework/context in addition to evidence quality.
- `SEMANTIC_ONLY` — a hypothesis or interpretation must remain distinct from measured/detected fact and needs task-level validation before factual wording is allowed.

Readiness is about **evidence sufficiency**, not whether a UI card or relation handler already exists. For example, the promoted `perceptual_series` evidence is now sufficient for a literal explicit-span comparison, while #476 still owns the reusable product/domain `COMPARE` implementation.

## Quality-gate vocabulary

- `EXACT_EVENT_REQUIRED` — small localization or event-identity errors can invalidate the claim.
- `EVENT_COVERAGE_REQUIRED` — matched-event precision is insufficient without adequate recovery of the relevant event population.
- `LOCALIZATION_TOLERANT` — approximate localization can support the intended aggregate/comparative statement.
- `AGGREGATE_ONLY` — evidence is safe as a bounded summary, not as exact event truth.
- `MULTI_EVIDENCE_CORROBORATION` — no single descriptor is sufficient; independent evidence dimensions must converge.
- `STYLE_CONTEXT_REQUIRED` — interpretation is valid only inside an explicit analytical framework.
- `USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE` — explicit trusted spans can support the comparison before automatic structure is trustworthy.
- `SEMANTIC_HYPOTHESIS_ONLY` — interpretive/model prose stays in a lower truth tier than measured or derived fact.

These are reusable safety gates, not a genre ontology and not universal numeric thresholds.

## Current sufficiency map

### Production evidence supports narrow literal claims

The contract currently permits, within their documented domains:

1. work-level global key identification;
2. localized trusted chord labels;
3. user-selected symbolic note-density comparison;
4. **user-selected PerceptualSeries comparison** over the same source lineage and canonical preprocessing contract.

The fourth item is new after #487. It can state literal quantities such as:

- RMS amplitude proxy is higher/lower between two explicit spans;
- onset-strength aggregate is higher/lower;
- spectral-centroid aggregate is higher/lower;
- relative coarse-band distribution changed.

It cannot silently upgrade those measurements to calibrated loudness, semantic timbre adjectives, source identity, affect, formal-section labels, or causal explanations.

### Experimental evidence remains visibly experimental

`melody_register_peak` is now represented as `SUPPORTED_EXPERIMENTAL` rather than being collapsed into either production or blocked. Its current evidence is bounded to the LStoM pop/arranged symbolic-MIDI validation domain. The contract explicitly rejects generalizing that result to arbitrary piano or recorded-music transcription.

This readiness tier exists so experimentally useful evidence can participate in research/product prototyping without weakening the meaning of `SUPPORTED_NOW`.

### High-leverage blockers remain explicit

1. **Trusted structure/repetition.** Named section comparisons remain blocked while automatic section evidence is evaluation-only. Explicit user spans can substitute for structure only when the claim does not require section identity.
2. **Metric grid/downbeat/bar phase.** Global tempo is not enough for groove or flow timing. #474 showed why: the production librosa path could estimate tempo while recovering only a minority of reference beat events on the published Candombe validation slice. #472 therefore preserves event coverage separately from matched-event timing error.
3. **Vocal/syllable localization.** Rap-flow alignment remains blocked until local vocal events and the metric grid are both accurate at claim-relevant resolution.
4. **Source/performer identity plus recurrence.** Jazz motivic interaction remains blocked; co-occurrence is not evidence that one performer responded to another.
5. **Source/layer activity.** #487 now supplies measured perceptual change, but a produced-music "drop" explanation still needs independently supported layer activity and a trusted or explicit transition locator.
6. **Melodic correspondence.** Transposed-return claims remain blocked by evaluation-only motif matching and broader melody-domain uncertainty.
7. **Local tonal context.** Global key plus oracle theory interpretation is insufficient for modulation, cadence, or stronger framework-specific tonal-motion claims.

## Measured relation versus interpretation

The contract deliberately separates three statements that may sound similar in casual prose:

1. **Measured:** "the spectral-centroid median is higher in span B."
2. **Relational/editorial:** "several measured dimensions change together at this transition."
3. **Interpretive:** "the transition feels more exciting because it gets brighter."

#487 supports the first for explicit same-source spans. The second may require additional independently validated evidence such as source/layer activity. The third is `SEMANTIC_ONLY` unless an explicit semantic/context layer has been validated for that task and its uncertainty is preserved.

This boundary is central to Analysis V3: availability of a low-level descriptor must never manufacture a psychological, stylistic, or causal fact.

## Localization and coverage are separate failure modes

An event detector can have a small median localization error over the events it happens to match while missing most relevant events. That is unsafe for repeated beat-relative statements because omitted events can change the pattern being described.

#472 therefore keeps separate:

- matched-event timing error;
- reference-event coverage;
- assignment changes under controlled grid perturbation;
- span-membership changes under boundary perturbation.

The contract does not convert one benchmark into a universal threshold. A groove claim, notation consumer, section summary, and playback affordance can legitimately require different operating points.

## User-verifiable proof is part of the contract

Every representative claim records proof actions such as:

- seek or loop the exact span;
- compare A/B spans or occurrences;
- show the measured evidence series and aggregates;
- show beat-grid/event locations;
- show local tonal evidence and analytical framework;
- show hypothesis supports separately from the hypothesis itself.

A backend statement is not a complete explanation if the user cannot inspect why it was made through the music.

## Consolidation of #470

#470 was useful as a provisional research matrix derived from early #456 review. It is **not** a second policy source of truth.

This executable contract now promotes the #470 hypotheses that have a clear current role:

- experimental melody register;
- explicit-span literal perceptual comparison;
- rap flow/metric alignment blockers;
- jazz motivic interaction blockers;
- subjective/affective causal interpretation as semantic-only.

Other #470 hypotheses—cross-version meter regularization, corpus-level strategy generalization, controlled reharmonization, and recreation-as-verification—remain useful research inputs for later M2/M3/M4 work, but are not promoted merely to increase taxonomy coverage.

## Next work

1. #476: implement the first deterministic `COMPARE` RelationObservation over promoted PerceptualSeries and explicit seconds-authoritative spans.
2. Extend #472-style perturbation tests to the concrete relation output, especially boundary sensitivity and evidence coverage.
3. Continue held-out metric-grid validation before any beat-relative production claim.
4. Validate source/layer activity before multidimensional arrangement/drop explanations.
5. Expand melody, recurrence, tonal, and semantic gates only when task-level evidence justifies them.

## Non-goals

- no production router or product-visible prose in this contract;
- no new detector;
- no graph/vector database;
- no genre-specific product fork;
- no fabricated confidence, localization, or coverage threshold;
- no assumption that MIDI is required for every claim;
- no assumption that an implemented capability is sufficient for every downstream interpretation.
