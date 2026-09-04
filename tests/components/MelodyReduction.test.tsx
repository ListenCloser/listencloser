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

describe("MelodyReductionObject", () => {
  it("renders exact-note musical geometry with explicit Experimental provenance", () => {
    render(
      <MelodyReductionObject
        insight={insight}
        projection={projection}
        playbackRole="original"
        canHear
        onFocus={vi.fn()}
        onHear={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: "Experimental melody reduction" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /2 exact source notes/ })).toBeInTheDocument();
    expect(screen.getByText(/Experimental · lstom/)).toBeInTheDocument();
    expect(screen.getByText(/not a verified melody label or a top-voice rule/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Inspect provenance"));
    expect(screen.getByText("12345678-aaaa-bbbb-cccc-123456789012")).toBeInTheDocument();
    expect(screen.getByText("2/2 persisted Piano Roll note entities")).toBeInTheDocument();
    expect(screen.getByText(/general piano and dense polyphony remain ambiguous/)).toBeInTheDocument();
  });

  it("exposes shared Focus and current-source Hear actions without implying isolated playback", () => {
    const onFocus = vi.fn();
    const onHear = vi.fn();
    render(
      <MelodyReductionObject
        insight={insight}
        projection={projection}
        playbackRole="transcription"
        canHear
        onFocus={onFocus}
        onHear={onHear}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Focus in Piano Roll" }));
    fireEvent.click(screen.getByRole("button", { name: "Hear transcription playback" }));

    expect(onFocus).toHaveBeenCalledOnce();
    expect(onHear).toHaveBeenCalledOnce();
    expect(screen.getByText(/does not synthesize or silently switch/)).toBeInTheDocument();
  });

  it("disables Hear when there is no active playback source", () => {
    render(
      <MelodyReductionObject
        insight={insight}
        projection={projection}
        playbackRole={null}
        canHear={false}
        onFocus={vi.fn()}
        onHear={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Hear current playback" })).toBeDisabled();
  });
});
