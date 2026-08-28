# Music Workspace — Product UI Design System

## Design intent

Music Lab is an **operate-mode music analysis workspace**, not a marketing dashboard and not a toy DAW. The interface should feel like a focused instrument for listening, comparing, inspecting, and understanding a piece of music.

The product should read as:
- precise rather than flashy
- calm rather than futuristic
- editorial rather than card-heavy
- musical rather than generic SaaS
- dense enough for serious work, but never visually noisy

The UI must privilege the music itself: waveform, piano roll, score, temporal evidence, and analysis are the visual center. Chrome is secondary.

## Anti-references

Do not introduce:
- purple gradients
- glassmorphism
- neon-on-black cyber aesthetics
- card grids inside cards
- oversized dashboard KPI tiles
- generic AI sparkle iconography
- excessive pills/chips
- decorative gradients without semantic meaning
- rounded containers around every region
- large marketing-style headings inside the workspace
- hidden critical controls that appear only on hover

## Visual direction

Use a warm-neutral dark workspace with quiet contrast and one restrained accent.

The closest product archetype is a modern creative tool: compact navigation, a broad central canvas, stable transport, subtle separators, and an inspector that feels integrated rather than modal.

### Palette

Core surfaces:
- canvas: `#11110f`
- shell: `#171714`
- raised: `#1d1d19`
- hover: `#25241f`
- strong surface: `#2b2a24`

Text:
- primary: `#f1efe8`
- secondary: `#b6b2a7`
- tertiary: `#817d73`

Borders:
- subtle: `rgba(241,239,232,0.07)`
- standard: `rgba(241,239,232,0.12)`
- strong: `rgba(241,239,232,0.20)`

Accent:
- primary: `#d6b56d` — warm brass / manuscript tone
- primary hover: `#e2c27e`
- soft: `rgba(214,181,109,0.12)`

Semantic:
- success: `#8fb58a`
- warning: `#d0a65f`
- danger: `#c9786f`

Do not use gradients for primary UI surfaces.

## Typography

Use the application sans stack unless a high-quality variable font is deliberately introduced. The hierarchy should come from weight, spacing, and density rather than extreme size changes.

- workspace title: 18–20px, 600
- section title: 13–14px, 600
- controls/body: 13px, 400–500
- metadata: 11–12px, 400–500
- monospace only for timestamps, numeric music metadata, and debug/evidence values

Avoid all-caps except tiny metadata labels where it materially improves scanability.

## Geometry

Creative-tool geometry should be compact.

- global radius: 7px
- small controls: 5px
- large floating panels only: 10px
- do not use pill radius unless the content is genuinely a chip/status

Primary spacing scale:
- 4, 6, 8, 12, 16, 20, 24, 32px

Borders and negative space should define regions more often than cards.

## Workspace architecture

Desktop target:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ compact top bar: product / piece title                    analysis · user │
├───────────────┬───────────────────────────────────────────┬────────────────┤
│ Library       │ representation nav                        │ Inspector      │
│               ├───────────────────────────────────────────┤                │
│ pieces        │                                           │ findings       │
│ import        │            MUSIC CANVAS                   │ evidence       │
│               │                                           │ ask            │
│               │                                           │                │
├───────────────┴───────────────────────────────────────────┴────────────────┤
│ playback source        waveform / scrub       transport       time         │
└────────────────────────────────────────────────────────────────────────────┘
```

### Top bar

Height: ~48px.

The left side should contain a small product mark and current piece. Do not display internal repo/product names such as `hello-ai`.

The right side should contain only global actions. `Analysis` should behave as a panel toggle when results exist; analysis progress should appear as restrained inline state, not as a large button.

### Library

The library is a navigator, not a dashboard card collection.

- desktop width: 220–248px
- separated from canvas by a 1px border
- compact rows (~42–48px)
- selected piece indicated primarily by surface + text contrast, not a glowing outline
- import action at top or bottom, visually stable
- destructive actions visible on selection/focus with an adequate click target
- track status should be terse and secondary

### Canvas

The canvas is the largest uninterrupted region.

Do not repeat the piece title in global chrome. Use a compact representation switcher for `Waveform`, `Piano roll`, `Score`, and `Spectrogram` inside the canvas.

The representation should not itself be wrapped in an ornamental card. Its natural surface can define the visual language:
- waveform: quiet charcoal background, warm-neutral waveform
- piano roll: editor grid, restrained note colors
- score: paper-like warm light surface inside dark workspace is acceptable
- spectrogram: scientifically legible palette, not decorative

### Representation navigation

Use a low-profile tab strip with 36–40px height. Active state should rely on text contrast and a small underline/indicator. Avoid large rounded tab pills.

`Compare` belongs in transport because it changes what the user hears; representation tabs change what the user sees.

### Inspector

Desktop inspector width: 300–340px.

It should be a persistent docked region rather than visually feeling like a modal overlay. Organize it as a scrollable reading surface with stable sections.

Analysis hierarchy:
1. concise interpretation / key findings
2. time-linked findings
3. evidence and confidence
4. deeper detail

Avoid repeating every value as a separate bordered card. Prefer grouped sections and rows. Confidence should be visually quiet unless it is low or disputed.

### Ask / AI

Ask should feel like a capability of the inspector, not a separate product. Prefer a collapsible section or inspector mode. Keep the conversation narrow, evidence-linked, and tied to the current piece/time range.

### Transport

Transport is a stable bottom bar, ~56px high. It is the strongest persistent control surface besides the canvas.

It should answer four things clearly:
- what source am I hearing?
- am I playing?
- where am I?
- can I switch/compare representations without losing position?

Use one primary play/pause control and compact adjacent controls. Tempo is not globally important enough to occupy persistent chrome unless relevant to the active task.

## Interaction and motion

Motion should clarify spatial changes, never decorate them.

- panel open/close: 160–220ms ease-out
- menus/popovers: subtle opacity + 4–6px translation
- hover transitions: 100–150ms
- do not animate layout continuously during playback
- respect `prefers-reduced-motion`

Buttons should use slight surface/contrast changes. Avoid scaling buttons on hover.

## Empty/loading/error states

Empty states should orient the user to the music workflow, not fill space with illustration.

Good empty-state structure:
- one sentence explaining the outcome
- one primary import action
- transcription mode as a secondary control
- supported formats in tertiary text

Loading existing music should preserve the workspace frame and show skeleton/progress inside the canvas instead of replacing the entire product with a floating status box.

Errors should appear next to the affected action/representation and preserve access to successfully created artifacts.

## Responsive behavior

Desktop is primary because the task is analysis-heavy.

- >= 1180px: library + canvas + inspector
- 820–1179px: library collapsible; inspector overlays/docks as needed
- < 820px: canvas primary; library and inspector become sheets; transport remains fixed and usable

Do not simply shrink three desktop columns onto mobile.

## Accessibility

- WCAG AA text contrast
- 40px minimum pointer target for primary controls
- visible focus ring using accent color at restrained opacity
- keyboard navigation for tabs, library, source picker, menus
- active representation and active playback source announced distinctly
- never encode confidence/status through color alone

## Component rules

Prefer reusable primitives for:
- `IconButton`
- `SegmentedControl` only where mutually-exclusive modes genuinely benefit from it
- `MenuButton`
- `PanelHeader`
- `Section`
- `EmptyState`
- `StatusText`
- `Tooltip`

Do not create a generic `Card` primitive and apply it to every region.

## Design QA gate

Before a UI PR is mergeable, review screenshots at 1440×900 and 390×844 and check:
1. Can the user identify the current piece, active representation, active playback source, and play state in <2 seconds?
2. Is the central music representation visually dominant?
3. Are there unnecessary cards, pills, gradients, or borders?
4. Does every persistent control earn its space?
5. Do loading/error/empty states preserve spatial stability?
6. Can Analysis and Library be opened/closed without losing playhead state?
7. Does the UI remain useful at the narrow viewport?


## V5 visual language — editorial instrument

V5 is a craft pass, not a new information architecture. The stable model remains **Library | music canvas | Inspector | Transport**. The visual goal is a professional editorial instrument: quiet chrome, highly legible state, and musical material that carries more visual weight than the application shell.

Reference synthesis for implementation agents:
- **Mobbin:** use mature creative/editor patterns for panel density, menus, loading, empty states, and persistent transport. Borrow interaction logic, not visual branding.
- **21st.dev:** prefer a small repeatable primitive vocabulary (tabs, menu/popover, tooltip, icon button, status, skeleton) over one-off controls.
- **Taste / Impeccable:** audit before decorating; remove generic AI-dashboard habits such as card grids, KPI tiles, gratuitous pills, gradients, glass, and decorative AI glyphs.
- **Emil Kowalski:** interaction quality comes from hover/press/focus behavior, menu geometry, state transitions, and restrained motion rather than ornamental animation.
- **awesome-design-md:** this file is authoritative for visual decisions. When implementation and this document disagree, update one deliberately rather than allowing silent drift.

### V5 surface hierarchy

1. **Music is brightest.** Score paper, waveform trace, notes, selections, and the active playhead carry contrast.
2. **Chrome is quiet.** Library, Inspector, toolbar, and transport use closely related warm graphite surfaces separated mostly by spacing and hairlines.
3. **Raised surfaces are rare.** Reserve elevation for menus, transient status, and true overlays. A section is not a card by default.
4. **Brass is interaction, not decoration.** Use the accent for active state, focus, selection, and primary actions; never as a background wash.
5. **Typography carries hierarchy.** Prefer size, weight, spacing, and muted text over borders and filled boxes.

### Analysis hierarchy

Analysis is an interpretation surface, not a detector dump:
1. a concise high-level summary grounded only in available evidence;
2. quiet inline metadata (key / tempo / meter) only when values exist;
3. notable time-linked moments;
4. collapsed supporting evidence.

Never render empty metadata boxes. Never show `—` as a KPI. Roman numerals and harmonic function require interpretable key context. Local melody events already promoted to Notable moments should not be duplicated as raw evidence merely because a detector emitted them.

### Ask hierarchy

Ask has no decorative AI logo. It is a contextual explanation/comparison tool. Starter prompts should change with selection state and teach the user what the capability is good at. The current recording, playhead, selection, and trusted analysis are implicit context.

### Playback and score

Playback source and representation are distinct, but their relationship must be obvious. The Score surface exposes a direct **Hear score** action when notation-derived audio exists. The score cursor follows shared transport time measure-by-measure: left-to-right within the active measure, then jumps to the next measure and follows the next system when notation wraps.

### Loading and availability

Progressive availability is preferred over a global blocking state. The workspace frame appears immediately; audio can become playable before analysis/score finishes. Controls must not imply readiness for data that is not loaded. Import is independent from opening an existing recording once the Library project itself is ready. Progress UI must stay within viewport bounds.

### Primitive discipline

Before adding a new control, reuse or extend an existing interaction pattern. Icon-only controls are acceptable only for universally recognized actions; otherwise add a visible label at desktop sizes and retain a tooltip/accessible name at compact sizes. Focus, hover, disabled, and selected states are part of the component contract, not optional polish.
