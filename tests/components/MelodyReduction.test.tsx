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
    playbackRole: "original",
    canHear: true,
    selectedNoteId: null,
    onFocus: vi.fn(),
    onHear: vi.fn(),
    onSelectNote: vi.fn(),
    ...overrides,
  };
  render(<MelodyReductionObject {...props} />);
  return props;
}

describe("MelodyReductionObject", () => {
  it("renders a compact full-timeline lane and keeps technical detail secondary", () => {
    renderObject({ selectedNoteId: "note-c5" });

    expect(screen.getByRole("region", { name: "Experimental melody reduction" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /full Piano Roll timeline with 2 exact source notes/ })).toBeInTheDocument();
    expect(screen.getByText("Experimental")).toBeInTheDocument();
    expect(screen.getByText("2 proposed notes")).toBeInTheDocument();
    expect(screen.queryByText(/A method-specific proposed melodic line/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show C5 at 0:01 in Piano Roll" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByText("Details"));
    expect(screen.getByText("12345678-aaaa-bbbb-cccc-123456789012")).toBeInTheDocument();
    expect(screen.getByText("2/2 exact Piano Roll notes")).toBeInTheDocument();
    expect(screen.getByText(/not a verified melody label or top-voice rule/)).toBeInTheDocument();
  });

  it("lets each proposed note select its exact source note and lets the lane collapse", () => {
    const onSelectNote = vi.fn();
    renderObject({ onSelectNote });

    fireEvent.click(screen.getByRole("button", { name: "Show C5 at 0:01 in Piano Roll" }));
    expect(onSelectNote).toHaveBeenCalledWith(projection.notes[0]);

    fireEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByRole("img", { name: /Proposed melody reduction/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getByRole("img", { name: /Proposed melody reduction/ })).toBeInTheDocument();
  });

  it("keeps Focus and current-source hearing as short secondary actions", () => {
    const onFocus = vi.fn();
    const onHear = vi.fn();
    renderObject({ playbackRole: "transcription", onFocus, onHear });

    fireEvent.click(screen.getByRole("button", { name: "Focus" }));
    fireEvent.click(screen.getByRole("button", { name: "Hear transcription" }));

    expect(onFocus).toHaveBeenCalledOnce();
    expect(onHear).toHaveBeenCalledOnce();
  });

  it("disables Hear when there is no active playback source", () => {
    renderObject({ playbackRole: null, canHear: false });
    expect(screen.getByRole("button", { name: "Hear" })).toBeDisabled();
  });
});
