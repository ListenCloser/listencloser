# Design / AI-taste tooling research

Status: **Phase-0 research; non-authoritative**  
Owner: #1143  
Last updated: 2026-09-03

This document records what external tools are good for, not which aesthetic Listen Closer should adopt.

## Decision model

A tool is useful only if it improves one of these distinct jobs:

1. **reference discovery** — find relevant shipped patterns or visual systems;
2. **reference interpretation** — extract the decisions that make a reference effective;
3. **divergent exploration** — produce genuinely different directions before commitment;
4. **implementation sourcing** — reuse strong existing components/primitives rather than inventing another local version;
5. **critique / anti-slop** — identify generic generated-interface patterns and aesthetic regressions;
6. **UX / accessibility review** — catch interaction, responsive, focus and readability defects;
7. **rendered evidence** — inspect what actually ships rather than infer design quality from source.

No single tool should own all seven.

## Mobbin

**Role:** reference discovery / shipped-product interaction research.

Mobbin is most useful because it is a corpus of real product screens and flows rather than a gallery of isolated concept art. For Listen Closer, that makes it appropriate for studying:

- creative-tool workspace hierarchy;
- libraries / content selection;
- compact inspector patterns;
- processing and loading states;
- empty / first-use states;
- responsive transitions;
- onboarding/auth boundaries;
- command, search and selection patterns.

### Recommended use

Use Mobbin to answer bounded questions such as:

> How do high-craft creative/productivity tools keep a dense workspace visually calm?

or:

> How do products make one current object obvious while keeping a library available?

Do not search `music app` and copy the first visually similar product.

### Failure mode

Mobbin can create **precedent gravity**: because a pattern exists in a successful app, an agent may treat it as correct for Listen Closer. The research artifact must state the transferable decision and the mismatch as well as the similarity.

### Posture

**USE AS REFERENCE.** Do not add it as an automatic component or design authority.

---

## 21st.dev / 21st MCP

**Role:** implementation sourcing + optional divergent exploration.

Current 21st tooling is broader than a static gallery. Its agent/CLI workflow can search a large component catalog, inspect code, install components, generate variants, explore directions, review UI and publish a project's own theme/components.

This is promising for Listen Closer for two separate reasons:

1. **stop agents inventing commodity components** when a good accessible implementation already exists;
2. **show alternatives visually before code commitment**, especially for isolated interactions or marketing compositions.

### Best use

Use 21st only after the brief names the interaction or visual role. Example:

> We need a compact, keyboard-operable source selector consistent with our approved geometry and tokens. Search for structurally relevant implementations; do not import their visual theme wholesale.

Potential later use: publish a small set of **our own approved components/tokens** so agents retrieve Listen Closer's shipped primitives before community components.

### Failure modes

- component-shopping becomes art direction;
- fashionable shaders/gradients/docks/animated heroes create visual collage;
- copied registry code duplicates an existing local primitive;
- community component accessibility/maintenance quality varies;
- importing a component's dependencies costs more than rebuilding a simple primitive with the current stack.

### Evaluation

Compare a fixed UI task under:

- baseline implementation from current repo primitives;
- 21st search + adapt;
- 21st generated variants.

Measure product fit, code/dependency cost, accessibility, and whether it materially improves the rendered result.

### Posture

**EVALUATE / implementation accelerator.** Never make it art-direction authority.

---

## Anthropic `frontend-design` skill

**Role:** generation discipline / aesthetic floor.

The useful property of frontend-design style guidance is not a particular palette. It tries to prevent the model from defaulting to the statistical average of modern web design by requiring a deliberate aesthetic direction, stronger typography/composition choices, context-specific visual ideas, and finished frontend implementation.

### Recommended use

Evaluate as a **base generation skill** for visual prototype branches. Pair it with a Listen Closer brief and reference packet; never use it with only `make this prettier`.

The correct test is whether the same fixed brief produces:

- more intentional hierarchy;
- less default SaaS composition;
- stronger typography;
- fewer arbitrary decorative choices;
- better coherence across landing + workspace.

### Failure mode

A generic design skill can still confidently rationalize the first direction it generates. It raises the floor but does not supply product-specific taste.

### Posture

**EVALUATE.** Likely useful as a generation layer if comparative rendered evidence supports it.

---

## Taste / design-taste anti-slop skills

**Role:** critique / negative knowledge.

These skills are valuable because generated interfaces have recurring tells that can look locally polished while making the product anonymous:

- default purple/blue gradient hero treatment;
- rounded-card stacks for every information group;
- generic centered badge → huge heading → two CTAs → screenshot pattern;
- glassmorphism without product meaning;
- excessive pills and rounded rectangles;
- default neutral/slate palettes and generic sans typography;
- decorative background particles / glow / grid effects;
- feature-card triptychs;
- animation added as proof of polish rather than to communicate state.

### Recommended use

Run a taste/anti-slop critique **after** a direction is rendered. The critic should identify specific visual decisions that resemble generated defaults, then require the designer to defend, modify or remove them.

Keep the critic separate from the generator where possible. A single agent asked to generate and self-approve often explains away its own defaults.

### Failure mode

A strong anti-pattern list can become a new style preset: `never gradients`, `never cards`, `never centered type` is no better than blindly using them. The rule is **reject unearned defaults**, not ban entire techniques.

### Posture

**EVALUATE AS CRITIC.** Likely high leverage if kept product-agnostic and evidence-based.

---

## `/taste` / design-DNA extraction approaches

**Role:** reference interpretation.

This is one of the most strategically interesting ideas in the research set: instead of collecting inspiration screenshots, extract the **decision logic** of a reference.

Useful output is not:

```text
background: #111
radius: 12px
font: X
```

It is closer to:

```text
Context: dense expert workspace.
Decision: use near-flat surfaces with hierarchy driven primarily by typography + spacing.
Reason: preserves density without turning every group into a card.
Evidence: repeated across navigation, inspector and content surfaces.
Transfer to Listen Closer: potentially useful for Breakdown/Inspector.
Do not copy: brand typeface, exact palette, proprietary icon shapes.
```

### Recommended use

Deep-analyze only the strongest 8–12 references. Extract:

- hierarchy decisions;
- typography roles;
- density/negative-space strategy;
- color proportions and semantic use;
- geometry/radius strategy;
- product imagery/data visualization strategy;
- motion rules;
- copy voice;
- explicit tradeoffs.

Then synthesize across references. A one-off choice should not become a design principle just because one admired site uses it.

### Failure mode

Token extraction can create **false objectivity**: precise numbers look authoritative even when the transferable value was actually composition or hierarchy.

### Posture

**HIGH-PRIORITY EVALUATION.** The method is more important than any one implementation.

---

## SuperDesign

**Role:** divergent exploration.

SuperDesign's strongest conceptual value is forcing the workflow to remain in design space long enough to compare alternatives rather than immediately editing production code.

### Recommended use

Use for one bounded experiment:

- same Listen Closer brief;
- same reference packet;
- same target landing + workspace states;
- require three directions that differ in typography, composition, material and brand metaphor—not only palette;
- export or reimplement enough to compare rendered directions without changing production runtime.

### Failure mode

A visually attractive standalone mockup can ignore the real product's constraints and content density. Every candidate must eventually be judged using actual Listen Closer states, not only a concept canvas.

### Posture

**EVALUATE FOR DIVERGENCE.** Do not make generated canvas output production truth.

---

## Vercel Web Interface Guidelines

**Role:** UX / accessibility / implementation-quality review.

The guidelines are useful because they encode many small interface decisions that generated UI often misses, including:

- keyboard operation;
- visible/unobscured focus;
- focus management;
- hit-target sizing;
- mobile input behavior;
- interaction contrast;
- border/shadow/radius craft;
- color and chart accessibility;
- reduced browser/theme mismatch;
- clear/actionable copy and error recovery.

The project also exposes this guidance in a form intended for coding-agent review.

### Recommended use

Use as a **secondary mechanical audit after an art direction exists**. A direction that fails keyboard, focus, target-size or mobile behavior is not acceptable regardless of aesthetic quality.

### Failure mode

Some recommendations reflect Vercel's own brand/product choices rather than universal law. Do not import wording conventions or visual preferences simply because they appear in the guide.

### Posture

**ADOPT AS SECONDARY REVIEW INPUT**, with product-specific exceptions documented.

---

## Existing Listen Closer Playwright visual suite

**Role:** rendered evidence / regression.

This is already the most important internal tool in the stack. #723 ensures visual scenarios emit reviewable PNG artifacts independently of hosted Argos availability.

### Recommended use

Expand/standardize the screenshot matrix under #1143 so every serious visual direction renders the same product states and viewport sizes.

A design PR should eventually answer:

- What did the landing look like before/after?
- What did the core workspace look like before/after?
- Did the direction survive constrained width/mobile?
- Does the empty state belong to the same brand?
- Are Breakdown/Ask still legible at real density?
- Does reduced motion preserve the composition?

### Failure mode

Pixel stability is not taste. A perfectly stable ugly page passes visual regression. The screenshots must feed human/agent critique, not replace it.

### Posture

**KEEP / EXPAND.** This is the evidence layer for every candidate workflow.

---

## Proposed evaluation stack

The working hypothesis is not `pick one tool`; it is:

```text
Mobbin + curated web/reference research
          ↓
design-DNA extraction
          ↓
Listen Closer creative brief
          ↓
frontend-design-style generator
    + optional SuperDesign divergence
          ↓
real product-state renders
          ↓
Taste / anti-slop critic
    + Vercel mechanical UX audit
          ↓
product-owner comparative review
          ↓
approved system
          ↓
21st.dev / local component library for bounded implementation sourcing
          ↓
Playwright screenshot review on every production PR
```

This remains a hypothesis until the fixed-task comparison is run.

## First fixed-task comparison

Use the **signed-out landing** as the initial tooling benchmark because:

- it is currently perceived as one of the weakest surfaces;
- it allows stronger art direction without risking dense workspace usability;
- current and historical variants already exist for comparison;
- desktop + phone + reduced-motion screenshots already fit the existing test model;
- it exposes typography, composition, product storytelling, brand material, motion and CTA craft in one bounded surface.

### Constraints

The comparison must keep constant:

- product promise / factual claims;
- auth behavior;
- no fabricated musical evidence;
- same core CTA requirement;
- same desktop and phone viewport targets;
- accessible/reduced-motion behavior;
- no production merge from the experiment itself.

### Candidate workflows

A. baseline agent + current repo context only  
B. frontend-design-style generation + curated references  
C. B + explicit anti-slop critic/revision pass  
D. divergent concept workflow (SuperDesign or equivalent) + same references, followed by the same critique

Do not compare code verbosity or prompt cleverness. Compare rendered output and maintenance cost.

## Information still to collect

- exact OSS license / installation boundary for each candidate skill/repository;
- whether each tool is suitable for non-interactive CI/agent use;
- security implications of agent-installed community component code;
- whether 21st project libraries can be useful without adding an unnecessary external source of truth;
- whether a local repo-native skill can reproduce the valuable parts of third-party taste guidance after the research phase;
- concrete reference corpus and design-DNA artifacts;
- rendered fixed-task results.
