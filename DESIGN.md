# Listen Closer — Product UI Design System

## Authority

This file is the human-readable source of truth for Listen Closer's product UI.

- `DESIGN.md` owns intent, semantic roles, interaction conventions, and design constraints.
- `apps/web/src/app/tokens.css` owns the executable values for ordinary application chrome.
- `docs/adr/0012-oss-first-frontend-primitives.md` owns the generic frontend primitive strategy.
- Product-specific music renderers may use specialized palettes or geometry when the measured data requires it, but their surrounding controls and chrome follow this system.

When implementation and this document disagree, update one deliberately. Do not resolve drift by adding another late override stylesheet.

Temporary aliases in `apps/web/src/app/tokens.css` (`--ui-*`, older `--bg` / `--panel` / `--accent`, abbreviated spacing/type tokens, etc.) are migration compatibility for #1211 / #523, not a second permanent vocabulary. New code should prefer the canonical semantic token names.

## Design intent

Listen Closer is an **operate-mode music analysis workspace**, not a marketing dashboard and not a toy DAW. It should feel like a focused instrument for listening, comparing, inspecting, and understanding a recording.

The product should read as:

- precise rather than flashy;
- calm rather than futuristic;
- work-first rather than dashboard-like;
- musical rather than generic SaaS;
- dense enough for serious use without becoming visually noisy;
- expressive where identity matters, restrained where the user is working.

The music itself—waveform, piano roll, score, temporal evidence, structure, and analysis—is the visual center. Chrome is secondary.

## Anti-patterns

Do not introduce:

- purple/neon gradients or cyber aesthetics;
- glassmorphism;
- card grids inside cards;
- oversized dashboard/KPI tiles;
- generic AI sparkle iconography;
- excessive pills/chips;
- decorative gradients without semantic meaning;
- rounded containers around every region;
- large marketing-style headings inside the workspace;
- critical controls that exist only on hover;
- versioned visual generations such as `*-v7.css`, `*-polish-vN.css`, or V7/V8 class families;
- `transition: all`;
- feature-local reimplementations of commodity menu/dialog/select/tab/tooltip/focus behavior.

Prefer **delete → consolidate → group → progressively disclose** over adding another surface.

## Visual language

The current accepted direction is **graphite + lime action + mineral relation + neutral time**.

Color is semantic. Lime is not decoration: it identifies the primary action/focus state. Mineral tones describe relationships and analysis. Time/playback is intentionally neutral so transport state does not read as an alarm or call to action.

### Surfaces

Canonical executable tokens:

- canvas: `--surface-canvas` = `#0d100e`;
- chrome: `--surface-chrome` = `#111411`;
- panel: `--surface-panel` = `#151815`;
- raised: `--surface-raised` = `#1b1f1b`;
- hover: `--surface-hover` = `#202520`;
- strong surface: `--surface-strong` = `#262b26`;
- music canvas: `--surface-music` = `#0b0e0c`;
- deep music canvas: `--surface-music-deep` = `#080b09`;
- score paper: `--surface-paper` = `#efeee8`.

Prefer spacing and hairlines over nesting bordered cards. Raised surfaces are for menus, transient status, and genuine overlays—not every section.

### Text and lines

- primary text: `--text-primary` = `#eceee6`;
- secondary text: `--text-secondary` = `#b5bab1`;
- tertiary text: `--text-tertiary` = `#767d75`;
- subtle line: `--line-subtle` = `rgba(239, 241, 233, 0.075)`;
- strong line: `--line-strong` = `rgba(239, 241, 233, 0.14)`.

Typography, whitespace, and contrast should carry hierarchy before extra boxes or decoration do.

### Semantic color

- primary action/focus: `--action-primary` = `#dff45a`;
- primary hover: `--action-primary-hover` = `#efff86`;
- relationship/analysis: `--relation` = `#829d9d`;
- playback/time: `--time` = `#a8afa7`;
- destructive: `--intent-danger` = `#cf7770`;
- success: `--intent-success` = `#28745b`.

Never encode status, confidence, or availability through color alone.

Representation-specific data color is allowed when it improves legibility or carries measured meaning. It must not silently become a second application-chrome palette.

Do not use gradients for primary workspace surfaces or controls.

## Typography

Use the application sans face for workspace chrome and controls. The display serif may appear in intentionally editorial/identity-bearing surfaces such as landing composition; it is not the default application UI typeface.

Canonical type scale:

- `--type-xs`: 11px;
- `--type-sm`: 12px;
- `--type-base`: 13px;
- `--type-md`: 15px;
- `--type-lg`: 18px;
- `--type-xl`: 24px;
- `--type-2xl`: 32px.

Use restrained weight differences rather than extreme size changes. Monospace is for timestamps, measured numeric values, and other genuinely tabular/debug-like data—not ordinary prose.

Avoid all-caps except tiny metadata labels where it materially improves scanning.

## Geometry and spacing

Creative-tool geometry is compact and mostly rectangular.

Canonical radius scale:

- `--radius-sm`: 2px;
- `--radius-md`: 3px;
- `--radius-lg`: 4px;
- `--radius-pill`: only for content that is genuinely a chip/status.

Canonical spacing scale:

- 4, 8, 12, 16, 24, 32, 48, 64px (`--space-1` through `--space-8`).

Use arbitrary geometry only when a renderer, canvas measurement, or one-off composition has a concrete reason. Generic controls should consume system tokens.

## Workspace architecture

The stable information architecture is:

```text
Library | music canvas | Inspector
              |
          Transport
```

Desktop should privilege the central music canvas. Library and Inspector are supporting surfaces. On compact layouts, the canvas remains primary and support panels stage rather than shrinking all three columns together.

### Library

The Library is a navigator, not a dashboard collection.

- compact rows;
- selected recording signaled by surface/text hierarchy rather than glow;
- import remains stable and easy to find;
- status is terse and secondary;
- destructive actions have adequate targets and require confirmation or a safe Undo path;
- destructive controls must remain keyboard/focus discoverable, not hover-only.

### Music canvas

Do not wrap each representation in ornamental cards. Let its natural surface carry the visual weight:

- waveform: quiet dark field and neutral measured trace;
- piano roll: editor grid with restrained note semantics;
- score: warm light paper inside dark workspace is intentional;
- spectrogram: scientifically legible data palette, not decorative heatmap styling;
- structure/experimental maps: visually subordinate to the listening/selection model unless the user explicitly promotes them.

Representation navigation should remain low-profile. `Compare` belongs with hearing/transport because it changes what the user hears; representation tabs change what the user sees.

### Inspector

The Inspector is a reading/action surface, not a detector dashboard.

Default hierarchy:

1. one to a few musician-useful observations;
2. direct musical actions such as Hear / Loop / Focus / Compare where valid;
3. one proof/evidence disclosure level;
4. deeper provenance only when it adds genuinely new information.

Do not repeat a fact across cards, Details, Evidence, and domain sections. #1161 owns the detailed Inspector product contract.

### Ask

Ask is a capability of the Inspector, not a separate generic chatbot product. It shares the visible musical context/selection and should not duplicate workspace scope UI.

### Transport

Transport is the strongest persistent control surface besides the canvas. It must answer clearly:

- what am I hearing?;
- am I playing?;
- where am I?;
- what passage is selected/looped?;
- can I compare sources without losing position?.

Use one obvious play/pause action and compact adjacent controls. Playback/time state uses the neutral time role, not the primary-action accent by default.

## Primitive ownership

Follow accepted ADR 0012: **own the product; borrow the primitives**.

For new generic application controls, the default is:

- local shadcn-style component ownership in `apps/web/src/components/ui`;
- Base UI as the default underlying accessible primitive layer;
- existing Tailwind CSS v4 + CSS variables/tokens for styling.

Existing Radix usage may remain where already appropriate; Radix or React Aria may be used for a concrete better-fit requirement. Do not mix primitive bases casually or migrate a working control solely for aesthetic consistency.

Feature/product code should consume generic app-level controls from `apps/web/src/components/ui` rather than importing vendor primitives directly unless a documented capability exception requires it.

Generic primitive names/styles are feature-neutral. Avoid `piece-*`, `library-*`, `ask-*`, etc. inside reusable primitive anatomy.

Prefer established iconography for ordinary interface icons. Brand marks and genuinely music-specific symbols remain custom.

Do **not** create a generic `Card` primitive and apply it everywhere.

## Interaction and motion

Motion clarifies state/spatial changes; it does not decorate them.

- default fast transition: `--motion-duration-fast` = 150ms;
- use explicit transition properties, never `transition: all`;
- panel/menu movement should be short and restrained;
- do not continuously animate application layout during playback;
- respect `prefers-reduced-motion`;
- avoid scale-on-hover for ordinary buttons.

Dialogs, menus, tabs, selects, tooltips, disclosures, drawers/sheets, and focus management should inherit keyboard/pointer semantics from maintained primitives rather than feature-local browser logic.

## Content conventions

UI copy is part of the system.

- use the Unicode ellipsis `…`, not three periods `...`, when an ellipsis is semantically intended;
- use `…` for active loading/processing labels (`Importing…`) and for commands whose conventional label indicates a follow-up step;
- use CSS `text-overflow: ellipsis` for visual truncation; do not mutate the underlying content to fake truncation;
- buttons use clear verb/action labels;
- icon-only controls require an accessible name and should be reserved for familiar actions;
- errors live next to the affected action/surface and preserve access to successfully available work;
- loading and empty states are concise and spatially stable;
- implementation names, repo names, and engine jargon do not enter primary UI unless they are intentionally exposed configuration.

## Empty, loading, and error states

Empty states should orient, not decorate:

- one clear outcome/orientation statement;
- one obvious primary action;
- secondary configuration only when it affects the next operation.

Opening existing work should preserve the workspace frame. Progressive capability availability is preferable to replacing the whole product with a global loading surface.

Errors should be scoped to the failed operation/representation. A failed enrichment step must not hide successfully created durable artifacts.

## Responsive behavior

Desktop is primary because the task is analysis-heavy, but compact layouts must remain first-class.

- wide desktop: Library + canvas + Inspector;
- constrained desktop/tablet: support panels collapse/stage before the canvas becomes unusably narrow;
- phone: canvas first; Library and Inspector become temporary support surfaces; transport remains usable.

Do not simply shrink three desktop columns onto mobile.

Primary mobile controls should aim for ~44px touch geometry. All pointer targets must meet WCAG 2.2 AA target-size requirements or a valid exception.

## Accessibility

Accessibility is a component contract, not a later polish pass.

- WCAG AA text/control contrast;
- visible, unobscured `:focus-visible` state;
- keyboard-operable menus/dialogs/tabs/selects and other controls;
- explicit accessible names for icon-only controls;
- active representation and active playback source are distinct programmatic states;
- meaningful loading/error/status announcements;
- reduced-motion support;
- no critical primary action hidden exclusively behind pointer hover.

## Design QA gate

For a material UI change, review rendered evidence at representative desktop and phone widths plus any affected intermediate width. Screenshots belong in PR evidence, not committed product assets unless they are intentional fixtures.

Ask:

1. Can the user identify the active recording, representation, playback source, and play state quickly?
2. Is musical material visually dominant over chrome?
3. Are there unnecessary cards, pills, gradients, borders, or duplicate labels?
4. Does every persistent control earn its space?
5. Do loading/error/empty states preserve spatial stability?
6. Are focus, keyboard, touch, and reduced-motion states valid?
7. Is this using the canonical token/primitive owner, or adding another local styling dialect?
8. Did the change delete or consolidate superseded UI rather than leaving two permanent paths?

## Migration rule

#1211 and #523 are responsible for converging historical UI onto this contract. During migration:

- preserve working behavior while moving ownership;
- temporary aliases must name their retirement issue;
- delete superseded styles/components in the same slice when safe;
- do not add a new compatibility layer to avoid removing an old one;
- specialized renderer overrides are allowed only where ordinary application tokens cannot own the integration cleanly.
