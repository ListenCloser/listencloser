# Mobile workspace

Status: V6 follow-up. This document defines the phone interaction model for the existing Library | Canvas | Inspector | Transport product architecture. It is not a separate product and it is not desktop squeezed into 390 px.

## Product stance

Desktop is a simultaneous workspace. Phone is a staged workspace.

On desktop, Library, musical representation, Inspector, and Transport can coexist. On a phone, one musical representation remains the primary surface and supporting surfaces temporarily take focus:

- **Canvas** is the default view and owns most of the screen.
- **Library** opens as a near-full-height drawer for choosing/importing recordings.
- **Analysis / Ask** opens as a bottom sheet above transport because it is vertically read and thumb-operated.
- **Transport** stays persistent and compact so playback never disappears while another surface is open.
- **Representation switching** remains directly available and horizontally scrollable.

Do not create a second mobile information architecture with different concepts. Adapt the same state and terminology to a touch-first presentation.

## Reference synthesis

### Apple HIG

- Use deliberately limited toolbar actions on iPhone rather than crowding every desktop command into chrome.
- Aim for 44 pt touch targets for primary controls and leave enough spacing to avoid accidental activation.
- Use standard visible triggers instead of interactions that depend on hover.

References:
- https://developer.apple.com/design/human-interface-guidelines/toolbars
- https://developer.apple.com/design/human-interface-guidelines/accessibility

### 21st.dev

21st's current mobile guidance is useful as interaction guidance, not an aesthetic to import wholesale:

- three to five persistent destinations at most;
- labels matter on touch because icon-only controls become a memory test;
- use `100dvh` for fixed-shell layouts;
- account for `env(safe-area-inset-bottom)`;
- bottom drawers map naturally to phone detail/supporting tasks;
- keep drawer focus and dismissal behavior explicit.

References:
- https://21st.dev/blog/react-mobile-navigation-components
- https://21st.dev/blog/react-modal-dialog-components
- https://21st.dev/community/components/s/drawer

### Lightroom mobile

Lightroom is a useful creative-tool precedent because it does not reproduce desktop panels simultaneously. It changes the visible tools according to the current task and uses focused edit/detail views on mobile.

Reference:
- https://helpx.adobe.com/lightroom/mobile/get-started/workspace-overview.html

### Ableton Note

Ableton treats mobile music work as a purpose-built sketch/capture environment that remains compatible with the desktop ecosystem rather than reproducing Ableton Live's full desktop layout. The lesson for us is to preserve the musical object and workflows, not every desktop panel arrangement.

Reference:
- https://www.ableton.com/en/note/manual/

### Mobbin research prompts

When authenticated Mobbin access is available, collect shipped examples for these problems rather than generic `music app` screens:

- mobile media editor persistent playback
- mobile asset/library drawer
- mobile inspector / properties bottom sheet
- mobile timeline or waveform selection
- mobile contextual toolbar
- mobile import/progress state
- mobile compare / source switching

For every example, record the task being solved, what transfers to our product, and what should *not* be copied.

## Breakpoint behavior

### >= 821 px — desktop

Keep the current three-surface editor shell and persistent transport.

### 601–820 px — compact/tablet

Keep Library and Inspector as edge drawers. Preserve enough canvas context to make the drawers feel contextual rather than modal.

### <= 600 px — phone

- Canvas is the only persistent content surface.
- Library uses an edge drawer with an explicit visible trigger.
- Inspector uses a bottom sheet above transport.
- Controls that are expected to be tapped should target roughly 44 px.
- Hover-only affordances are prohibited.
- Representation tabs remain direct, horizontally scrollable, and touch-sized.
- Transport accounts for safe-area inset and remains visible.
- Secondary playback actions may lose text labels when space is tight, but must keep accessible names and visible active state.

## Interaction contracts

### Library

- `Library` in the header opens/closes the drawer.
- Selecting a recording closes no state implicitly other than changing the active recording.
- Import remains a visible labeled action.
- A destructive row action must not require opening a one-item overflow menu.

### Inspector / Ask

- `Analysis` opens the bottom sheet when analysis is available.
- Analysis / Ask use the same shared tabs as desktop.
- The sheet can be dismissed by the explicit close/backdrop interaction; the canvas remains behind it.
- Sheet content scrolls independently from the musical canvas.

### Transport

- Play/Pause remains the primary control.
- Source selection remains available without leaving the current representation.
- Seek remains full-width enough to manipulate reliably.
- Loop/Region keep 44 px targets on phone even if their visible text is compacted.
- Home-indicator safe area is reserved; controls never sit underneath it.

### Score / waveform / piano roll

Do not build separate phone representations. Adapt viewport, zoom, follow, and selection behavior around the same synchronized transport and selection stores.

## Validation matrix

Every significant workspace visual PR should cover:

- 1440 × 900 desktop
- 1100 × 800 narrow desktop
- 768 × 1024 tablet/compact
- 390 × 844 phone

At phone width verify:

1. no horizontal page overflow;
2. Library is reachable without hover;
3. Analysis opens as a bottom sheet;
4. Play/Pause, source, seek, and loop are tappable;
5. representation tabs are reachable by horizontal scroll;
6. loading/progress UI stays within the viewport;
7. safe-area padding does not cover transport controls;
8. opening the software keyboard in Ask does not strand the composer behind fixed chrome.

## Non-goals for the first mobile pass

- native iOS/Android application;
- gesture-heavy DAW editing;
- a bottom navigation bar merely because it is fashionable;
- hiding core representations on mobile;
- replacing the synchronized transport architecture;
- reproducing all desktop Compare controls at once if the phone cannot present them clearly.
