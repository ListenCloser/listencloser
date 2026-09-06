import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { REPRESENTATIONS } from "@/components/workspace/representations/registry";

const mocks = vi.hoisted(() => ({
  seek: vi.fn(),
  setSelection: vi.fn(),
  replaceSources: vi.fn(),
  chord: {
    id: "chord-c",
    version_id: "midi-v1",
    kind: "chord",
    claim: "C major",
    confidence: 0.9,
    evidence: {},
    provenance: { engine: "lv-chordia" },
    span: {
      start_seconds: 4,
      end_seconds: 6,
      start_beat: null,
      end_beat: null,
      start_measure: null,
      end_measure: null,
    },
  },
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: {
      representations: [{
        kind: "piano_roll",
        label: "Piano Roll",
        sourceUrl: "/performance.mid",
        sourceLabel: "Transcription MIDI",
        confidence: null,
        provenance: "test",
        versionId: "midi-v1",
        notes: [
          { id: "c4", pitch: 60, start: 4, end: 5, velocity: 80 },
          { id: "e4", pitch: 64, start: 5, end: 6, velocity: 82 },
        ],
      }],
      insights: [mocks.chord],
      selection: null,
      inspectorCollapsed: false,
    },
    setSelection: mocks.setSelection,
  }),
}));

vi.mock("@/lib/stores/timeline", () => ({
  useTimeline: () => ({ timeline: { bpm: 120 } }),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: {
      position: 0,
      isPlaying: false,
      activeSource: {
        id: "audio-v1",
        label: "Original",
        url: "/source.ogg",
        kind: "audio",
        role: "original",
      },
    },
    seek: mocks.seek,
    replaceSources: mocks.replaceSources,
  }),
}));

describe("Harmony lane shared workspace integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("seeks and selects the exact chord span without taking playback-source ownership", () => {
    const PianoRollView = REPRESENTATIONS.find((item) => item.id === "piano_roll")!.component;
    render(<PianoRollView active />);

    fireEvent.click(screen.getByRole("button", { name: /C major, 4\.00 to 6\.00 seconds/ }));

    expect(mocks.seek).toHaveBeenCalledWith(4);
    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 4, end: 6, domain: "performance" },
      provenance: { origin: "piano_roll", timeExact: true, measureApproximate: false },
    });
    expect(mocks.replaceSources).not.toHaveBeenCalled();
  });
});
