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
| Deep musical-understanding frontier + rapid OSS integration queue | **DONE** | #1172 established that the current OSS/method ecosystem is already rich enough to deepen ListenCloser materially. The bottleneck is bounded integration and product surfacing, not another evergreen candidate survey. | Research is complete. Preserve the full candidate matrix as provenance in #1172; execution now belongs to the focused first- and second-wave owners below. | [#1172](https://github.com/ListenCloser/listencloser/issues/1172) |
| Experimental-capability product/UX architecture | **ACTIVE** | Rapid breadth will create cognitive load unless capability discovery, processing, result placement, trust status, and alternate interpretations have a coherent product model. | Design `many capabilities; few concepts`: Processing/Add analysis as the likely control home, results placed by musician task, and experimental status/provenance progressively disclosed. | [#1173](https://github.com/ListenCloser/listencloser/issues/1173) |
| Piano Depth proving ground | **ACTIVE** | Solo piano is the highest-observability current domain for proving the complete Understand loop from faithful performance evidence through readable Score, inspectable objects/relations, and grounded verification. | Bias depth work toward piano while mixed-music breadth continues in parallel. Treat Score/MIDI as evidence coordinate systems, not universal product ontology. Generalize lineage/object/relation/time/provenance machinery, not Western/piano assumptions. Execute #1193 correction and #1194 object-first reductions; #1195 remains gated until its minimum integrated-proof inputs exist. | [#1192](https://github.com/ListenCloser/listencloser/issues/1192) |
| Grounded contextual Breakdown | **ACTIVE** | Supported grounded findings remain an important product primitive and proof layer. | Continue shipping useful supported observations through existing ranking/focus/evidence seams; low-value truth need not occupy primary UI. | [#588](https://github.com/ListenCloser/listencloser/issues/588) |
| Understanding-presentation probe | **DONE** — `INSUFFICIENT_EVIDENCE` | Current evidence density was too weak to distinguish narrative/guided presentation honestly across representative Works. | Do not implement another narrative/guided surface now. Revisit after the evidence/relationship substrate is materially richer. | [#1089](https://github.com/ListenCloser/listencloser/issues/1089) |

#### First experimental breadth wave

These focused lanes are authorized for **bounded experimental product integration**, not automatic canonization.

| Capability / relationship | Posture | Product value | Experimental direction | Focused owner |
| --- | --- | --- | --- | --- |
| Continuous pitch / expressive F0 | **ACTIVE** | Makes singing, bends, vibrato, fretless/expressive monophonic motion inspectable instead of forcing it into discrete MIDI. | Ship one maintained F0 path (e.g. PESTO/torchcrepe) as an experimental synchronized result; canonize later. | [#1087](https://github.com/ListenCloser/listencloser/issues/1087) |
| Measured change moments | **ACTIVE** | Gives a direct `where should I listen next?` interaction from evidence already in production. | Productize bounded change candidates from current perceptual evidence; no semantic `section/drop/climax` inflation. | [#848](https://github.com/ListenCloser/listencloser/issues/848) |
| Within-Work recurrence / similar moments | **ACTIVE** | Enables `where does something like this come back?`, one of the most general deep-dive relationships. | Start with transparent existing-stack recurrence/cross-similarity; label returned candidates as method-specific similarity, not motif/chorus truth. | [#812](https://github.com/ListenCloser/listencloser/issues/812) |
| Experimental structure map | **ACTIVE** | Functional/segment maps can immediately orient the listener and provide a new analysis lens even when imperfect. | Integrate one current maintained structure candidate/control as a qualified alternate map with exact source/engine provenance. | [#1175](https://github.com/ListenCloser/listencloser/issues/1175) |
| Source/layer isolation + arrangement evidence | **ACTIVE** | Popular-music understanding repeatedly depends on vocals/drums/bass/layer entry/exit and isolation. Isolation itself is useful even before downstream claims are canonical. | Make one maintained separator path optional/user-triggered; preserve stems and exact source/model provenance; do not make separation universal preprocessing. | [#1176](https://github.com/ListenCloser/listencloser/issues/1176) |

#### Second experimental breadth wave

#1172 shaped the next six opportunities. **Shaping does not mean starting all six implementation paths simultaneously.** Prefer the especially cheap/independent source-score, production/spatial, and supplied-lyrics lanes as capacity permits; drums/groove is somewhat heavier; singing-specific note transcription and learned retrieval remain gated on first-wave overlap becoming clear.

| Capability / relationship | Posture | Product value | Experimental direction / gate | Focused owner |
| --- | --- | --- | --- | --- |
| Source-score / trusted-MIDI symbolic detail | **ACTIVE** | Trusted written evidence can immediately answer richer questions about register, contour, interval motion, density, texture and voice motion. | Reuse music21 + Partitura first; do not wait for audio-only parity. Do not compete with #1082 / active source-score attachment ownership; consume exact symbolic roles once available. | [#1178](https://github.com/ListenCloser/listencloser/issues/1178) |
| Measured production / spatial lens | **ACTIVE** | Produced-music understanding needs literal loudness, stereo/spatial, spectral and transient change evidence, not only symbolic facts. | Start with existing librosa + pyloudnorm + transparent stereo/mid-side measures; expose method-qualified relations, not a descriptor dashboard or semantic adjectives. | [#1179](https://github.com/ListenCloser/listencloser/issues/1179) |
| Drum / groove evidence | **GATED** | Beat/downbeat alone does not explain drum patterns, bar recurrence, displacement or microtiming. | Begin after bounded integration capacity is available and one production-eligible drum-event checkpoint is license/runtime verified; align events to the exact Beat This pulse rather than creating another pulse authority. | [#1180](https://github.com/ListenCloser/listencloser/issues/1180) |
| User-supplied lyrics alignment | **ACTIVE** | Synchronized supplied text unlocks direct vocal navigation and later text↔beat/phrase relations. | Align only user-provided/licensed text to exact audio; no lyrics acquisition/scraping; preserve text/audio/model provenance and explicit failed/ambiguous spans. | [#1181](https://github.com/ListenCloser/listencloser/issues/1181) |
| Singing-specific note transcription | **GATED** | Singing→notes is a different contract from continuous F0 and could make the sung melodic line inspectable without pretending the general auto transcription is canonical for voice. | Do not create a parallel owner until #1087's first pitch-contour slice and #931's general-transcription boundary can be cleanly partitioned. GAME/current successors are candidate families, not a default decision. | [#1087](https://github.com/ListenCloser/listencloser/issues/1087) / [#931](https://github.com/ListenCloser/listencloser/issues/931) gate |
| Task-shaped learned retrieval | **GATED** | A concrete text→passage or cross-Work `find something like this` job could add value beyond within-Work recurrence. | Wait for #812's first Similar Moments slice to clarify the distinct residual job. If activated, use bounded local storage/indexing; historical #332 still forbids generic embedding/vector infrastructure merely because CLaMP3/CLAP-like models exist. | [#812](https://github.com/ListenCloser/listencloser/issues/812) gate; create a focused retrieval owner only after a distinct job is proven |

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

The following remain gated as **large canonical systems/defaults**, while focused owners may still propose small reversible experiments when they have a concrete product behavior and lawful provenance:

- **personal corpus / cross-Work retrieval:** no default embedding/vector-search architecture yet; a thin experimental text→passage or passage→passage interaction may be tested only after the distinct job is clear and without forcing a permanent storage/index choice;
- **multi-performance comparison / practice:** broad product mode waits on score↔performance alignment, though bounded alignment/following experiments may proceed through focused owners;
- **source-score OMR:** still gated until attached source scores prove enough value;
- **creative proposal / transformation loop:** still later as a broad product program; local counterfactual/isolation experiments may be useful proof actions;
- **broader publishing/corpus intelligence:** do not build a large platform before the Understand evidence substrate earns it.

## Portfolio dependency / sequencing notes

Only real decision dependencies belong here; experimental breadth should not be serialized by historical product-order assumptions.

- **Breadth and trust run in parallel.** Focused first-/second-wave owners and #1173 may advance while #588/#613/#807/#498 continue improving authority and fidelity.
- **Piano depth is a proving track, not a serialization gate.** #1193/#1194 and existing #498/#1178/#812/#1175 work may advance while mixed-music breadth continues. Do not require Score, MIDI, one melody, or Western-theory objects from non-piano domains. Activate #1195 only when its explicit current-main gate clears.
- **Experimental exposure is not canonization.** A working experimental engine may be visible to users while still excluded from default routing or authoritative Breakdown claims.
- **Compare no longer blocks reversible discovery experiments.** #1088 still owns explicit A/B desirability, but #812/#848/#1175 may proceed independently because their outputs remain qualified and reversible.
- **Source/authority dependencies remain hard where semantically real.** #1082/#613/#807 still gate product-safe score↔performance publication and downstream #1086 expression work; #1178 must not invent score/performance alignment while source-score ownership is in flight.
- **Do not auto-run the model zoo.** Expensive or domain-specific analyses should generally be opt-in and separately fail-safe.
- **Many capabilities, few concepts.** #1173 owns the UX pressure created by breadth; do not add one permanent top-level tab, card taxonomy, or settings concept per engine.
- **Do not activate every shaped lane at once.** Prefer independent low-lift lanes first; heavier/shared-runtime work should wait for available integration capacity and clean ownership seams.
- **Evaluate only when a durable decision exists.** Defaults, broad trusted claims, automatic routing, persistent learned-retrieval infrastructure, or retirement of alternatives may justify focused evaluation; experimental exposure by itself does not.
- **Runtime capability maturity is not product authority.** `capabilities.json` describes runtime exposure/maturity; the roadmap decides whether a product path is active, and provenance/trust UI must remain honest.

## How roadmap changes

A portfolio decision changes this file. A PR merge, benchmark result, or new implementation idea does **not** require a roadmap edit unless it changes a posture, gate, horizon, sequencing dependency, or next product decision.

When evidence changes one of those facts:

1. update this roadmap as the current portfolio authority;
2. update the focused issue body when its own posture/gate/decision contract changes;
3. leave detailed execution and live PR state in GitHub;
4. link to evaluation/capability authorities instead of copying their tables or runtime status here.

Issue comments and historical strategy threads are evidence/provenance, not a newer roadmap layer that overrides this file.
