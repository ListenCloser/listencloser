# First executable design-tool experiment

Owner: #1143

This is the first bounded experiment after Phase-0 documentation. It is intentionally **not** a production redesign.

## Fixed target

Signed-out landing, because it combines:

- brand/first impression;
- typography;
- composition;
- product storytelling;
- visual metaphor/product imagery;
- CTA hierarchy;
- responsive behavior;
- motion/reduced motion;
- relatively little signed-in state complexity.

## Baseline

Render current `main` at:

- 1440×900;
- 390×844;
- reduced-motion desktop.

Also retain historical #503 and #706 render/source evidence as prior hypotheses, not baseline winners.

## Shared input packet

Every experiment receives:

1. `DESIGN_BRIEF_V0.md`;
2. the same 8–12 selected deep references or their design-DNA summaries;
3. the current landing screenshot(s);
4. current landing semantic content/auth constraints;
5. no fake musical evidence;
6. no production merge requirement;
7. requirement for at least 3 meaningfully different directions before choosing one.

## Run A — baseline agent

Use current repository context and the fixed brief only.

Purpose: establish what an ordinary capable coding/design agent produces without a specialized taste layer.

## Run B — frontend-design generation layer

Use the same input packet plus the selected frontend-design skill/guidance.

Purpose: measure whether explicit aesthetic-direction instructions materially change composition, typography and product specificity.

## Run C — generator + independent taste critic

Start from Run B directions, then run a separate anti-slop/taste critique pass.

The critic must:

- identify generated-template tells;
- identify decorative decisions that do not serve the product;
- flag typography/composition defaults;
- flag brand clichés;
- propose deletions or stronger alternatives;
- avoid imposing its own preset palette/layout.

Revise once from that critique and render again.

## Run D — divergent design tool

Use SuperDesign or an equivalent design-space tool if setup/license fit is acceptable.

Require:

- same brief;
- same references;
- ≥3 genuinely different compositions;
- no production code mutation;
- export/reimplementation sufficient to render the fixed evaluation surfaces.

## Optional Run E — 21st-assisted implementation

After one direction is chosen for implementation-quality comparison, use 21st search only for 1–2 specific primitives where a catalog implementation may be better than bespoke work.

Example legitimate questions:

- responsive CTA/interaction primitive;
- a specific visual transition;
- a layout/illustration primitive.

Not legitimate:

> Find a cool hero and make Listen Closer look like it.

Compare 21st-assisted implementation against repo-native implementation using the tool scorecard.

## Review output

Create one contact sheet / review artifact showing the same viewport for each direction with no winner label.

For each candidate provide:

- short creative thesis;
- 3 strongest design decisions;
- 3 risks;
- anti-slop critique result;
- scorecard;
- implementation/dependency notes.

The product-owner feedback request should be comparative and concrete, for example:

- Which direction feels most ownable?
- Which feels most musically relevant without cliché?
- Which typography/composition should survive even if the overall direction loses?
- Which feels too cold, too decorative, too `AI`, too DAW-like, too editorial, or too consumer?

Do not ask only `which one do you like?`.

## Circuit breakers

Stop a tool experiment when:

- it cannot produce output against the real brief/state;
- setup cost exceeds its plausible marginal value;
- licensing is unclear for the intended use;
- it repeatedly generates generic community-template composition;
- it requires introducing a production dependency to evaluate a research idea;
- its output cannot be inspected/rendered reproducibly.

`REJECT` is a successful research outcome.
