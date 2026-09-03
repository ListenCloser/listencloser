# Product roadmap

This document is the canonical authority for **current product portfolio state and product sequencing**. It answers:

> What product work is authorized or worth considering next, and why?

[`PRODUCT.md`](PRODUCT.md) owns durable product identity, JTBD, strategic arena, mental model, and product principles. Focused GitHub issues own bounded discovery/evaluation/delivery scope. Live issues and pull requests own execution state. [`backend/config/capabilities.json`](../../backend/config/capabilities.json) owns runtime analysis maturity/exposure, and the evaluation docs own evaluation method and accepted technical results.

Roadmap posture is deliberately small:

- **ACTIVE** — the named product/enabling outcome is authorized now.
- **NEXT_PROBE** — only the bounded decision-changing probe is authorized; production implementation is not.
- **GATED** — do not activate the downstream product work until the named gate clears.
- **REVISIT** — no current work; reopen only on the focused owner's named trigger.
- **REJECT** — current evidence says not to pursue.
- **DONE** — the portfolio decision is complete; ordinary maintenance is not roadmap work.

## Current wedge

**Understand** is the current wedge: help a person move from hearing something they care about to a supported musical understanding they can locate, inspect, and verify.

The current portfolio has two simultaneous responsibilities:

1. finish the trust/representation prerequisites that make supported musical objects reliable enough to use; and
2. test whether those objects actually create more coherent understanding before broadening the product with more representations or automated relationships.

The closest adjacent expansion is **explicit user-chosen comparison**. Automatic recurrence/retrieval and broader corpus intelligence remain downstream until explicit A/B proves the relationship job is valuable.

## Opportunity hierarchy

1. **O1 — trustworthy inspectable musical objects.** The user must be able to connect what they hear to the right representation/evidence with exact authority and truthful projection. This is a blocking prerequisite, not the product end state.
2. **O2 — coherent grounded understanding.** The largest current product-value uncertainty is whether admitted evidence can become an understanding that is materially more useful than today's compact findings plus playback/inspection.
3. **O3 — explicit relationships / Compare.** Test user-chosen A/B before assuming automatic recurrence, retrieval, or corpus similarity is valuable.
4. **O4 — the right abstraction for the question.** Test whether a simpler task-shaped representation creates progress before investing in another automatic representation pipeline.
5. **O5 — act on understood musical ideas.** Creative/practice/transform workflows remain later options until the understand → verify → relate loop earns expansion.

## Portfolio

Horizons describe current investment posture, not a calendar.

### H1 — core: make Understand trustworthy and valuable

#### Product bets

| Bet | Posture | Why now | Weakest important assumption | Hard gate | Next decision | Focused owner |
| --- | --- | --- | --- | --- | --- | --- |
| Grounded contextual Breakdown | **ACTIVE** | A normal supported contextual finding is the smallest shipped bridge from evidence to useful understanding and a prerequisite for richer explanation. | Does the grounded finding create useful progress when it reaches ordinary Breakdown with hear/focus/evidence intact? | Exact Version/support truth and existing Breakdown admission semantics must remain intact. | Ship the bounded grounded finding or fail closed; do not create another finding/ranking system. | [#588](https://github.com/ListenCloser/listencloser/issues/588) |
| Understanding-presentation probe | **NEXT_PROBE** | This is the highest-information-value test of the core wedge: whether the evidence already available can produce better understanding before adding more evidence surfaces. | Does staged presentation improve comprehension, and is the winning shape narrative, guided listening/reveal, or the current compact Breakdown? | Production implementation remains gated on usable grounded findings, representation-native focus, exact representation authority, and preserved playback/selection/Ask context. | Choose `NARRATIVE`, `GUIDED_INTERACTION`, `CURRENT_BREAKDOWN`, or `INSUFFICIENT_EVIDENCE` from one bounded manual round. | [#1089](https://github.com/ListenCloser/listencloser/issues/1089) |

#### Enabling prerequisites

These are authorized because they are required for the current product outcome; they are not independent product bets.

| Enabler | Posture | Product reason / gate | Focused owner |
| --- | --- | --- | --- |
| Representation fidelity across Piano Roll / Score | **ACTIVE** | Core inspectable objects must preserve the right musical evidence rather than hide upstream errors. | [#498](https://github.com/ListenCloser/listencloser/issues/498) |
| Exact representation / Version authority | **ACTIVE** | Downstream evidence, projection, comparison, and alignment must bind to the exact semantic representation instead of kind/recency guesses. | [#613](https://github.com/ListenCloser/listencloser/issues/613) |
| Representation-native evidence focus/projection | **ACTIVE** | A supported claim must remain inspectable in the representation where its evidence can be shown truthfully. | [#807](https://github.com/ListenCloser/listencloser/issues/807) |
| Product-shaped theory truth | **ACTIVE** | Do not let oracle/theoretical quality substitute for detected-input evidence; withheld theory remains withheld until valid evidence changes the decision. | [#1020](https://github.com/ListenCloser/listencloser/issues/1020) |
| Existing MusicXML as source-score evidence | **ACTIVE** | Use authoritative written evidence the musician already has instead of forcing unnecessary reconstruction; this also creates a trustworthy score-side input for later relations. | [#1082](https://github.com/ListenCloser/listencloser/issues/1082) |
| Score ↔ performance relation publication / first product proof | **GATED** | The maintained alignment method and normalized relation have been adopted, but product publication must not bypass exact source/role authority or shared focus semantics. | [#1083](https://github.com/ListenCloser/listencloser/issues/1083) |

### H2 — adjacent: test relationships and abstraction with cheap evidence

| Bet | Posture | Why now | Weakest important assumption | Hard gate | Next decision | Focused owner |
| --- | --- | --- | --- | --- | --- | --- |
| Explicit A/B Compare | **NEXT_PROBE** | It is the closest adjacent job and removes the assumptions of automatic candidate discovery. | Do musicians repeatedly benefit from an explicit A/B loop, and do measured relations add value beyond precise alternating playback? | Production cross-Work claims require dimension-specific comparable-evidence contracts; the current probe must stay manual/prototype-first. | Choose `PLAYBACK_ONLY`, `A_B_INTERACTION`, `A_B_PLUS_RELATION`, `CROSS_WORK_DEMAND`, or `NO_STRONG_JOB`. | [#1088](https://github.com/ListenCloser/listencloser/issues/1088) |
| Minimum useful abstraction (chord map vs lead sheet) | **NEXT_PROBE** | Compact actionable representations have strong proxy evidence, but ListenCloser still needs to learn which level of detail actually helps its target jobs. | Does a compact abstraction beat Score/Piano Roll, and does melody add enough value over chords alone? | Discovery uses trusted/manual content; automatic production remains gated on bounded melody/chord truth and exact compatible lineage. | Choose `CURRENT_VIEWS`, `CHORD_MAP`, `LEAD_SHEET`, `NICHE_ONLY`, or `INSUFFICIENT_EVIDENCE`. | [#1091](https://github.com/ListenCloser/listencloser/issues/1091) |
| Performance-expression evidence | **GATED** | Aligned timing/dynamics/articulation could make the difference between written and performed music inspectable. | Does aligned expression evidence create meaningful progress over existing Score/Piano Roll for a real performance task? | #1083 must first complete a trustworthy exact-Version product alignment path and proof. | After the alignment gate clears, run one bounded audible task before widening the product surface. | [#1086](https://github.com/ListenCloser/listencloser/issues/1086) |
| Continuous pitch representation | **REVISIT** | Technical feasibility is not the current uncertainty; its value to the chosen understand/verify wedge is still weakly evidenced. | Is there a concrete voice/expressive-monophonic task where continuous pitch materially beats current representations? | Reopen only with decision-changing desirability/task evidence, then evaluate the smallest maintained OSS path. | Keep unimplemented unless a concrete task clears the reopening trigger. | [#1087](https://github.com/ListenCloser/listencloser/issues/1087) |
| Within-Work recurrence | **REVISIT** | The real-musical probe did not establish reliable boundaries or honest `no useful return` behavior. Explicit A/B carries fewer assumptions. | Can recurrence retrieve independently grounded positives, abstain on negatives, and be audibly useful? | Reopen only with a lawful independently annotated positive/negative corpus plus human audible judgments. | Do not add matching/retrieval infrastructure from current evidence. | [#812](https://github.com/ListenCloser/listencloser/issues/812) |
| Measured-change navigation | **REVISIT** | Promoted evidence exists, but no real product-usefulness result justifies a new navigation/change-point surface. | Does measured-change navigation answer a concrete “where should I listen next?” job better than existing Breakdown/navigation? | A predeclared multi-Work listening probe with exact evidence coverage and a bounded stop condition. | Keep inactive unless that product problem becomes concrete. | [#848](https://github.com/ListenCloser/listencloser/issues/848) |

### H3 — options: preserve cheaply, do not build speculative programs

- **GATED — personal corpus / cross-Work retrieval:** only after explicit Compare demonstrates recurring cross-Work demand and a truthful comparison/retrieval contract exists.
- **GATED — multi-performance comparison / practice:** only after Score↔performance alignment is product-proven and one-performance expression evidence is useful.
- **GATED — source-score OMR:** only after attaching existing source scores proves enough value to justify harder ingestion.
- **REVISIT — creative proposal / transformation loop:** first prove a user wants to act on an understood selection through inspect → compare → accept/reject semantics; do not begin with a generative model.
- **REVISIT — broader instrument-native representations / publishing:** shape only when a concrete target job is blocked by the current core loop.

## Portfolio dependency / sequencing notes

Only decision dependencies belong here; detailed implementation ordering stays in focused issues.

- **Core understanding before breadth:** run the #1089 understanding-presentation probe while #588/#613/#807 continue making grounded objects trustworthy. A positive desirability result raises priority but does not waive those implementation gates.
- **Explicit Compare before automatic discovery:** test #1088 before reactivating #812 recurrence, cross-Work retrieval, embeddings, clustering, or corpus intelligence.
- **Source/authority before downstream performance claims:** attach trustworthy score evidence (#1082), preserve exact representation authority (#613), and complete the product-safe #1083 relation/focus path before activating #1086 expression claims.
- **Choose the abstraction before automating it:** run #1091 with trusted/manual material before starting new melody/chord model work or an automatic lead-sheet pipeline for this product bet.
- **Runtime capability maturity is not portfolio authorization:** `capabilities.json` may make a probe possible or block a claim, but a working model/engine does not promote a product bet by itself.

## How roadmap changes

A portfolio decision changes this file. A PR merge, benchmark result, or new implementation idea does **not** require a roadmap edit unless it changes a posture, gate, horizon, sequencing dependency, or next product decision.

When evidence changes one of those facts:

1. update this roadmap as the current portfolio authority;
2. update the focused issue body when its own posture/gate/decision contract changes;
3. leave detailed execution and live PR state in GitHub;
4. link to evaluation/capability authorities instead of copying their tables or runtime status here.

Issue comments and historical strategy threads are evidence/provenance, not a newer roadmap layer that overrides this file.
