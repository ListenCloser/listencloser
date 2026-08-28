# Workspace Redesign V3 — Implementation Brief

Status: proposed design + implementation PR

## Why this redesign

The current product has the correct broad pieces — library, multiple representations, analysis inspector, and synchronized transport — but the visual system still behaves like an AI-generated dashboard rather than a focused music workstation.

The biggest problems are structural rather than decorative:

- the product chrome competes with the music canvas
- the palette leans heavily into purple/gradient conventions
- many controls are expressed as pills/cards instead of a compact creative-tool language
- loading and empty states interrupt spatial continuity
- the analysis surface reads as a separate panel full of UI rather than a layer of understanding over the music
- the library and representation controls do not yet feel like parts of one stable workspace
- the bottom transport is valuable but needs to become the clear persistent playback authority

The redesign should preserve functionality and data contracts while replacing the presentation architecture.

## Research synthesis

The redesign draws from several complementary sources rather than copying one visual style.

### Impeccable

Use the product as an `Operate` surface: density, stable navigation, readable states, quieter motion. Establish explicit `PRODUCT.md`/`DESIGN.md`-style context, audit generic AI UI patterns, then polish/harden rather than continuously inventing new local styles.

Applied here:
- design-system document committed to the repo
- no purple gradients / glassmorphism / card soup
- stable workspace frame
- restrained controls and state hierarchy

### Taste Skill

Use redesign-specific audit-first behavior: identify existing hierarchy and interaction problems before styling. Prefer deliberate layout variance and a recognizable visual direction over generic component-library defaults.

Applied here:
- redesign starts from workspace information architecture
- canvas gets much more visual weight than controls
- side panels behave as tool regions, not cards

### Emil Kowalski design engineering principles

Polish comes from interaction details: control sizing, predictable motion, obvious click targets, menus that feel anchored, and animation used only to preserve context.

Applied here:
- 40px minimum important click targets
- 160–220ms panel transitions
- no hover scaling
- spatially stable loading states
- focus and keyboard behavior included in acceptance criteria

### DESIGN.md ecosystem / awesome-design-md

Treat design rules as repository-level agent context, not tribal knowledge. Future coding agents should consume `DESIGN.md` before changing UI.

Applied here:
- root `DESIGN.md`
- concrete palette, geometry, hierarchy, anti-patterns, QA gate

### Mobbin / 21st.dev

Use them primarily as pattern catalogs, not as a source of a single aesthetic. Look for proven patterns for creative/editor products: slim toolbars, source pickers, docked inspectors, selection states, side sheets, overflow menus, and compact empty states.

Do not paste together unrelated components from the catalogs.

## Product concept

Think **music inspection desk**, not **AI music dashboard**.

The core user loop should be visually obvious:

```text
pick a piece → choose how to see it → listen/compare → inspect findings → ask deeper questions
```

Everything remains on one spatially stable screen.

## Desktop mock

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  ♪  Music Lab    /    reflets-dans-leau.m4a                         Analysis     • user │ 48
├──────────────────┬───────────────────────────────────────────────────┬────────────────────┤
│ Library          │ Audio   Piano roll   Score   More ▾     Compare   │ Analysis           │
│                  ├───────────────────────────────────────────────────┤                    │
│ + Import         │                                                   │ Overview           │
│                  │                   PIECE TITLE                     │ C major · likely   │
│ ● Reflets...     │                                                   │ 112 BPM            │
│   Transcribed    │              [ active representation ]           │                    │
│                  │                                                   │ Findings           │
│   Demo piano     │                                                   │ 0:14–0:22           │
│                  │                                                   │ Phrase intensifies │
│                  │                                                   │                    │
│                  │                                                   │ Evidence           │
│                  │                                                   │ ▸ Harmony          │
│                  │                                                   │ ▸ Melody           │
│                  │                                                   │                    │
│                  │                                                   │ Ask about this…    │
├──────────────────┴───────────────────────────────────────────────────┴────────────────────┤
│ Original ▾    |◀    ▶    ▶|       ━━━━━━━●━━━━━━━━━━     0:42 / 2:16      Compare A/B  │ 56
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key changes from current UI

1. **Palette reset** — warm charcoal + paper/brass accent; no purple gradient identity.
2. **Integrated header** — one compact top bar; project/piece hierarchy is quiet.
3. **Library becomes navigation** — flush left rail with compact rows, no floating card aesthetic.
4. **Canvas loses ornamental wrapper** — representations own the space.
5. **Tabs flatten** — low-profile text tabs rather than rounded pills.
6. **Inspector becomes docked reading/tool surface** on desktop.
7. **Transport becomes authoritative** — persistent, compact, obvious source + playback + time.
8. **Loading stays in place** — canvas skeleton/status rather than a centered standalone container.

## Mobile mock

```text
┌──────────────────────────────┐
│ ♪  Reflets…          ⋯   ◇  │
├──────────────────────────────┤
│ Audio  Piano  Score  More ▾ │
├──────────────────────────────┤
│                              │
│     active representation    │
│                              │
│                              │
├──────────────────────────────┤
│ Original ▾       0:42 / 2:16│
│      |◀     ▶     ▶|        │
└──────────────────────────────┘

Library → left/bottom sheet
Analysis → right/bottom sheet
```

The canvas remains the primary mobile surface. Do not make users horizontally navigate three columns.

## Visual mock tokens

```text
Canvas      #11110f
Shell       #171714
Raised      #1d1d19
Hover       #25241f
Text        #f1efe8
Secondary   #b6b2a7
Muted       #817d73
Accent      #d6b56d
Border      rgba(241,239,232,.12)
Danger      #c9786f
Success     #8fb58a
```

Use 7px default radius, not 16–22px. Reserve rounded rectangles for actual controls, not structural surfaces.

## Component-by-component implementation

### `app/globals.css`

Refactor design tokens first. Remove the existing purple gradient identity and reduce CSS duplication where possible.

Target:
- semantic CSS variables matching `DESIGN.md`
- smaller default radii
- no global gradient accents
- focus-ring variable
- compact control sizing
- panel/grid layout defined in one coherent workspace section

Do not attempt a giant unrelated CSS cleanup in this PR.

### `design/tokens.json`

Update to match the shipped V3 design tokens exactly. `DESIGN.md` is the intent document; `tokens.json` remains machine-readable values.

### `components/workspace/WorkspaceShell.tsx`

Refactor markup into clear regions:
- `studio-topbar`
- `workspace-library-region`
- `workspace-canvas-region`
- `workspace-inspector-region`
- `workspace-transport-region`

Desktop inspector should be docked. At narrower breakpoints it may overlay with backdrop.

Make header title hierarchy more useful:
- small product mark/name
- active piece belongs primarily to canvas title; do not repeat it loudly in both places

### `components/workspace/LibraryPanel.tsx`

Make rows compact and stable.

Requirements:
- >=40px action targets
- deletion/select controls do not require precision clicking
- selected state uses surface + type hierarchy
- immediate optimistic removal remains visible if already implemented
- avoid status-chip soup
- import is a clear action but not a giant CTA once the library has content

### `components/workspace/RepresentationStack.tsx`

This is the center of the redesign.

Changes:
- flatten piece title/header
- representation tabs become compact underline/text tabs
- keep `More` and `Compare`, but visually integrate them with the tab strip
- remove inline `style` from empty state and use system classes
- loading state should occupy the representation canvas dimensions without replacing the entire visual hierarchy
- no card wrapper around active representation

Keep all existing representation availability logic and compare behavior intact.

### `components/workspace/Inspector.tsx`

Visual restructuring only unless very small UX copy changes are required.

The information order should become:
1. Overview
2. Time-linked findings
3. Domain sections / evidence
4. provenance/confidence details
5. Ask entry point

Do not turn every insight into a card. Use separators, disclosure rows, and typographic hierarchy.

### `components/workspace/AskPanel.tsx`

Treat Ask as an inspector capability. Reduce chat chrome. The composer can stay fixed to the bottom of the inspector when Ask is active.

### `components/workspace/TransportBar.tsx`

Rebuild layout while preserving transport state semantics.

Desktop structure:

```text
[source picker]  [previous] [play/pause] [next]    [scrub/timeline]    [time]    [compare]
```

Requirements:
- source picker clearly names Original / Transcription / Score where available
- central play button is the strongest control
- timestamps use tabular/monospace numerals
- no redundant persistent BPM badge
- compare controls stay subordinate until compare mode is active

### Visualizations

`Waveform`, `PianoRoll`, `SheetMusic`, `Spectrogram` should each receive only enough styling to harmonize with the shell.

Do not rewrite visualization algorithms in this PR.

Waveform:
- eliminate overly dark isolated block feeling
- improve playhead contrast
- selection should be legible without a neon overlay

Piano roll:
- neutral grid
- notes use restrained semantic palette
- current time playhead should match transport accent

Score:
- warm paper surface is encouraged; it gives notation appropriate contrast against the workspace
- maximize usable score width

## Mock implementation page

Create `design/mockups/workspace-v3.html` as a static, dependency-free visual spec. It should show:
- populated desktop workspace
- open analysis inspector
- waveform or piano-roll facsimile
- transport
- representative library rows

Also add `design/mockups/workspace-v3-mobile.html` if doing so stays small. Static mockups are for visual communication only and must not become production dependencies.

If the implementation environment can run Playwright, capture PNGs into `docs/pr/workspace-redesign-v3/` and embed them in the PR description.

## Tests / verification

No merge based only on unit tests.

### Functional regression

Run existing tests covering:
- library selection/deletion
- representation switching
- compare mode
- transport source switching
- analysis panel open/close
- import empty state

### Browser scenarios

At minimum verify manually or through Playwright:

1. Empty workspace → import action visible and legible.
2. Loaded piece → switch Audio → Piano roll → Score without playhead reset.
3. Toggle Analysis while playing → playback position persists.
4. Collapse/reopen Library → active piece persists.
5. Enter Compare → switch A/B source → position persists.
6. Delete a non-active library item → row disappears immediately.
7. Delete active item → stale playhead/representation state does not remain.
8. 1440×900 screenshot.
9. 1024×768 screenshot.
10. 390×844 screenshot with usable transport and sheet-based side regions.

### Visual review checklist

Reject the PR if any are true:
- purple gradient remains as dominant identity
- canvas is visually smaller than side UI without functional reason
- more than two nested bordered surfaces appear around a representation
- active tabs are giant pills
- library actions have tiny hit targets
- analysis becomes a card grid
- transport source is unclear
- loading replaces the spatial frame
- narrow layout requires horizontal page scrolling

## Scope guardrails

This PR is allowed to make substantial frontend structural/CSS changes.

It should **not**:
- change analysis algorithms
- change transcription algorithms
- change database schema
- rewrite workspace stores unless required for responsive UI state
- invent new product concepts
- add large frontend dependencies solely for styling

21st.dev components may be adapted selectively if they reduce implementation cost and match `DESIGN.md`; do not introduce a component merely because it is visually impressive.

## Definition of done

This should feel like one coherent creative tool rather than multiple product features placed beside each other.

A successful first impression at 1440px is:

> “This is a music workspace. I can immediately pick a piece, inspect one representation, hear what I am looking at, and open analysis when I need it.”
