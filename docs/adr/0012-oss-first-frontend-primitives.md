# 0012: OSS-first frontend primitives

Status: accepted
Date: 2026-08-30

## Context

ListenCloser has intentionally bespoke music interfaces, but its generic frontend infrastructure has also accumulated custom implementations of commodity web behavior.

Current examples include:

- `components/ui/ListboxMenu.tsx` implementing open/close state, outside-click detection, focus restoration, arrow/Home/End/Escape handling, disabled-option traversal, and listbox ARIA behavior;
- `components/ui/TabStrip.tsx` implementing roving focus and keyboard navigation;
- `components/ui/Tooltip.tsx` and associated CSS implementing tooltip behavior and layout;
- `lib/api-client.ts` layering custom cache revision/epoch/version-owner bookkeeping on top of TanStack Query;
- multiple global/versioned CSS layers loaded in `app/layout.tsx`, including `workspace-v3.css`, `product-polish-v4.css`, `visual-language.css`, and `readiness-polish-v6.css`;
- custom waveform, region/selection, timeline, audio decode/cache, spectrogram rendering, and FFT code even though mature audio-visualization OSS exists.

This is not uniformly bad code. The problem is ownership: generic browser interaction, accessibility, cache lifecycle, and visualization mechanics create maintenance cost without differentiating the product. In a repository developed by many parallel agents, bespoke primitives also encourage slightly different implementations of the same control and make design cleanup additive instead of convergent.

The product should remain bespoke where behavior is intrinsically musical: score and piano-roll interaction, cross-representation selection, evidence overlays, analysis presentation, source/version semantics, and music-specific transport behavior.

## Decision

Adopt the principle **"own the product; borrow the primitives."**

### Generic UI primitives

Use a maintained headless OSS primitive before implementing generic browser UI mechanics ourselves.

For new generic application controls, the preferred stack is:

- **shadcn/ui** as the local component/composition layer;
- **Base UI** as the default underlying accessible primitive layer;
- existing **Tailwind CSS v4 + CSS variables** for visual styling and design tokens.

Base UI is preferred for new migrations because it is unstyled, WAI-ARIA-oriented, handles keyboard/focus/pointer behavior, and is the current default base for new shadcn/ui projects. Radix or React Aria may be used when an existing component or concrete requirement makes them a materially better fit; do not mix bases casually.

Do not add bespoke implementations of dropdowns, selects, comboboxes, dialogs, tooltips, popovers, tabs, menus, switches, accordions, drawers, focus traps, roving tabindex, outside-click handling, or similar generic interaction systems unless an issue/PR documents why the standard primitive cannot satisfy the requirement.

ListenCloser owns the styling and composition. Adopting a primitive library does **not** mean adopting stock shadcn visual appearance.

### Server state

TanStack Query is the frontend owner of remote/server state: fetching, caching, invalidation, optimistic updates, polling, and mutation lifecycle.

Do not build a second cache protocol on top of it. Existing custom revision/epoch invalidation in `lib/api-client.ts` should be simplified incrementally into stable query keys, query/mutation options, explicit invalidation, and optimistic cache updates where needed.

Synchronous product state such as playback position, active representation, musical selection, panel state, and compare state remains client/domain state. Do not introduce another global-state dependency merely to replace small React contexts; evaluate one only when measured complexity justifies it.

### API contracts

Prefer the generated OpenAPI contract as the source for frontend request/response types. The target direction is a thin generated/typed client integrated with TanStack Query rather than parallel handwritten API contracts and request wrappers.

### Styling

Do not create new versioned global CSS override layers such as `*-v7.css` or `*-polish-vN.css`.

New design work should converge toward:

1. design tokens / CSS variables;
2. reusable primitive wrappers;
3. product-specific components;
4. page/workspace composition.

Existing global CSS layers should be consolidated opportunistically as touched, without combining visual redesign and broad stylesheet archaeology into one risky PR.

### Audio visualization

Do not add more bespoke generic waveform/spectrogram/FFT infrastructure before evaluating **wavesurfer.js** against the current product contract.

WaveSurfer already provides TypeScript-based waveform rendering/playback plus maintained Regions, Timeline, Spectrogram, Hover, Zoom, Minimap, and Record plugins. A replacement is not automatic: an evaluation must verify source switching without position loss, annotation/selection overlays, cross-representation synchronization, rendering latency, large-file behavior, accessibility hooks, testability, styling constraints, and bundle/runtime cost.

If adopted, WaveSurfer should own generic audio visualization/playback mechanics while ListenCloser continues to own musical selection, evidence, synchronization, and version/source semantics.

### Icons and other commodity assets

Prefer an established icon set for ordinary interface icons instead of repeated hand-authored SVGs. Brand marks and genuinely music-specific symbols remain custom. Choose the concrete icon dependency when the primitive migration begins rather than adding an unused package in this ADR.

## Evidence

- Base UI describes accessibility as a primary goal and implements ARIA attributes, role attributes, pointer interactions, keyboard navigation, and focus management: https://base-ui.com/react/overview/accessibility
- Base UI is unstyled/headless and supports Tailwind, CSS Modules, and plain CSS: https://base-ui.com/react/overview/about
- shadcn/ui made Base UI the default base for new projects in July 2026 while retaining Radix support: https://ui.shadcn.com/docs/changelog/2026-07-base-ui-default
- TanStack Query explicitly separates server state from synchronous client state and is intended to own async cache/update lifecycle: https://tanstack.com/query/latest/docs/framework/react/guides/does-this-replace-client-state
- wavesurfer.js v7 is TypeScript-based and exposes waveform playback plus Regions, Timeline, Spectrogram and other plugins: https://wavesurfer.xyz/docs/

Alternatives considered:

- **Continue custom primitives:** rejected as the default because accessibility/focus/menu mechanics are commodity complexity and repeatedly recreated by agents.
- **Radix as the new default:** still a valid mature choice, but shadcn now recommends Base UI for new work. Existing Radix usage would not need migration solely for consistency.
- **React Aria as the new default:** strong accessibility and now supported by shadcn, but there is no current product requirement that outweighs the simpler Base UI default. Revisit for controls where React Aria provides a clearly better fit.
- **Adopt a full styled design system:** rejected because ListenCloser needs a distinct creative-tool visual language rather than a framework's house style.
- **Adopt Zustand/Redux immediately:** rejected. First remove server state from local/global state and measure the remaining synchronous-state problem.
- **Replace waveform/spectrogram immediately:** rejected. The audio surface contains product-specific synchronization semantics and requires an equal-contract bakeoff before migration.

## Consequences

Positive:

- fewer homegrown accessibility and focus-management bugs;
- less generic frontend code to maintain;
- a smaller primitive vocabulary for parallel agents;
- redesign work changes tokens/components instead of adding cascade patches;
- clearer boundary between durable product IP and commodity frontend mechanics;
- server-state behavior converges on one cache/invalidation model.

Costs:

- existing primitives need incremental migration rather than a single rewrite;
- shadcn components live in the repository and still require disciplined ownership rather than blind generated-code accumulation;
- some Base UI abstractions may need thin ListenCloser wrappers to enforce design tokens and stable product APIs;
- WaveSurfer may prove unsuitable for some or all of the current visualization contract.

Migration must remain incremental. Do not churn a working primitive solely to satisfy this ADR while another active PR is editing the same surface.

## Revisit when

- Base UI becomes unmaintained or materially regresses accessibility/browser support;
- another primitive base demonstrably satisfies ListenCloser's interaction requirements better;
- the remaining synchronous workspace state becomes complex enough that a dedicated client-state library measurably simplifies the code;
- the WaveSurfer evaluation shows it cannot meet product latency/synchronization/accessibility requirements;
- a future frontend framework change makes these boundaries obsolete.
