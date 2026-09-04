import type { ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MelodyReductionObject } from "@/components/workspace/inspector/MelodyReduction";
import type { MelodyReductionProjection } from "@/lib/melody-reduction";
import type { Insight } from "@/lib/domain.types";

const insight = {
  id: "melody-1",
  kind: "melody",
  claim: "Range: MIDI 72–74",
  confidence: null,
  evidence: {
    heuristic: "lstom_biLSTM",
    model_version: "1.0.0",
  },
  provenance: {
    method: "lstom_biLSTM",
    engine: { engine: "lstom" },
  },
  span: { start_seconds: null, end_seconds: null },
} as unknown as Insight;

const projection: Extract<MelodyReductionProjection, { status: "supported" }> = {
  status: "supported",
  sourceVersionId: "12345678-aaaa-bbbb-cccc-123456789012",
  startSeconds: 1,
  endSeconds: 2,
  notes: [
    { id: "note-c5", pitch: 72, startSeconds: 1, endSeconds: 1.5, velocity: 80 },
    { id: "note-d5", pitch: 74, startSeconds: 1.5, endSeconds: 2, velocity: 82 },
  ],
};

function renderObject(overrides: Partial<ComponentProps<typeof MelodyReductionObject>> = {}) {
  const props: ComponentProps<typeof MelodyReductionObject> = {
    insight,
    projection,
    pieceEndSeconds: 10,
    playheadSeconds: 0,
    selectedNoteId: null,
    onSelectNote: vi.fn(),
    ...overrides,
  };
  return render(<MelodyReductionObject {...props} />);
}

describe("MelodyReductionObject", () => {
  it("renders a compact musical lane with maturity and provenance kept secondary", () => {
    renderObject({ selectedNoteId: "note-c5" });

    expect(screen.getByRole("region", { name: "Experimental melody reduction" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /full Piano Roll timeline with 2 exact source notes/ })).toBeInTheDocument();
    expect(screen.getByText("Melody")).toBeInTheDocument();
    expect(screen.getByText("2 notes")).toBeInTheDocument();
    expect(screen.getByText("Experimental")).toBeInTheDocument();
    expect(screen.queryByText(/proposed notes/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show C5 at 0:01 in Piano Roll" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "About" }));
    expect(screen.getByText(/Version 12345678-aaaa-bbbb-cccc-123456789012/)).toBeInTheDocument();
    expect(screen.getByText("2/2 exact Piano Roll notes")).toBeInTheDocument();
    expect(screen.getByText(/not a verified melody label or top-voice rule/)).toBeInTheDocument();
  });

  it("lets each melody note locate its exact source note", () => {
    const onSelectNote = vi.fn();
    renderObject({ onSelectNote });

    fireEvent.click(screen.getByRole("button", { name: "Show C5 at 0:01 in Piano Roll" }));
    expect(onSelectNote).toHaveBeenCalledWith(projection.notes[0]);
  });

  it("shares performance playback position without introducing another playback control", () => {
    const { container } = renderObject({ playheadSeconds: 1.25 });

    expect(container.querySelector("[data-melody-playhead='true']")).toBeInTheDocument();
    expect(container.querySelector("[data-melody-note-id='note-c5']")).toHaveAttribute("data-playing", "true");
    expect(screen.queryByRole("button", { name: /Hear|Focus|Hide|Show$/ })).not.toBeInTheDocument();
  });

  it("withholds a performance-time playhead when the caller has no compatible timeline", () => {
    const { container } = renderObject({ playheadSeconds: null });
    expect(container.querySelector("[data-melody-playhead='true']")).not.toBeInTheDocument();
  });
});
