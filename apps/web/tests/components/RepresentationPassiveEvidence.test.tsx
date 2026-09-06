import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { REPRESENTATIONS } from "@/components/workspace/representations/registry";
import type { Insight } from "@/lib/domain.types";
import {
  WorkspaceProvider,
  useWorkspace,
  type RepresentationEntry,
} from "@/lib/stores/workspace";

vi.mock("@/components/workspace/representations/Waveform", () => ({
  default: ({ annotations = [] }: { annotations?: unknown[] }) => (
    <output data-testid="waveform-annotation-count">{annotations.length}</output>
  ),
}));

vi.mock("@/components/workspace/representations/PianoRoll", () => ({
  default: ({ annotations = [] }: { annotations?: unknown[] }) => (
    <output data-testid="piano-roll-annotation-count">{annotations.length}</output>
  ),
}));

vi.mock("@/components/workspace/representations/Spectrogram", () => ({
  default: ({ annotations = [] }: { annotations?: unknown[] }) => (
    <output data-testid="spectrogram-annotation-count">{annotations.length}</output>
  ),
}));

vi.mock("@/components/SheetMusic", () => ({
  default: ({ annotations = [] }: { annotations?: unknown[] }) => (
    <output data-testid="score-annotation-count">{annotations.length}</output>
  ),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: { position: 0, duration: 12, isPlaying: false },
    seek: vi.fn(),
  }),
}));

vi.mock("@/lib/stores/timeline", () => ({
  useTimeline: () => ({ timeline: { bpm: 120 } }),
}));

const representations: RepresentationEntry[] = [
  {
    kind: "waveform",
    label: "Waveform",
    sourceUrl: "/audio/source.wav",
    audioUrl: "/audio/source.wav",
    sourceLabel: "Original",
    confidence: null,
    provenance: "test",
    versionId: "audio-v1",
  },
  {
    kind: "piano_roll",
    label: "Piano Roll",
    sourceUrl: "/midi/source.mid",
    sourceLabel: "Transcription",
    confidence: null,
    provenance: "test",
    versionId: "midi-v1",
    notes: [],
  },
  {
    kind: "score",
    label: "Score",
    sourceUrl: "/score/source.musicxml",
    sourceLabel: "Score",
    confidence: null,
    provenance: "test",
    versionId: "score-v1",
    musicxml: "<score-partwise version=\"4.0\" />",
    measureStarts: [0, 4, 8],
  },
];

function boundedInsight(id: string, kind: string, claim: string): Insight {
  return {
    id,
    version_id: "audio-v1",
    kind,
    claim,
    span: {
      start_seconds: 2,
      end_seconds: 6,
      start_beat: null,
      end_beat: null,
      start_measure: null,
      end_measure: null,
    },
    entity_ids: [],
    evidence: {},
    confidence: 0.9,
    provenance: {},
    created_at: new Date().toISOString(),
    created_by: null,
    produced_by_job_id: null,
  };
}

const insights: Insight[] = [
  boundedInsight("rest-1", "rhythm_rests", "A clear rest"),
  boundedInsight("chord-1", "chord", "C major"),
];

function Harness() {
  const {
    workspace,
    replaceRepresentations,
    setInsights,
    toggleInspector,
  } = useWorkspace();

  return (
    <>
      <button
        type="button"
        onClick={() => {
          replaceRepresentations(representations);
          setInsights(insights);
        }}
      >
        Publish evidence
      </button>
      <button type="button" onClick={toggleInspector}>Toggle Inspector</button>
      <output data-testid="inspector-state">
        {workspace.inspectorCollapsed ? "collapsed" : "open"}
      </output>
      {REPRESENTATIONS.map((definition) => {
        const View = definition.component;
        return <View key={definition.id} active />;
      })}
    </>
  );
}

describe("passive representation evidence", () => {
  it("keeps passive locators projected when the Inspector is collapsed", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <Harness />
      </WorkspaceProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Publish evidence" }));

    expect(screen.getByTestId("inspector-state")).toHaveTextContent("open");
    expect(screen.getByTestId("waveform-annotation-count")).toHaveTextContent("2");
    expect(screen.getByTestId("piano-roll-annotation-count")).toHaveTextContent("2");
    expect(screen.getByTestId("spectrogram-annotation-count")).toHaveTextContent("2");
    expect(screen.getByTestId("score-annotation-count")).toHaveTextContent("2");

    await user.click(screen.getByRole("button", { name: "Toggle Inspector" }));

    expect(screen.getByTestId("inspector-state")).toHaveTextContent("collapsed");
    // The passive rhythm locator remains, while the secondary chord locator
    // follows the existing approximate-projection policy and stays opt-in.
    expect(screen.getByTestId("waveform-annotation-count")).toHaveTextContent("1");
    expect(screen.getByTestId("piano-roll-annotation-count")).toHaveTextContent("1");
    expect(screen.getByTestId("spectrogram-annotation-count")).toHaveTextContent("1");
    expect(screen.getByTestId("score-annotation-count")).toHaveTextContent("1");
  });
});