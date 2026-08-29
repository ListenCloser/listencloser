# Evidence Sufficiency V3 — initial claim gates

Status: **research / architecture contract**. This document and its machine-readable companion do not enable production analysis or product exposure.

Related: #457, #458, #456, #336, #340, #468, #472, #474.

## Why this exists

Evidence quality is only meaningful relative to a downstream claim. A global tempo estimate can support a tempo display while being insufficient for a statement about a snare anticipating the downbeat. Approximate section boundaries may support browsing while being insufficient for an exact layer-entry claim.

The initial contract therefore makes one question explicit:

> What must be true before hello-ai is allowed to make this particular musical claim?

The checked-in source of truth for this first slice is `backend/evaluation/analysis_v3/claim_sufficiency.json`. It is validated against the existing capability maturity registry. The contract fails closed: a claim marked `SUPPORTED_NOW` cannot depend on planned evidence or a capability whose current status is experimental, evaluation-only, or withheld.

## Readiness vocabulary

- `SUPPORTED_NOW` — all required checked-in capabilities are currently production; the claim is still restricted to its documented domain and abstention rule.
- `BLOCKED_BY_EVIDENCE_QUALITY` — the relevant evidence family exists, but current maturity/validation is not sufficient for the claim.
- `BLOCKED_BY_MISSING_EVIDENCE` — a required evidence primitive is not yet represented by a production capability.
- `STYLE_SPECIFIC_RESEARCH` — the claim requires an explicit analytical framework/context in addition to evidence quality.
- `SEMANTIC_ONLY` — reserved for hypotheses that should not be asserted as exact musical facts without task-level validation.

## Quality-gate vocabulary

The first reusable gates are deliberately small:

- `EXACT_EVENT_REQUIRED` — small localization or event-identity errors can invalidate the claim.
- `EVENT_COVERAGE_REQUIRED` — quality must include how much of the relevant event population is actually recovered, not only error statistics over matched events. The acceptable coverage remains claim- and domain-specific.
- `LOCALIZATION_TOLERANT` — approximate localization can still support the intended aggregate/comparative statement.
- `AGGREGATE_ONLY` — evidence is safe only as a summary, not as exact local events.
- `MULTI_EVIDENCE_CORROBORATION` — no single descriptor is sufficient; independent evidence dimensions must converge.
- `STYLE_CONTEXT_REQUIRED` — interpretation is valid only inside an explicit analytical framework.
- `USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE` — trusted user-selected spans can support the comparison even when automatic section evidence cannot.
- `SEMANTIC_HYPOTHESIS_ONLY` — model prose/hypothesis must remain distinct from detected or derived fact.

These names are provisional and should be revised from #456 corpus evidence and #457 perturbation experiments rather than treated as ontology for its own sake.

## What the first ten gates reveal

### Usable now, narrowly

1. **Global key identification** can use the production key capability, but it must stay global. It cannot imply local key regions or modulation.
2. **Localized chord labels** can use the trusted chord path inside its validated domain and should still withhold unsupported spans.
3. **User-selected rhythm-density contrast** can compare deterministic density measurements without pretending the selected spans are automatically detected verses/choruses.

`SUPPORTED_NOW` means the current registry allows the evidence path; it does **not** erase domain limitations or turn benchmark accuracy into certainty for each item.

### High-leverage blockers

1. **Trusted sections / repetition.** Named section comparisons remain blocked because `section`/`structure` are evaluation-only. User selection is a valuable escape hatch for some comparisons.
2. **Beat/downbeat/bar phase.** Production tempo is not enough for beat-relative groove claims. #474 made the distinction concrete: the production librosa path estimated global tempo accurately on its Candombe validation files while matching only 33.46% of reference beats; Beat This `single_final0` matched 100% with materially better localization. #472 therefore preserves coverage alongside matched-event timing error. A beat-relative claim must clear both localization and claim-appropriate coverage gates, plus whatever onset/source evidence it needs.
3. **Perceptual and source/layer series.** #468 established a bounded evaluation-only perceptual evidence layer, but explaining a produced-music transition as a convergence of energy, spectral/register, and arrangement changes still needs claim-level relation validation and source activity where applicable.
4. **Melodic correspondence.** Current melody extraction is experimental and motif matching is evaluation-only, so transposed-return claims should not be product facts yet.
5. **Local tonal context.** Global key plus oracle theory interpretation is insufficient for local modulation, cadence, or framework-specific motion claims. `key_region` and `cadence` are explicitly withheld today.

This prioritization is intentionally downstream-driven: improve evidence that unlocks many useful claims before polishing low-leverage detectors.

## Localization and coverage are separate failure modes

An event detector can have a small median localization error over the events it happens to match and still miss most relevant events. That is unsafe for repeated beat-relative statements, because the omitted events may change the pattern being described.

#472's perturbation utilities therefore keep these quantities separate:

- matched-event timing error;
- reference-event coverage;
- assignment changes under controlled grid perturbation.

The contract does **not** convert the #474 result into a universal threshold such as “X ms” or “Y% coverage.” A groove claim, notation consumer, section summary, and playback affordance may legitimately require different operating points. Thresholds belong to task/domain validation.

## User-verifiable proof is part of the gate

Every representative claim includes `proof_actions`, such as:

- seek / loop the exact span;
- compare two spans or occurrences;
- show the beat grid or onset positions;
- show chord/local tonal evidence;
- show the measured change series.

A claim is not fully useful merely because the backend can compute it. The product should let a user inspect why the claim was made through the music itself.

## Next experiments

This PR is a policy skeleton, not completion of #457. #472 now supplies the first deterministic metric-grid and span-boundary perturbation primitives; follow-up research should extend the same discipline to:

1. **Metric-grid downstream claims:** connect measured localization/coverage to concrete beat-relative relations without inventing a universal threshold.
2. **Section/perceptual boundaries:** apply span perturbation to #468 real perceptual A/B relations and measure when the relation changes materially.
3. **Melody perturbation:** drop/add/shift notes and measure recurrence, contour, and register claim stability.
4. **Chord/key perturbation:** inject upstream errors and quantify failure propagation into Roman numeral/function/cadence claims.
5. **Separation/source perturbation:** quantify how bleed/noise affects source-entry and multi-evidence transition claims.

Thresholds from those experiments should eventually become evidence-specific gate metadata. They should not be invented in this document.

## Relationship to #456 and the research matrix

#456 is expected to derive a broader explanation taxonomy from human expert breakdowns. The ten executable claims here are representative architecture probes grounded in the current roadmap and capability registry, not a claim that the human explanation corpus has already been enumerated.

The provisional research matrix in #470 contains useful additional hypotheses such as cross-version meter regularization, corpus-level strategy comparison, controlled reharmonization, and recreation-as-verification. Those should remain **research inputs** until they are promoted into this validated contract or rejected. This file plus `claim_sufficiency.json` should be treated as the executable policy source of truth; parallel provisional matrices should not silently become competing production contracts.

## Non-goals

- no production router or product-visible prose;
- no new detector;
- no graph/vector database;
- no genre-specific product fork;
- no fabricated confidence, localization, or coverage threshold;
- no assumption that MIDI is required for every claim;
- no assumption that a capability being implemented means it is sufficient for every downstream interpretation.
