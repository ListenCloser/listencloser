import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PassageCompare from "@/components/workspace/PassageCompare";
import type { MusicalSelection } from "@/lib/stores/workspace";

const mocks = vi.hoisted(() => ({
  workspace: {
    activeWorkId: "work-1" as string | null,
    representations: [
      {
        kind: "waveform" as const,
        versionId: "audio-version-1",
      },
    ],
    selection: null as MusicalSelection | null,
  },
  transport: {
    activeSource: {
      id: "audio-version-1",
      label: "Original",
      url: "https://example.invalid/original.wav",
      kind: "audio" as const,
      role: "original" as "original" | "transcription" | "derived" | "score",
    },
  },
  setSelection: vi.fn(),
  seek: vi.fn(),
  requestWorkspaceOrientation: vi.fn(),
  comparePerceptualSpans: vi.fn(),
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: mocks.workspace,
    setSelection: mocks.setSelection,
  }),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    seek: mocks.seek,
    transport: mocks.transport,
  }),
}));

vi.mock("@/lib/inspector/orientation", () => ({
  requestWorkspaceOrientation: mocks.requestWorkspaceOrientation,
}));

vi.mock("@/lib/relation-api-client", () => ({
  comparePerceptualSpans: mocks.comparePerceptualSpans,
}));

function selection(start: number, end: number): MusicalSelection {
  return {
    timeRange: { start, end, domain: "performance" },
    provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
  };
}

function supportedResponse() {
  return {
    status: "supported",
    evidence_report_version_id: "00000000-0000-0000-0000-000000000010",
    finding: {
      id: "relation-finding-1",
      source_relation_id: "00000000-0000-0000-0000-000000000020",
      kind: "perceptual_span_comparison",
      relation_kind: "compare",
      trust_class: "deterministic_derived",
      maturity: "production",
      subject_locator: {
        start_seconds: 10,
        end_seconds: 14,
        source_artifact_version_id: "audio-version-1",
        authority: "user_selected",
      },
      comparison_locator: {
        start_seconds: 20,
        end_seconds: 24,
        source_artifact_version_id: "audio-version-1",
        authority: "user_selected",
      },
      support_refs: [
        { type: "external", namespace: "perceptual_series", id: "report:rms" },
      ],
      measurements: [
        {
          support_ref: { type: "external", namespace: "perceptual_series", id: "report:rms" },
          feature: "rms",
          direction: "higher",
          summary: "Median RMS amplitude is 20.0% higher than in the comparison span.",
          unit: "linear_amplitude",
          normalization: "none",
          subject_value: 0.12,
          comparison_value: 0.1,
          delta: 0.02,
          components: [],
        },
      ],
      sufficiency: {
        gate: "USER_SELECTION_CAN_SUBSTITUTE_STRUCTURE",
        status: "supported",
        reasons: [],
      },
      headline: "The selected passages differ in measured perceptual evidence.",
      evidence_summary: "One promoted measurement supports this comparison.",
      available_actions: ["focus", "compare", "evidence"],
      provenance: {},
    },
    reasons: [],
  };
}

async function establishComparison() {
  const user = userEvent.setup();
  const view = render(<PassageCompare />);
  await user.click(screen.getByRole("button", { name: "Use selection as reference" }));
  mocks.workspace.selection = selection(20, 24);
  view.rerender(<PassageCompare />);
  await user.click(screen.getByRole("button", { name: "Check against selected passage" }));
  return { user, view };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.workspace.activeWorkId = "work-1";
  mocks.workspace.representations = [
    { kind: "waveform", versionId: "audio-version-1" },
  ];
  mocks.workspace.selection = selection(10, 14);
  mocks.transport.activeSource = {
    id: "audio-version-1",
    label: "Original",
    url: "https://example.invalid/original.wav",
    kind: "audio",
    role: "original",
  };
});

describe("PassageCompare truthfulness guards", () => {
  it("does not carry a supported finding onto a newly selected comparison passage", async () => {
    mocks.comparePerceptualSpans.mockResolvedValue(supportedResponse());
    const { view } = await establishComparison();

    expect(await screen.findByText("The selected passages differ in measured perceptual evidence.")).toBeVisible();

    mocks.workspace.selection = selection(30, 34);
    view.rerender(<PassageCompare />);

    expect(screen.queryByText("The selected passages differ in measured perceptual evidence.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeVisible();
  });

  it("focuses the exact performance selection without seeking notation-time Score audio", async () => {
    mocks.transport.activeSource = {
      id: "score-version-1",
      label: "Score",
      url: "https://example.invalid/score.wav",
      kind: "score",
      role: "score",
    };
    mocks.comparePerceptualSpans.mockResolvedValue(supportedResponse());
    const { user } = await establishComparison();

    await screen.findByText("The selected passages differ in measured perceptual evidence.");
    await user.click(screen.getByRole("button", { name: "Focus B" }));

    expect(mocks.seek).not.toHaveBeenCalled();
    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 20, end: 24, domain: "performance" },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    expect(mocks.requestWorkspaceOrientation).toHaveBeenCalledTimes(1);
  });

  it("does not imply terminal unavailable evidence will appear later", async () => {
    mocks.comparePerceptualSpans.mockResolvedValue({
      status: "unavailable",
      evidence_report_version_id: null,
      finding: null,
      reasons: ["no persisted perceptual evidence"],
    });
    await establishComparison();

    expect(await screen.findByText("Measured perceptual evidence is not available for this recording.")).toBeVisible();
    expect(screen.queryByText(/recording yet/i)).not.toBeInTheDocument();
  });
});
