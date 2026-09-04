# Product roadmap

This document is the canonical authority for **current product portfolio state and product sequencing**. It answers:

> What product work is authorized or worth considering next, and why?

[`PRODUCT.md`](PRODUCT.md) owns durable product identity, JTBD, strategic arena, mental model, and product principles. Focused GitHub issues own bounded discovery/evaluation/delivery scope. Live issues and pull requests own execution state. [`backend/config/capabilities.json`](../../backend/config/capabilities.json) owns runtime analysis maturity/exposure, and the evaluation docs own evaluation method and accepted technical results.

Roadmap posture is deliberately small:

- **ACTIVE** — the named product/enabling outcome is authorized now. `ACTIVE` may mean an explicitly experimental product path; it does **not** imply canonical/default/trusted-for-all-domains.
- **NEXT_PROBE** — only the bounded decision-changing probe is authorized; production implementation is not.
- **GATED** — do not activate the downstream product work until the named gate clears.
- **REVISIT** — no current work; reopen only on the focused owner's named trigger.
- **REJECT** — current evidence says not to pursue.
- **DONE** — the portfolio decision is complete; ordinary maintenance is not roadmap work.

## Current wedge

**Understand** remains the current wedge: help a person move from hearing something they care about to a supported musical understanding they can locate, inspect, verify, relate, and eventually act on.

The current portfolio has three simultaneous responsibilities:

1. keep improving the trust/representation substrate so product claims remain bound to exact evidence and Versions;
2. **increase evidence and relationship breadth quickly enough that the product can become musically useful across materially different Works**; and
3. learn from real product use which experimental capabilities deserve canonization, default routing, broader trust, or deletion.

The product-owner judgment as of 2026-09-04 is that the current evidence substrate is **too sparse for the dream Understand experience**. #1089 reached `INSUFFICIENT_EVIDENCE`; do not spend the next phase trying to rescue presentation with the same thin facts.

## Portfolio policy — breadth now, provenance always, defaults later

For reversible music-analysis capabilities, separate two decisions:

1. **Can this create a useful experimental product behavior now?**
2. **Should this become canonical/default/authoritative later?**

The first bar is intentionally much cheaper than the second.

### Experimental integration bar

A maintained OSS-backed capability may ship experimentally before broad benchmark/canonization work when:

- it unlocks a concrete musician-facing behavior;
- integration is bounded and operationally feasible;
- exact engine/package/model/version provenance is retained;
- its result remains isolated as its own immutable evidence/Version/artifact where appropriate;
- failure is explicit and does not contaminate stronger evidence;
- the UI/API communicates experimental/qualified status honestly;
- licensing permits the intended deployment mode;
- it does not weaken Version/provenance/auth/privacy contracts.

A capability does **not** need a broad held-out benchmark, canonical-winner decision, or default-routing decision before a user can try it experimentally.

### Canonization bar

Defaults, authoritative claims, broad trust domains, automatic routing, expensive always-on processing, and retirement of alternatives still require stronger evidence. Use real product usage plus focused evaluation to decide what should be promoted, narrowed, replaced, or deleted.

Preferred loop:

```text
think big
→ map broadly
→ integrate feasible capabilities quickly
→ expose honestly as experimental
→ learn from real use
→ evaluate only where a durable decision matters
→ canonize / delete later
```

Do not convert this into `run every model on every import`. Optional expensive analyses should normally remain user-triggered, independently runnable, independently fail-safe, and progressively disclosed.

## Opportunity hierarchy

1. **O1 — trustworthy inspectable musical objects.** Evidence/projection/Version authority remains non-negotiable.
2. **O1.5 — sufficient musical evidence and relationships.** The next major product bottleneck is not only correctness; it is whether the product knows enough useful things about real music to support deep understanding.
3. **O2 — coherent grounded understanding.** Revisit presentation once representative Works contain enough useful relations to sustain it honestly.
4. **O3 — explicit and discovered relationships.** User-chosen Compare remains valuable, but experimental recurrence/change/structure discovery no longer needs to wait for Compare if it can ship as a reversible qualified interpretation.
5. **O4 — the right abstraction for the question.** Compact task-shaped views remain useful candidates, especially when existing evidence can already support them.
6. **O5 — act on understood musical ideas.** Practice, performance, arrangement, transformation, and teaching interactions become more plausible as the evidence substrate expands.

## Portfolio

Horizons describe current investment posture, not a calendar.

### H1 — core: make Understand trustworthy **and musically sufficient**

#### Product / evidence programs

| Bet | Posture | Why now | Current decision / next action | Focused owner |
| --- | --- | --- | --- | --- |
| Deep musical-understanding frontier + rapid OSS integration queue | **ACTIVE** | The product now needs a much richer evidence/relationship substrate, not another presentation-only experiment. | Define the dream Lens × Product Mode frontier, map current gaps, maintain a broad OSS/method inventory, and activate 5–10 bounded experimental product capabilities. | [#1172](https://github.com/ListenCloser/listencloser/issues/1172) |
| Experimental-capability product/UX architecture | **ACTIVE** | Rapid breadth will create cognitive load unless capability discovery, processing, result placement, trust status, and alternate interpretations have a coherent product model. | Design `many capabilities; few concepts`: Processing/Add analysis as the likely control home, results placed by musician task, and experimental status/provenance progressively disclosed. | [#1173](https://github.com/ListenCloser/listencloser/issues/1173) |
| Grounded contextual Breakdown | **ACTIVE** | Supported grounded findings remain an important product primitive and proof layer. | Continue shipping useful supported observations through existing ranking/focus/evidence seams; low-value truth need not occupy primary UI. | [#588](https://github.com/ListenCloser/listencloser/issues/588) |
| Understanding-presentation probe | **DONE** — `INSUFFICIENT_EVIDENCE` | Current evidence density was too weak to distinguish narrative/guided presentation honestly across representative Works. | Do not implement another narrative/guided surface now. Revisit after the evidence/relationship substrate is materially richer. | [#1089](https://github.com/ListenCloser/listencloser/issues/1089) |

#### First experimental breadth lanes

These lanes are authorized for **bounded experimental product integration**, not automatic canonization. Focused owners must refresh their issue bodies to remove stale evaluation-before-exposure gates where they conflict with this roadmap, while preserving provenance and exact existing dependencies.

| Capability / relationship | Posture | Product value | Experimental direction | Focused owner |
| --- | --- | --- | --- | --- |
| Continuous pitch / expressive F0 | **ACTIVE** | Makes singing, bends, vibrato, fretless/expressive monophonic motion inspectable instead of forcing it into discrete MIDI. | Ship one maintained F0 path (e.g. PESTO/torchcrepe) as an experimental synchronized result; canonize later. | [#1087](https://github.com/ListenCloser/listencloser/issues/1087) |
| Measured change moments | **ACTIVE** | Gives a direct `where should I listen next?` interaction from evidence already in production. | Productize bounded change candidates from current perceptual evidence; no semantic `section/drop/climax` inflation. | [#848](https://github.com/ListenCloser/listencloser/issues/848) |
| Within-Work recurrence / similar moments | **ACTIVE** | Enables `where does something like this come back?`, one of the most general deep-dive relationships. | Start with transparent existing-stack recurrence/cross-similarity; label returned candidates as method-specific similarity, not motif/chorus truth. | [#812](https://github.com/ListenCloser/listencloser/issues/812) |
| Experimental structure map | **ACTIVE** | Functional/segment maps can immediately orient the listener and provide a new analysis lens even when imperfect. | Under #1172, create a focused owner for a current maintained structure candidate/control (including current All-In-One successor/port if viable); expose as an alternate interpretation with exact provenance. | [#1172](https://github.com/ListenCloser/listencloser/issues/1172) |
| Source/layer isolation + arrangement evidence | **ACTIVE** | Popular-music understanding repeatedly depends on vocals/drums/bass/layer entry/exit and isolation. Isolation itself is useful even before downstream claims are canonical. | Under #1172, create a focused owner for a maintained separator ecosystem; make stems optional/user-triggered and preserve source-model provenance. | [#1172](https://github.com/ListenCloser/listencloser/issues/1172) |
| Vocal/lead melody alternate interpretation | **ACTIVE** | General mixed-music understanding is weak when the product cannot trace the salient sung/played line. | Under #1172/#931 boundaries, integrate one production-eligible vocal/lead path as an alternate experimental interpretation without replacing canonical `auto` by default. | [#1172](https://github.com/ListenCloser/listencloser/issues/1172) |
| Symbolic deep-analysis enrichment | **ACTIVE** | Source-score/MIDI-bearing Works can become much deeper immediately using maintained symbolic-analysis libraries. | Reuse music21/Partitura and evaluate thin adapters such as musif/jSymbolic only where they produce a clear product behavior. Do not wait for audio-only parity. | [#1172](https://github.com/ListenCloser/listencloser/issues/1172) |
| Lyrics/voice alignment | **ACTIVE** | User-supplied lyrics aligned to audio unlock synced text, vocal navigation, and later flow/text↔music relations. | Find one lawful maintained aligner and ship only for user-supplied/licensed text; no implicit copyrighted lyric acquisition. | [#1172](https://github.com/ListenCloser/listencloser/issues/1172) |

#### Trust / representation enablers

These remain active because rapid breadth must not destroy source/provenance correctness.

| Enabler | Posture | Product reason / gate | Focused owner |
| --- | --- | --- | --- |
| Representation fidelity across Piano Roll / Score | **ACTIVE** | Core inspectable objects must preserve the right musical evidence rather than hide upstream errors. | [#498](https://github.com/ListenCloser/listencloser/issues/498) |
| Exact representation / Version authority | **ACTIVE** | New experimental outputs must coexist without kind/recency ambiguity or silently stealing authority from canonical evidence. | [#613](https://github.com/ListenCloser/listencloser/issues/613) |
| Representation-native evidence focus/projection | **ACTIVE** | A result should remain locatable/inspectable in its natural representation without inventing a second selection/focus model. | [#807](https://github.com/ListenCloser/listencloser/issues/807) |
| Product-shaped theory truth | **ACTIVE** | Framework-qualified theory remains useful, but experimental breadth must not silently promote oracle/theoretical output into universal fact. | [#1020](https://github.com/ListenCloser/listencloser/issues/1020) |
| Existing MusicXML as source-score evidence | **ACTIVE** | Authoritative written evidence immediately expands what the product can analyze and enables score/performance relations. | [#1082](https://github.com/ListenCloser/listencloser/issues/1082) |
| Score ↔ performance relation publication / first product proof | **GATED** | Alignment is already a strong maintained-OSS direction, but publication still depends on exact source/role authority and shared focus semantics. | [#1083](https://github.com/ListenCloser/listencloser/issues/1083) |

### H2 — adjacent jobs that can advance alongside breadth

| Bet | Posture | Why now | Next decision | Focused owner |
| --- | --- | --- | --- | --- |
| Explicit A/B Compare | **NEXT_PROBE** | Precise user-chosen comparison remains an important job independent of automatic discovery. | Test whether A/B interaction and bounded relations create value; experimental recurrence does not need to wait for this result. | [#1088](https://github.com/ListenCloser/listencloser/issues/1088) |
| Minimum useful abstraction (chord map vs lead sheet) | **NEXT_PROBE** | Compact actionable representations may outperform Score/Piano Roll for song-oriented jobs. | Continue the abstraction decision, but do not let a full evaluation program block low-risk experimental views once evidence is available. | [#1091](https://github.com/ListenCloser/listencloser/issues/1091) |
| Performance-expression evidence | **GATED** | Aligned timing/dynamics/articulation could make performance itself explainable. | #1083 must first provide a trustworthy exact-Version alignment path; then an experimental expression lane may ship before broad canonization. | [#1086](https://github.com/ListenCloser/listencloser/issues/1086) |

### H3 — later defaults / larger systems, but experimental slices may be allowed

The following remain gated as **large canonical systems/defaults**, while #1172 may still authorize small reversible experiments if they have a concrete product behavior and lawful provenance:

- **personal corpus / cross-Work retrieval:** no default embedding/vector-search architecture yet; a thin experimental text→passage or passage→passage interaction may be tested if it does not force a permanent storage/index choice;
- **multi-performance comparison / practice:** broad product mode waits on score↔performance alignment, though bounded alignment/following experiments may proceed through focused owners;
- **source-score OMR:** still gated until attached source scores prove enough value;
- **creative proposal / transformation loop:** still later as a broad product program; local counterfactual/isolation experiments may be useful proof actions;
- **broader publishing/corpus intelligence:** do not build a large platform before the Understand evidence substrate earns it.

## Portfolio dependency / sequencing notes

Only real decision dependencies belong here; experimental breadth should not be serialized by historical product-order assumptions.

- **Breadth and trust run in parallel.** #1172/#1173 and independent experimental capability lanes may advance while #588/#613/#807/#498 continue improving authority and fidelity.
- **Experimental exposure is not canonization.** A working experimental engine may be visible to users while still excluded from default routing or authoritative Breakdown claims.
- **Compare no longer blocks reversible discovery experiments.** #1088 still owns explicit A/B desirability, but #812/#848/experimental structure may proceed independently because their outputs remain qualified and reversible.
- **Source/authority dependencies remain hard where semantically real.** #1082/#613/#807 still gate product-safe score↔performance publication and downstream #1086 expression work.
- **Do not auto-run the model zoo.** Expensive or domain-specific analyses should generally be opt-in and separately fail-safe.
- **Many capabilities, few concepts.** #1173 owns the UX pressure created by breadth; do not add one permanent top-level tab, card taxonomy, or settings concept per engine.
- **Runtime capability maturity is not product authority.** `capabilities.json` describes runtime exposure/maturity; the roadmap decides whether a product path is active, and provenance/trust UI must remain honest.

## How roadmap changes

A portfolio decision changes this file. A PR merge, benchmark result, or new implementation idea does **not** require a roadmap edit unless it changes a posture, gate, horizon, sequencing dependency, or next product decision.

When evidence changes one of those facts:

1. update this roadmap as the current portfolio authority;
2. update the focused issue body when its own posture/gate/decision contract changes;
3. leave detailed execution and live PR state in GitHub;
4. link to evaluation/capability authorities instead of copying their tables or runtime status here.

Issue comments and historical strategy threads are evidence/provenance, not a newer roadmap layer that overrides this file.
