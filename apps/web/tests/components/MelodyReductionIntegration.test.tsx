import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MelodyReduction from "@/components/workspace/inspector/MelodyReduction";
import type { Insight } from "@/lib/domain.types";

const mocks = vi.hoisted(() => ({
  setSelection: vi.fn(),
  setActiveRepresentation: vi.fn(),
  seek: vi.fn(),
  activeSourceRole: "original" as "original" | "score",
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: {
      selection: null,
      representations: [{
        kind: "piano_roll",
        label: "Piano Roll",
        sourceUrl: "",
        sourceLabel: "Transcription MIDI",
        confidence: null,
        provenance: "transkun",
        versionId: "midi-v1",
        notes: [
          { id: "source-note-1", pitch: 72, start: 1, end: 1.5, velocity: 80 },
          { id: "source-note-2", pitch: 74, start: 1.5, end: 2, velocity: 82 },
          { id: "later-note", pitch: 60, start: 9, end: 10, velocity: 70 },
        ],
      }],
    },
    setSelection: mocks.setSelection,
    setActiveRepresentation: mocks.setActiveRepresentation,
  }),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: {
      position: 1.25,
      activeSource: {
        id: "source-v1",
        label: mocks.activeSourceRole === "score" ? "Score" : "Original",
        url: "/source.ogg",
        kind: "audio",
        role: mocks.activeSourceRole,
      },
    },
    seek: mocks.seek,
  }),
}));

const insight = {
  id: "melody-1",
  version_id: "midi-v1",
  kind: "melody",
  claim: "Proposed melody",
  confidence: null,
  evidence: {
    heuristic: "lstom_biLSTM",
    notes: [
      { pitch: 72, start_seconds: 1.0001, end_seconds: 1.5001, velocity: 80 },
      { pitch: 74, start_seconds: 1.5001, end_seconds: 2.0001, velocity: 82 },
    ],
  },
  provenance: { engine: { engine: "lstom" }, method: "lstom_biLSTM" },
  span: { start_seconds: null, end_seconds: null },
} as unknown as Insight;

describe("MelodyReduction shared workspace integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.activeSourceRole = "original";
  });

  it("clicking one reduced note selects only the exact persisted Piano Roll note and navigates there", () => {
    render(<MelodyReduction insight={insight} />);
    fireEvent.click(screen.getByRole("button", { name: "Show C5 at 0:01 in Piano Roll" }));

    expect(mocks.setSelection).toHaveBeenCalledWith({
      noteIds: ["source-note-1"],
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    expect(mocks.setActiveRepresentation).toHaveBeenCalledWith("piano_roll");
    expect(mocks.seek).toHaveBeenCalledWith(1);
  });

  it("does not apply performance seconds or a performance playhead to Score playback", () => {
    mocks.activeSourceRole = "score";
    const { container } = render(<MelodyReduction insight={insight} />);
    fireEvent.click(screen.getByRole("button", { name: "Show C5 at 0:01 in Piano Roll" }));

    expect(mocks.setSelection).toHaveBeenCalledWith({
      noteIds: ["source-note-1"],
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    expect(mocks.setActiveRepresentation).toHaveBeenCalledWith("piano_roll");
    expect(mocks.seek).not.toHaveBeenCalled();
    expect(container.querySelector("[data-melody-playhead='true']")).not.toBeInTheDocument();
  });

  it("shares the current performance playhead while leaving playback ownership to transport", () => {
    const { container } = render(<MelodyReduction insight={insight} />);

    expect(container.querySelector("[data-melody-playhead='true']")).toBeInTheDocument();
    expect(container.querySelector("[data-melody-note-id='source-note-1']")).toHaveAttribute("data-playing", "true");
    expect(screen.queryByRole("button", { name: /Hear|Focus/ })).not.toBeInTheDocument();
  });
});
