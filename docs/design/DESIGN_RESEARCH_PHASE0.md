# Listen Closer visual identity / AI taste research — Phase 0

Status: **research, non-authoritative**  
Owner: #1143  
Scope: census, baseline, tooling evaluation, and research protocol only. No production visual direction is selected by this document.

## Why this exists

Listen Closer has accumulated multiple rounds of UX, visual-language, landing, favicon, empty-state, typography, and screenshot-review work. That history is useful evidence, but it does not establish that the current or historical aesthetic direction is the right brand.

The immediate objective is to improve the *process by which visual decisions are made* before doing another broad restyle.

The research question is:

> How should Listen Closer combine strong external references, agent design/taste skills, divergent concept generation, real rendered product states, and explicit critique so autonomous agents can produce distinctive visual work without falling into generic AI/SaaS patterns?

## Phase-0 principles

1. **Prior design is evidence, not doctrine.** Existing graphite/paper/brass, shared-musical-time, quiet-workspace, and Laws-of-UX conclusions may survive, change, or be rejected.
2. **Rendered output beats source-code confidence.** CSS diffs and green CI do not prove aesthetic quality.
3. **Reference reasoning beats reference cloning.** Capture why a reference works and what tradeoff it makes; do not copy screenshots or brand signatures.
4. **Divergence before convergence.** Require materially different art directions before selecting a system.
5. **Tools have roles.** A component catalog, a UX-pattern library, an agent skill, and a critique rubric solve different problems and must not be treated as interchangeable design authorities.
6. **Taste is partly negative knowledge.** Explicitly detect common generated-UI defaults and repeated visual tropes.
7. **Brand is broader than CSS.** Typography, voice, iconography, favicon/mark, composition, product imagery/data visualization, motion, material, density, and interaction character are one system.
8. **Product truth remains a hard constraint.** A beautiful marketing composition cannot fabricate measured musical evidence or imply unsupported state.

## Prior-design census

This table is deliberately provisional. The status describes how Phase 0 should treat the work, not whether the original work was good or bad.

| Source | What it contributed | Phase-0 treatment | Reason |
| --- | --- | --- | --- |
| #328 | broader workspace IA / selection-centric design hypotheses; Mobbin and 21st.dev named as references | **RETEST** | useful questions, but predates later product simplification and was never a completed brand study |
| #405 | visual R&D around shared musical time, evidence-linked interaction, anti-slop rules, expressive landing / quiet workspace | **KEEP AS EVIDENCE / RETEST** | unusually thoughtful exploration, explicitly historical and never a production merge candidate |
| #446 | typography/readability and small interaction craft improvements | **MECHANICAL FOUNDATION** | landed, concrete readability work; does not determine brand |
| #489 | product-native empty workspace replacing generic music-note clip art | **MECHANICAL FOUNDATION / RETEST VISUAL** | landed and improves product specificity, but its exact shared-time scaffold is still only one aesthetic hypothesis |
| #503 | editorial two-column landing with structural shared-time illustration | **RETEST** | substantial landing hypothesis; closed unmerged |
| #601 / #607 | attempted durable visual/interaction contract, later rejected as stale multi-topic docs | **SUPERSEDED AS AUTHORITY / KEEP AS EVIDENCE** | confirms that historical visual principles should not be automatically canonical |
| #680 | removed redundant workspace mark; unified canvas typography token use | **MECHANICAL FOUNDATION** | landed simplification/consistency independent of brand direction |
| #695 | brand/landing owner; graphite/paper/warm-neutral and real-demo quality gates | **RETEST** | useful framing and truth guardrails; current art direction is not assumed correct |
| #706 | more expressive graphite/paper landing iteration | **RETEST** | closed unmerged; useful candidate material, not a winner |
| #719 | two-stroke aperture + shared-time-axis favicon exploration | **RETEST** | small-size method was good; subjective identity direction was explicitly unresolved |
| #723 | retained Playwright visual-review screenshots in CI | **MECHANICAL FOUNDATION** | critical infrastructure for rendered review regardless of future aesthetic |
| #1064 | cognitive-load / Laws-of-UX rubric | **KEEP AS UX INPUT, NOT ART DIRECTION** | valuable interaction constraints; insufficient to establish visual identity |

## Existing mechanical assets worth preserving during research

Phase 0 should exploit rather than replace these:

- Playwright visual scenarios and retained screenshot artifacts from #723;
- desktop, constrained, phone and reduced-motion coverage where currently present;
- existing product truth rules around unsupported/unavailable evidence;
- stable product states that can be rendered consistently for A/B design comparison;
- existing typography/design tokens as a baseline to compare against, not as immutable style choices.

## External tool roles — initial matrix

This is an evaluation queue, not an adoption list.

| Tool / resource | Primary job | Promising use in Listen Closer | Failure mode to guard against | Initial posture |
| --- | --- | --- | --- | --- |
| Mobbin | shipped-product screen/flow reference corpus | study hierarchy, navigation, empty/loading states, responsive behavior, interaction patterns | copying a fashionable product's identity; treating screenshots as context-free solutions | **USE AS REFERENCE** |
| 21st.dev / 21st MCP | searchable React component/template/theme catalog + agent integration | find real implementation primitives after a design intent exists; inspect alternatives before inventing another component | component shopping determines art direction; fashionable effects leak into product; duplicate local primitives | **EVALUATE / implementation accelerator** |
| Anthropic `frontend-design` skill | agent instruction for intentional frontend aesthetics and implementation | raise generated-design floor; require explicit aesthetic thesis and deliberate typography/composition | a general-purpose skill cannot know Listen Closer's identity; may still rationalize first output | **EVALUATE** |
| Taste / design-taste style skills | negative constraints / anti-generated-UI critique | catch common AI defaults and force more deliberate geometry, type, palette and composition | overfitting to one author's taste; replacing generic defaults with a different generic house style | **EVALUATE AS CRITIC** |
| `/taste` / design-DNA extraction approaches | turn references into explicit design decisions and tradeoffs | document why chosen references work; create transferable constraints instead of pixel imitation | false precision; mechanically cloning extracted tokens | **HIGH-PRIORITY EVALUATION** |
| SuperDesign | divergent concept exploration / design canvas | force multiple materially different directions before code commitment | attractive speculative mockups detached from real product states | **EVALUATE FOR DIVERGENCE** |
| Vercel Web Interface Guidelines | implementation and interaction-quality audit | mechanical downstream review: focus, targets, forms, states, responsive behavior, copy clarity | mistaking product-specific Vercel preferences for universal brand rules | **ADOPT AS SECONDARY REVIEW INPUT** |
| existing Playwright visual suite | rendered product evidence | canonical before/after surfaces; compare direction consistency at known viewports | pixel-diff success mistaken for subjective quality | **KEEP / EXPAND** |

## Working tool architecture

Do not ask one model or one tool to `make it beautiful`.

Preferred research loop:

```text
current rendered product states
        +
curated external references
        ↓
design-DNA extraction / written critique
        ↓
explicit creative brief
        ↓
3+ divergent visual directions
        ↓
same surfaces rendered for every direction
        ↓
anti-slop + UX/mechanical critique
        ↓
human/product-owner comparative feedback
        ↓
selected/synthesized direction
        ↓
repo-native Listen Closer design skill/system
        ↓
bounded production implementation + screenshot review
```

### Separation of responsibilities

**Reference discovery** answers: what has already worked in real products / visual systems?

**Design-DNA extraction** answers: what decision makes this reference effective, and under what conditions?

**Divergent generation** answers: what substantially different Listen Closer-specific ways could satisfy the brief?

**Taste/anti-slop critique** answers: where did the generated output regress to generic patterns or decorative excess?

**UX/mechanical audit** answers: does the design remain operable, accessible and responsive?

**Visual regression infrastructure** answers: what pixels actually changed across real product states?

None of these alone answers: what should Listen Closer look and feel like?

## Current baseline capture contract

Before evaluating new directions, retain/produce screenshots for the same state matrix:

| Surface | Desktop | Constrained | Phone | Reduced motion | Notes |
| --- | --- | --- | --- | --- | --- |
| signed-out landing | required | optional | required | required | first-impression / brand surface |
| empty workspace | required | required | useful | n/a if static | first-use identity |
| populated workspace | required | required | required where product currently supports it | required for animated changes | core product visual system |
| Breakdown/evidence | required | required | useful | n/a | hierarchy, trust, density |
| Ask | required | required | useful | n/a | conversational product surface |
| processing/import | required | useful | useful | required when motion exists | state communication |
| favicon / mark | 16, 32, 64 px | n/a | n/a | n/a | silhouette + distinctiveness first |

Screenshots are evidence for critique, not design approval by themselves.

## Reference-corpus protocol

Target: 30–40 references, then 8–12 deep analyses.

Reference buckets:

1. **Music / audio / creative tools** — dense specialist interfaces, transport, visualization, creative focus.
2. **High-craft productivity / knowledge tools** — hierarchy, calm density, keyboard interaction, information architecture.
3. **Editorial / publishing** — typography, negative space, voice, narrative composition.
4. **Distinctive marketing / brand systems** — first impression, identity, product storytelling.
5. **Data / technical instruments** — precision, state, visualization, evidence without dashboard cliché.
6. **Marks / favicon systems** — memorable geometry at 16–32 px.

For every shortlisted reference, record:

- context / surface;
- exact decision we admire;
- hierarchy and composition;
- typography;
- palette/material ratios;
- shape/radius/border/shadow language;
- iconography/illustration/product imagery;
- density and whitespace behavior;
- motion/interaction character;
- copy voice;
- why it fits or conflicts with Listen Closer;
- what must **not** be copied.

A screenshot with no written reasoning is not a useful research artifact.

## Divergence requirements

At least three art directions must be materially distinct on more than palette.

Each direction must define and render:

- creative thesis;
- typography pairing / hierarchy;
- color/material system;
- geometric language;
- iconography / favicon hypothesis;
- workspace density and chrome;
- product visualization treatment;
- signed-out landing story;
- motion character;
- voice/copy examples;
- explicit anti-goals.

Use identical content/state when comparing directions so product differences do not masquerade as visual quality.

## Evaluation rubric

Use a 1–5 score only as a discussion aid; written rationale is required.

| Dimension | Question |
| --- | --- |
| Product specificity | Could this plausibly belong only to Listen Closer, or could the logo be swapped for any AI SaaS? |
| Memorability | Is there a small number of identifiable visual ideas that survive after closing the page? |
| Musical relevance | Does the aesthetic connect to listening/music without resorting to generic notes, equalizers or DAW cosplay? |
| Typography | Does type create hierarchy and character rather than merely remain legible? |
| Composition | Is hierarchy intentional across landing and workspace rather than a collection of components? |
| Material / color | Does the palette have an ownable role system and sufficient range without decorative noise? |
| Product continuity | Do landing, empty state and working product feel related without forcing identical expression levels? |
| UX clarity | Are primary tasks, state and hierarchy easier—not harder—to perceive? |
| Anti-template quality | Does it avoid common generated-interface defaults and trend mimicry? |
| Accessibility | Focus, contrast, motion, targets and responsive behavior remain sound. |
| Implementation fit | Can the direction be maintained cleanly in the current React/CSS architecture? |
| Truthfulness | Does visual emphasis avoid implying unsupported musical evidence/state? |

## Tool evaluation protocol

A tool is adopted only if it improves the **same fixed design task**.

For each candidate workflow:

1. provide the same product brief;
2. provide the same selected reference material;
3. target the same screen/state;
4. require the same implementation constraints;
5. render the result at the same viewport(s);
6. run the same critique rubric;
7. record meaningful differences in quality and maintenance cost.

Possible decisions:

- **ADOPT** — materially improves the workflow/output and should become part of normal agent design work;
- **USE AS REFERENCE** — valuable source material but not something agents should execute automatically;
- **OPTIONAL** — helpful for specific exploration/implementation jobs;
- **REJECT** — little incremental value, bad fit, or encourages undesirable convergence.

## Immediate execution order

1. Confirm no active open owner conflicts with #1143.
2. Inventory current design files/tokens and visual test states on `main`.
3. Finish primary-source research on the candidate open tools, including license/setup/agent integration.
4. Assemble the first reference corpus and write design-DNA notes.
5. Establish a fixed creative brief and evaluation surfaces.
6. Generate three divergent directions without modifying production runtime.
7. Present rendered comparisons for product-owner feedback.
8. Only then decide whether to supersede, rewrite, or close #695 and other historical direction issues.

## Non-goals for Phase 0

- no production landing redesign;
- no favicon merge;
- no new component framework;
- no broad CSS refactor;
- no fake demo music/evidence;
- no claim that an external skill is the product's designer;
- no canonical palette/font/mark decision yet.
