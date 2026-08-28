# V6 Reference Board — Music Workspace

This is the working reference board for the next visual-system pass. It is not a moodboard and it is not permission to copy another product. Every reference must answer a concrete product or interaction question.

## Goal

Move the workspace from “cleaned-up application UI” to a coherent **editorial music instrument**:

- professional without feeling enterprise-generic
- dense without feeling crowded
- contemporary without chasing visual trends
- musical content visually dominant over application chrome
- interactions understandable before tooltips
- progressive loading that preserves spatial stability
- one reusable component grammar instead of one-off generated controls

The stable architecture remains:

**Library | Music Canvas | Inspector | Transport**

V6 changes execution and consistency, not the core information architecture.

---

## How references are used

For every surface or interaction, collect references in this order:

1. **Mobbin — shipped product patterns**
   - Search for the underlying interaction problem, not for “music app”.
   - Extract what users have already been taught by mature products.
   - Prefer several examples and synthesize the recurring pattern.

2. **21st.dev — contemporary component executions**
   - Search for specific primitives: tabs, popovers, menus, tooltips, command interfaces, disclosure rows, sliders, progress, skeletons, compact inputs.
   - Review multiple visual directions before adapting anything.
   - Reuse implementation ideas, accessibility behavior, and micro-interactions; normalize all styling to our tokens.

3. **Creative-tool references — domain feel**
   - Figma, Ableton Live, Lightroom/Adobe creative tools, notation tools, and other professional editors.
   - Study density, panel hierarchy, canvas dominance, transport behavior, contextual controls, and selection semantics.

4. **Our design system — synthesis**
   - `DESIGN.md` is authoritative.
   - Never introduce a component because a reference looks fashionable.
   - Any imported/adapted pattern must use our spacing, typography, surface hierarchy, focus behavior, and color semantics.

---

# Reference families

## 1. Mobbin — pattern research

Source: https://mobbin.com/mcp

Mobbin's MCP/design library is useful because it exposes hundreds of thousands of shipped product screens to natural-language search. The important behavior for us is **pattern comparison**: ask for many examples of the same interaction, identify the recurring conventions, then map those conventions to our music workflow.

### Searches to run for V6

#### Library / asset browser

Search prompts:
- “desktop media library sidebar with compact rows and import action”
- “asset browser in professional editor with selected item and context menu”
- “file browser with processing state in a creative tool”
- “saved projects sidebar with rename delete and status”

Extract:
- selected-row treatment
- spacing/density
- placement of import/create
- destructive actions
- how processing/opening is communicated without turning every row into a status card

Apply to:
- `LibraryPanel`
- track row actions
- import/transcription-mode controls

#### Inspector / contextual properties

Search prompts:
- “right sidebar contextual inspector desktop editor”
- “properties panel with expandable sections and inline metadata”
- “analysis panel with overview details and evidence”
- “desktop inspector with tabs and dense text hierarchy”

Extract:
- section hierarchy
- use of dividers vs containers
- inline labels/value alignment
- disclosure density
- selected-object context
- empty/default state

Apply to:
- Analysis
- Ask
- selection scope
- supporting evidence

#### Transport / media controls

Search prompts:
- “desktop media player compact transport controls source selector loop”
- “audio editor bottom transport bar”
- “A B compare media player controls”
- “playback source selector desktop editor”

Extract:
- universal vs labeled icons
- time display hierarchy
- source-picker placement
- loop/selection semantics
- active-state treatment
- compare-mode discoverability

Apply to:
- `TransportBar`
- Original / Transcription / Score source picker
- loop / region controls
- Compare

#### Progressive loading

Search prompts:
- “desktop editor progressive loading skeleton existing document”
- “media processing progress while editor remains usable”
- “partial results loading in inspector”
- “background file processing status desktop app”

Extract:
- what remains interactive
- where progress appears
- what is skeletonized
- whether global blocking is avoided
- how failure of one artifact leaves successful artifacts accessible

Apply to:
- opening saved music
- transcription
- score generation
- analysis loading

#### Context menus / secondary actions

Search prompts:
- “compact desktop context menu professional app”
- “row actions menu asset browser”
- “popover selector desktop editor”

Extract:
- menu width and padding
- icon/text balance
- destructive action separation
- submenu avoidance
- keyboard/focus behavior

Apply to:
- Library row actions
- source selector
- Compare selectors
- future annotation actions

---

## 2. 21st.dev — component and modernization references

Sources:
- https://21st.dev/
- https://21st.dev/blog/mcp-ui-components
- https://21st.dev/blog/component-libraries
- https://21st.dev/blog/why-agents-invent-components

21st is not only an implementation shortcut. Use its catalog to compare modern component executions before we commit to one. It is especially valuable for the interaction details AI-generated apps usually get wrong: focus states, compact spacing, popover geometry, button states, loading polish, and motion.

### Component categories to mine

#### Tabs / segmented controls

Look for:
- compact tab strips
- underline or quiet-surface active states
- keyboard-friendly tab behavior
- no oversized pill containers

Use for:
- Waveform / Piano Roll / Score / Spectrogram
- Analysis / Ask

Reject:
- marketing-style animated tabs
- glow effects
- large rounded capsules

#### Menus and popovers

Look for:
- Origin UI / Base UI / shadcn-style menu patterns
- compact density
- good destructive-action separation
- visible focus and keyboard navigation
- subtle entrance motion

Use for:
- track actions
- source selector
- Compare A/B selector

#### Tooltips

Look for:
- fast, restrained tooltip timing
- clear keyboard behavior
- small readable surfaces

Use for:
- icon-only controls at compact breakpoints
- score controls
- less common transport actions

Do not use tooltips to rescue unclear primary controls.

#### Disclosure / accordion rows

Look for:
- flat disclosure rows separated by hairlines
- count metadata aligned quietly
- content that expands without becoming a card stack

Use for:
- Evidence groups
- deeper analysis details

#### Progress / skeletons

Look for:
- in-place skeletons
- slim progress bars
- activity indicators that do not block the full workspace

Use for:
- opening saved music
- loading analysis
- rendering score

Reject:
- animated gradient spectacles
- giant centered loading cards

#### Command/search interfaces

Keep as a future reference for:
- Library search
- “jump to moment”
- future command palette
- Ask shortcuts

Do not add a command palette in V6 solely because it is fashionable.

### 21st adoption rule

Before adding any adapted component:

1. check whether an equivalent already exists locally;
2. compare at least 3 candidate patterns;
3. choose based on interaction fit, not decoration;
4. normalize to our tokens;
5. preserve semantic HTML, keyboard handling, visible focus, reduced-motion behavior;
6. make the result a reusable local primitive instead of leaving copied one-off markup in the feature component.

---

## 3. Figma — persistent creative-tool hierarchy

Source: https://help.figma.com/hc/en-us/articles/360039832014-Design-Prototype-and-view-Code-in-the-Properties-Panel

Useful pattern:

- persistent navigation on the left
- broad uninterrupted canvas
- contextual properties/inspection on the right
- toolbar/primary interaction surface detached from content
- right panel changes meaning with current selection rather than opening a new page

### What to borrow

- Inspector is a **reading/control surface**, not a stack of cards.
- Selection changes Inspector context.
- Compact labels can be enabled where ambiguity is costly.
- Canvas content remains visually dominant.
- Global chrome is deliberately quieter than the object being edited.

### What not to copy

- design-object property density that does not map to musical interpretation
- tiny click targets simply because expert tools can get away with them
- Figma-specific floating toolbar arrangements without a music reason

---

## 4. Ableton Live — transport, browser, and follow behavior

Sources:
- https://www.ableton.com/en/live/learn-live/interface/
- https://www.ableton.com/en/live-manual/11/arrangement-view/

Useful patterns:

- stable, explicit transport
- browser and working canvas have distinct roles
- playback position is directly manipulable in the main content
- “follow” is a behavior users can understand as playback advances through a larger surface
- expert controls remain dense, but state is legible

### What to borrow

- transport state should be obvious without reading help text
- clicking musical content should seek predictably
- playback-follow is different from selection
- larger temporal surfaces should follow the active playhead without continuously reflowing layout
- source/representation switching should preserve position

### Apply to Score

- cursor travels through current measure only
- at barline it moves to next measure
- when notation wraps, follow jumps to next system
- selection and playback cursor remain separate concepts

### What not to copy

- DAW complexity that our analysis product does not need
- icon-only expert controls when a visible label would reduce ambiguity for our broader audience

---

## 5. Linear and modern productivity tools — restraint, not identity

Linear-style products are useful only as references for interaction polish:

- consistent keyboard/focus behavior
- restrained surfaces
- compact menus
- fast transitions
- typography-led hierarchy

Do **not** make the product look like a generic dark Linear clone. Music representations, score paper, waveform, piano-roll grid, and time-linked evidence should create the product's identity.

---

# Surface-by-surface V6 direction

## Library

Target feeling: **asset navigator**, not dashboard.

- selected row uses quiet tonal contrast
- filename is primary, state is secondary
- import is obvious and stable
- advanced transcription profile is available but visually secondary
- row actions use one canonical menu
- no bordered card per track

## Representation toolbar

Target feeling: **view switcher**, not navigation tabs for separate pages.

- low height
- direct labels
- subtle active indicator
- no “More” for core views
- avoid pills

## Inspector

Target feeling: **editorial interpretation panel**.

Order:
1. Overview
2. trusted metadata
3. notable time-linked moments
4. deeper musical interpretation
5. collapsed evidence

Selection should alter context without replacing the entire information architecture.

## Ask

Target feeling: **contextual questioning mode inside the Inspector**.

- no AI brand glyph
- no chatbot hero state
- starter prompts demonstrate useful musical questions
- selection/time context is implicit
- composer remains visually quiet until used

## Transport

Target feeling: **instrument control surface**.

- Play/Pause visually primary
- source is always legible
- time is easy to scan
- loop and region controls have visible labels at normal desktop widths
- compare is understandable as listening A/B, not another representation mode

## Waveform

Target feeling: **clean temporal overview**.

- lower visual noise
- selection/playhead highly legible
- avoid decorative dark gradients
- waveform itself should have enough contrast to feel like musical content

## Piano roll

Target feeling: **precision editor view**.

- one scroll model
- grid hierarchy at musically meaningful subdivisions
- notes visually dominant
- selection and playhead reuse the same temporal grammar as waveform/score

## Score

Target feeling: **notation document inside an editor**.

- score paper is allowed to be substantially brighter than chrome
- playback cursor is measure/system aware
- selection highlight stays inside actual measure geometry
- direct “Hear score” uses notation-derived audio
- no fake full-page vertical playback line

---

# V6 component shortlist

Create/normalize only when current code does not already provide a reusable equivalent:

- `IconButton`
- `LabeledIconButton`
- `Tooltip`
- `Menu` / `MenuItem`
- `Popover`
- `TabStrip`
- `DisclosureRow`
- `InlineMeta`
- `StatusText`
- `Skeleton`
- `ProgressBar`
- `InspectorSection`
- `TransportControl`
- `SourcePicker`

These are product primitives, not a generic component-library project. Avoid abstracting until at least two real surfaces need the same behavior.

---

# Reference-to-implementation checklist

Before implementing a V6 visual change:

- [ ] Name the product problem being solved.
- [ ] Collect at least 3 relevant shipped/reference examples when practical.
- [ ] Record the recurring behavior, not merely the visual style.
- [ ] Check 21st for contemporary implementations of the needed primitive.
- [ ] Check the repository for an existing primitive before creating another.
- [ ] Map the chosen behavior to our `DESIGN.md` tokens/rules.
- [ ] Implement all states: default, hover, pressed, selected, disabled, focus, loading/error when relevant.
- [ ] Verify keyboard and reduced-motion behavior.
- [ ] Capture before/after screenshots at 1440×900 and a narrow viewport.
- [ ] Confirm music remains visually dominant over chrome.

---

# Initial V6 implementation order

1. **Primitive audit + token normalization**
2. **Transport** — clearest state, source, loop/region, compare
3. **Inspector / Ask** — typography, evidence hierarchy, contextual interaction
4. **Library** — row density, import, menus, processing states
5. **Representation toolbar**
6. **Waveform / Piano roll / Score craft pass**
7. **Loading/error/empty-state consistency pass**
8. **Responsive/narrow-desktop pass**

The goal is not to make every surface more decorative. The goal is to make the whole application feel like it was designed by one team with one interaction grammar.