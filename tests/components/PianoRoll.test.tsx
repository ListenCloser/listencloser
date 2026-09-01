import { render, screen } from "@testing-library/react";
import PianoRoll from "@/components/workspace/representations/PianoRoll";

const mockNotes = [
  { id: "c4", pitch: 60, start: 0, end: 0.5, velocity: 80 },
  { id: "e4", pitch: 64, start: 0.5, end: 1.0, velocity: 80 },
  { id: "g4", pitch: 67, start: 1.0, end: 1.5, velocity: 80 },
];

describe("PianoRoll", () => {
  it("renders without crashing with notes", () => {
    render(<PianoRoll notes={mockNotes} />);
    expect(screen.getByText(/3 notes/)).toBeInTheDocument();
  });

  it("renders empty state when no notes", () => {
    render(<PianoRoll notes={[]} />);
    expect(screen.getByText("No notes to display.")).toBeInTheDocument();
  });

  it("renders note labels on SVG", () => {
    render(<PianoRoll notes={mockNotes} bpm={120} />);
    expect(screen.getAllByText(/C4/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/E4/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/G4/).length).toBeGreaterThanOrEqual(1);
  });

  it("keeps the scalar-BPM timing scaffold conservative when no observed pulse exists", () => {
    const { container } = render(<PianoRoll notes={mockNotes} bpm={120} />);

    expect(container.querySelectorAll('[data-grid-kind="tempo-beat"]').length).toBeGreaterThan(0);
    expect(container.querySelector('[data-grid-kind="observed-beat"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-grid-kind="subdivision"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-grid-kind="measure"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-pitch-lane="octave-anchor"]')).toBeInTheDocument();
    expect(container.querySelector('[data-ruler-kind="elapsed-time"]')).toBeInTheDocument();
  });

  it("uses exact non-uniform observed beats and downbeats instead of the BPM scaffold", () => {
    const { container } = render(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        beatTimes={[0.12, 0.71, 1.42]}
        downbeatTimes={[0.12]}
      />,
    );

    const beats = [...container.querySelectorAll('[data-grid-kind="observed-beat"]')];
    expect(beats).toHaveLength(3);
    expect(container.querySelectorAll('[data-grid-kind="observed-downbeat"]')).toHaveLength(1);
    expect(container.querySelector('[data-grid-kind="tempo-beat"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-grid-kind="subdivision"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-grid-kind="measure"]')).not.toBeInTheDocument();

    const x = beats.map((line) => Number(line.getAttribute("x1")));
    expect(x[1] - x[0]).not.toBeCloseTo(x[2] - x[1], 5);
  });

  it("fails closed to the BPM scaffold for malformed observed pulse coordinates", () => {
    const { container } = render(
      <PianoRoll notes={mockNotes} bpm={120} beatTimes={[0.7, 0.2, 1.4]} />,
    );

    expect(container.querySelector('[data-grid-kind="observed-beat"]')).not.toBeInTheDocument();
    expect(container.querySelectorAll('[data-grid-kind="tempo-beat"]').length).toBeGreaterThan(0);
  });

  it("keeps active time visually distinct from selected notes", () => {
    const { container } = render(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        playheadTime={0.25}
        selectedNoteIds={["e4"]}
      />,
    );

    expect(container.querySelectorAll('[data-note-state="active"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-note-state="selected"]')).toHaveLength(1);
    expect(container.querySelector('[data-playhead="true"]')).toBeInTheDocument();
  });

  it("keeps the static note layer continuous while transport and selection overlays change", () => {
    const { container, rerender } = render(
      <PianoRoll notes={mockNotes} bpm={120} playheadTime={0} />,
    );

    const staticLayer = container.querySelector('[data-piano-roll-static-layer="true"]');
    const c4Base = container.querySelector('[data-note-base="true"][data-note-key="c4"]');
    const e4Base = container.querySelector('[data-note-base="true"][data-note-key="e4"]');
    expect(staticLayer).toBeInTheDocument();
    expect(c4Base).toBeInTheDocument();
    expect(e4Base).toBeInTheDocument();

    rerender(<PianoRoll notes={mockNotes} bpm={120} playheadTime={0.25} />);

    expect(container.querySelector('[data-piano-roll-static-layer="true"]')).toBe(staticLayer);
    expect(container.querySelector('[data-note-base="true"][data-note-key="c4"]')).toBe(c4Base);
    expect(container.querySelector('[data-note-state="active"][data-note-key="c4"]')).toBeInTheDocument();

    rerender(
      <PianoRoll
        notes={mockNotes}
        bpm={120}
        playheadTime={1.25}
        selectedNoteIds={["e4"]}
        selectionTimeRange={{ start: 0.55, end: 0.95 }}
      />,
    );

    expect(container.querySelector('[data-piano-roll-static-layer="true"]')).toBe(staticLayer);
    expect(container.querySelector('[data-note-base="true"][data-note-key="e4"]')).toBe(e4Base);
    expect(container.querySelector('[data-selection-range="true"]')).toBeInTheDocument();
    expect(container.querySelector('[data-note-state="selected"][data-note-key="e4"]')).toBeInTheDocument();
    expect(container.querySelector('[data-note-state="active"][data-note-key="g4"]')).toBeInTheDocument();
  });

  it("refreshes the static layer contents when the note source changes", () => {
    const { container, rerender } = render(<PianoRoll notes={mockNotes} bpm={120} />);
    expect(container.querySelectorAll('[data-note-base="true"]')).toHaveLength(3);

    const nextNotes = [
      ...mockNotes,
      { id: "c5", pitch: 72, start: 1.5, end: 2.0, velocity: 96 },
    ];
    rerender(<PianoRoll notes={nextNotes} bpm={120} />);

    expect(container.querySelectorAll('[data-note-base="true"]')).toHaveLength(4);
    expect(container.querySelector('[data-note-base="true"][data-note-key="c5"]')).toBeInTheDocument();
    expect(screen.getByText(/4 notes/)).toBeInTheDocument();
  });
});
