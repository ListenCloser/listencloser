# Current-main visual census checklist

Owner: #1143

Use current `main` as the implementation authority. Historical PR source is context only.

## Global foundations

Inventory:

- root/global CSS imports and cascade order;
- active design tokens / CSS variables;
- font loading and actual font roles;
- body/background/theme-color/color-scheme behavior;
- shared button, tab, menu, disclosure and form primitives;
- icon sources and custom iconography;
- radius / shadow / border patterns;
- animation/reduced-motion patterns.

Record:

- duplicate/competing values;
- values that appear semantic vs merely historical;
- where signed-out and signed-in visual ownership diverge;
- places where one-off CSS overrides obscure the actual system.

## Signed-out landing

Inventory:

- DOM owner/component;
- active stylesheet(s);
- headline/body/CTA copy;
- mark/favicon usage;
- background/illustration assets;
- responsive breakpoints;
- reduced-motion behavior;
- current visual tests/screenshots.

## Workspace shell

Inventory:

- header;
- library;
- canvas/representation area;
- representation tabs/toolbars;
- inspector;
- transport;
- current selected/focused state;
- mobile/constrained behavior.

Identify which styling choices are true cross-product primitives and which are local/historical.

## Representations

For Waveform / Piano Roll / Score / Spectrogram record:

- background/material;
- typography;
- semantic colors;
- playhead/selection/focus colors;
- labels/grid/axes;
- empty/loading/error/unavailable states;
- renderer-imposed constraints.

## Breakdown / Ask

Record:

- type hierarchy;
- disclosure hierarchy;
- cards vs flat grouping;
- evidence/provenance styling;
- action prominence;
- empty/loading/error states;
- density at real product content length.

## Empty / import / processing

Record:

- first-use visual;
- primary action;
- processing/readiness surfaces;
- status-copy hierarchy;
- whether visual identity survives before real musical data exists.

## Brand identity surfaces

Inventory:

- `app/icon.svg` / favicon;
- `BrandMark` if still used;
- product wordmark/name typography;
- metadata / browser title;
- auth/landing identity;
- workspace identity presence/absence.

## Screenshot coverage

Map each visual test to the state it proves and note gaps.

Required target matrix lives in `DESIGN_RESEARCH_PHASE0.md`.

## Output

The census should end with:

1. **current visual primitives worth preserving regardless of art direction**;
2. **historical styling accidents / duplicate authorities**;
3. **surfaces where visual change is low-risk**;
4. **surfaces where design is coupled to product semantics**;
5. **missing screenshot states required before candidate comparison**.

Do not refactor while performing the census.
