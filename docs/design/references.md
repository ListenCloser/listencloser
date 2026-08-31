# Design references

> **Status:** discovery/reference material, not product or implementation authority.
>
> Root `DESIGN.md` owns the maintained visual and interaction contract. Use this page to research external patterns when a concrete design problem is open; use current product issues/PRs to decide what changes next.

## Reference rule

External products and component catalogs are evidence, not themes.

For a concrete interaction problem:

1. identify the user task/state that is unclear;
2. inspect several shipped/reference examples;
3. extract the recurring interaction behavior rather than copying styling;
4. check whether a local primitive already owns that behavior;
5. adapt the smallest useful pattern to `DESIGN.md` geometry, typography, focus, accessibility and motion;
6. validate the result in the actual music workflow and narrow viewport.

Do not maintain a design roadmap in this file. Do not introduce a component because it is fashionable.

## Mobbin — shipped interaction patterns

Use Mobbin to compare multiple real product examples for a **specific problem**, such as:

- compact asset/library navigation;
- contextual editor inspectors;
- media transports and source selection;
- row actions and destructive menus;
- progressive processing/loading inside an existing workspace;
- mobile drawers, sheets and contextual controls.

Useful questions:

- What stays persistent while context changes?
- Which actions are visible versus secondary?
- How are selected/processing/error states communicated without card clutter?
- What geometry and labels make an unfamiliar control understandable?

Do not search for a single "music app look" and copy it.

Reference: https://mobbin.com/

## 21st.dev — component execution reference

Use 21st.dev to inspect contemporary implementations and accessibility behavior for primitives such as:

- tabs;
- menus/listboxes/popovers;
- disclosure rows;
- tooltips;
- progress/skeletons;
- compact inputs and buttons;
- sheets/drawers.

Adoption rules:

- compare several implementations;
- classify the interaction correctly before choosing a primitive;
- preserve semantic HTML, keyboard behavior, visible focus and reduced-motion behavior;
- normalize styling to local tokens;
- prefer an existing local primitive over copied one-off markup;
- do not add a dependency solely for decorative motion or an indicator.

Examples of product-specific distinctions:

- representation switching is a content/view tab contract, not an action menu;
- playback source is a known-value selector, not a generic command menu;
- evidence rows are disclosure, not navigation cards;
- tooltips must not rescue an unclear primary action.

References:
- https://21st.dev/
- https://21st.dev/blog/component-libraries

## Figma and professional editor tools — workspace hierarchy

Useful pattern:

```text
navigation / assets | dominant canvas | contextual inspector
                         +
stable global/editor controls
```

Transferable lessons:

- canvas/content remains visually dominant;
- inspector changes with context without becoming a new page;
- navigation and object inspection have distinct roles;
- compact hierarchy can still have explicit labels and focus states;
- global chrome should be quieter than the thing being inspected.

Do not import design-tool property density that has no musical purpose or tiny expert-only click targets.

Reference: https://help.figma.com/hc/en-us/articles/360039832014-Design-Prototype-and-view-Code-in-the-Properties-Panel

## Ableton Live and music editors — transport and temporal behavior

Useful lessons:

- transport state is explicit and stable;
- browser/library and working canvas have distinct roles;
- musical content can be clicked/searched without losing playback context;
- follow-playhead behavior is different from user selection;
- dense controls work only when state remains legible;
- switching a view/source should preserve position unless the user explicitly changes it.

Do not import DAW complexity that does not serve listening, comparison, inspection or explanation.

References:
- https://www.ableton.com/en/live/learn-live/interface/
- https://www.ableton.com/en/live-manual/11/arrangement-view/

## Lightroom / creative tools — focused mobile workflows

Mobile creative tools are useful references because they do not shrink all desktop panels into one screen. They preserve the content object and stage supporting controls around the current task.

Use this together with `mobile-workspace.md` for drawer/sheet/focused-edit patterns.

Reference: https://helpx.adobe.com/lightroom/mobile/get-started/workspace-overview.html

## Apple platform guidance — mobile/accessibility baseline

For touch interfaces, prefer visible controls, sufficient target sizes, safe-area handling, keyboard/focus accessibility where applicable, and patterns that do not depend on hover.

References:
- https://developer.apple.com/design/human-interface-guidelines/
- https://developer.apple.com/design/human-interface-guidelines/accessibility

## Sonic Visualiser / notation / music-analysis tools

Use domain tools to study how evidence and time stay tied to the music:

- synchronized waveform/spectrogram/MIDI/annotation layers;
- multiple time resolutions;
- playback remains available during inspection;
- notation can be a document-like bright surface inside darker editor chrome;
- selection, playback cursor and evidence annotation are distinct concepts.

Reference: https://sonicvisualiser.org/features.html

## What not to copy

Across all references, reject patterns that conflict with `DESIGN.md`, especially:

- glassmorphism, neon/cyber aesthetics or decorative gradients;
- card grids inside a creative-tool workspace;
- oversized marketing headings;
- large pill navigation for core representations;
- hover-only critical actions;
- icon-only controls where labels materially reduce ambiguity;
- animated blobs/sliding effects that do not explain state;
- command palettes or abstraction layers added before product complexity needs them;
- a generic SaaS/Linear identity that visually overwhelms the music.

## Review checklist

Before shipping a reference-informed change:

- Does the change solve a named product problem?
- Is the behavior already owned by a local component?
- Did we inspect multiple reference examples where practical?
- Does the implementation follow `DESIGN.md` rather than the reference's branding?
- Are default, selected, hover/pressed, focus, disabled, loading and error states handled where relevant?
- Is keyboard/touch/reduced-motion behavior correct?
- Does the music remain more visually important than application chrome?
- Was the result checked at desktop and a narrow/mobile viewport?

A reference is useful only when it improves the actual Listen Closer interaction without becoming a second design system.