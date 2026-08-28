# 21st.dev V6 Component Shortlist

This is a concrete review list, not a dependency shopping list. We use 21st.dev to compare contemporary executions and accessibility contracts, then implement/adapt only the pieces that fit the Music Workspace design system.

## Decision rule

For each interaction:

1. classify the interaction correctly (content tab, value picker, action menu, disclosure, tooltip, etc.);
2. review several 21st examples;
3. choose the simplest behavior that fits the product;
4. normalize it to our typography, spacing, surfaces, focus states, and motion;
5. keep the final primitive local and reusable.

## Tabs

Primary references:

- https://21st.dev/originui/tabs
- https://21st.dev/community/components/explore/react-tabs
- https://21st.dev/community/components/jolbol1/tabs
- https://21st.dev/blog/react-tabs-components

### Adopt

- underline-style active state for **content/view switching**
- roving tabindex
- Arrow Left/Right and Home/End
- short, restrained transition
- scrollable strip at narrow widths rather than collapsing core views behind “More”

### Reject

- large pill/capsule tabs for Waveform / Piano Roll / Score / Spectrogram
- animated sliding blobs
- icon-only representation tabs
- Motion dependency solely for a tab indicator

### Applied in V6

`components/ui/TabStrip.tsx` is intentionally local and dependency-light. It is used for representation switching and Inspector mode switching so both surfaces share one keyboard and visual grammar.

---

## Known-value picker / playback source

Reference:

- https://21st.dev/blog/react-dropdown-menu-components

21st's current dropdown guidance usefully separates four different “dropdown” contracts. Playback source is **not an action menu**: it is one selected value from a small known set. That means selection must be remembered and keyboard movement must operate over options.

### Adopt

- trigger communicates current value
- selected option is visibly marked
- Arrow Down/Up opens and moves through options
- Home/End supported
- Escape closes and restores focus to trigger
- click-away closes without stealing subsequent focus
- menu surface is raised, but restrained

### Reject

- treating Original / Transcription / Score as generic menu actions
- searchable combobox for three items
- giant select field styling in the transport

### Applied in V6

`components/ui/ListboxMenu.tsx` replaces the one-off playback/Compare source popover and keeps the existing compact transport geometry.

---

## Action menus

References to review:

- Origin UI extended primitives: https://21st.dev/blog/origin-ui-components
- 21st navigation/menu collections: https://21st.dev/community/components/explore/navbar-react-components

Use for Library row actions only: rename, delete, future duplicate/export actions.

### Adopt

- compact vertical action menu
- keyboard navigation
- destructive action separated and semantically styled
- one canonical menu geometry shared across Library/context actions

### Reject

- reusing the playback-source Listbox contract for actions
- nested submenus for the current product surface area

---

## Disclosure / evidence rows

Review within Origin UI and minimal accordion/disclosure components.

Use for Analysis Evidence, where rows are information disclosure rather than card navigation.

### Adopt

- flat row + hairline separator
- chevron with restrained rotation
- count/metadata quiet and right-aligned
- content remains in the reading flow

### Reject

- accordion cards with individual backgrounds/borders
- large FAQ-style disclosure blocks

---

## Tooltip

Use sparingly for icon-only controls at compact breakpoints.

### Adopt

- concise label
- keyboard/focus support
- quick, non-theatrical appearance
- same visual surface family as menus

### Reject

- using a tooltip to explain a primary action that should have a visible label
- tooltip-only state information

---

## Command palette / action search

References:

- https://21st.dev/community/components/explore/react-command-palette
- https://21st.dev/blog/react-command-palette-components

**Not a V6 feature.** The current workspace does not have enough navigational/action complexity to justify Cmd-K. Keep this reference for future Library search, “jump to moment”, and larger editing workflows.

This is an explicit example of using 21st as a critique source rather than importing every fashionable pattern.

---

## Skeleton / progress

Review 21st progress and skeleton patterns only for micro-details.

### Adopt

- in-place skeleton matching final layout
- thin bounded progress
- stable workspace geometry
- partial readiness rather than global blocking

### Reject

- shimmer-heavy loading spectacle
- centered modal loading cards for normal document opening
- progress elements wider than their owning surface

---

## Visual filter for all 21st candidates

A candidate is a good fit if it feels:

- compact
- quiet
- keyboard-complete
- token-friendly
- dependency-light
- compatible with dense desktop editing

A candidate is a poor fit if its main appeal is:

- gradient/glow
- oversized rounded geometry
- springy marketing motion
- glassmorphism
- decorative iconography
- a novel interaction users must learn without musical benefit

The Music Workspace identity should come from the musical material and the relationship among waveform, piano roll, notation, timeline, selection, and interpretation—not from a recognizable third-party component aesthetic.
