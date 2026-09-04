import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MelodyReduction from "@/components/workspace/inspector/MelodyReduction";
import type { Insight } from "@/lib/domain.types";

const mocks = vi.hoisted(() => ({
  setSelection: vi.fn(),
  setActiveRepresentation: vi.fn(),
  seek: vi.fn(),
  play: vi.fn(),
  setActiveSource: vi.fn(),
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: {
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
      activeSource: {
        id: "original-v1",
        label: "Original",
        url: "/original.ogg",
        kind: "audio",
        role: "original",
      },
    },
    seek: mocks.seek,
    play: mocks.play,
    setActiveSource: mocks.setActiveSource,
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
  });

  it("Focus uses exact source note IDs and the existing Piano Roll representation", () => {
    render(<MelodyReduction insight={insight} />);
    fireEvent.click(screen.getByRole("button", { name: "Focus in Piano Roll" }));

    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 1, end: 2, domain: "performance" },
      noteIds: ["source-note-1", "source-note-2"],
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    expect(mocks.setActiveRepresentation).toHaveBeenCalledWith("piano_roll");
  });

  it("Hear seeks and plays the current Original without implicitly changing playback source", () => {
    render(<MelodyReduction insight={insight} />);
    fireEvent.click(screen.getByRole("button", { name: "Hear original audio" }));

    expect(mocks.seek).toHaveBeenCalledWith(1);
    expect(mocks.play).toHaveBeenCalledOnce();
    expect(mocks.setActiveSource).not.toHaveBeenCalled();
  });
});
