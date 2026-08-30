import { act, render, screen } from "@testing-library/react";
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
    activeSource: { role: "original" } as { role: string } | null,
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

// These fixtures characterize the dormant comparison implementation itself.
// Product exposure is covered separately; enable the capability explicitly so
// result-scoping behavior remains testable while Breakdown keeps it hidden.
vi.mock("@/lib/inspector/capabilities", () => ({
  isInspectorExposed: () => true,
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

async function captureAndSelectB(
  user: ReturnType<typeof userEvent.setup>,
  view: ReturnType<typeof render>,
) {
  await user.click(screen.getByRole("button", { name: "Use selection as reference" }));
  mocks.workspace.selection = selection(20, 24);
  view.rerender(<PassageCompare />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.workspace.activeWorkId = "work-1";
  mocks.workspace.representations = [
    { kind: "waveform", versionId: "audio-version-1" },
  ];
  mocks.workspace.selection = selection(10, 14);
  mocks.transport.activeSource = { role: "original" };
});

describe("PassageCompare result scoping", () => {
  it("does not carry a non-finding result onto a newly selected comparison passage", async () => {
    const user = userEvent.setup();
    mocks.comparePerceptualSpans.mockResolvedValue({
      status: "withheld",
      evidence_report_version_id: "00000000-0000-0000-0000-000000000010",
      finding: null,
      reasons: ["insufficient selected-span coverage"],
    });
    const view = render(<PassageCompare />);

    await captureAndSelectB(user, view);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));
    expect(await screen.findByText(/do not have enough validated evidence/i)).toBeVisible();

    mocks.workspace.selection = selection(30, 34);
    view.rerender(<PassageCompare />);

    expect(screen.queryByText(/do not have enough validated evidence/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeEnabled();
  });

  it("keeps a completed supported finding on A or B but clears it for a third span", async () => {
    const user = userEvent.setup();
    mocks.comparePerceptualSpans.mockResolvedValue(supportedResponse());
    const view = render(<PassageCompare />);

    await captureAndSelectB(user, view);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));
    expect(await screen.findByText(/selected passages differ/i)).toBeVisible();

    mocks.workspace.selection = selection(10, 14);
    view.rerender(<PassageCompare />);
    expect(screen.getByText(/selected passages differ/i)).toBeVisible();

    mocks.workspace.selection = selection(20, 24);
    view.rerender(<PassageCompare />);
    expect(screen.getByText(/selected passages differ/i)).toBeVisible();

    mocks.workspace.selection = selection(30, 34);
    view.rerender(<PassageCompare />);
    expect(screen.queryByText(/selected passages differ/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeEnabled();
  });

  it("drops a late supported response after the user moves from B to C", async () => {
    const user = userEvent.setup();
    let resolveRequest: ((value: ReturnType<typeof supportedResponse>) => void) | undefined;
    mocks.comparePerceptualSpans.mockImplementation(
      () => new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );
    const view = render(<PassageCompare />);

    await captureAndSelectB(user, view);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));

    mocks.workspace.selection = selection(30, 34);
    view.rerender(<PassageCompare />);
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeEnabled();

    await act(async () => {
      resolveRequest?.(supportedResponse());
    });

    expect(screen.queryByText(/selected passages differ/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeEnabled();
  });

  it("does not surface a late B request failure after the user moves to C", async () => {
    const user = userEvent.setup();
    let rejectRequest: ((reason?: unknown) => void) | undefined;
    mocks.comparePerceptualSpans.mockImplementation(
      () => new Promise((_, reject) => {
        rejectRequest = reject;
      }),
    );
    const view = render(<PassageCompare />);

    await captureAndSelectB(user, view);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));

    mocks.workspace.selection = selection(30, 34);
    view.rerender(<PassageCompare />);
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeEnabled();

    await act(async () => {
      rejectRequest?.(new Error("network failure"));
    });

    expect(screen.queryByText(/comparison request could not be completed/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeEnabled();
  });

  it("preserves the exact performance selection without raw-seeking when Score is active", async () => {
    const user = userEvent.setup();
    mocks.comparePerceptualSpans.mockResolvedValue(supportedResponse());
    const view = render(<PassageCompare />);

    await captureAndSelectB(user, view);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));
    expect(await screen.findByText(/selected passages differ/i)).toBeVisible();

    mocks.transport.activeSource = { role: "score" };
    view.rerender(<PassageCompare />);
    await user.click(screen.getByRole("button", { name: "Focus B" }));

    expect(mocks.seek).not.toHaveBeenCalled();
    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 20, end: 24, domain: "performance" },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    expect(mocks.requestWorkspaceOrientation).toHaveBeenCalledTimes(1);
  });

  it("uses non-promissory copy when measured evidence is unavailable", async () => {
    const user = userEvent.setup();
    mocks.comparePerceptualSpans.mockResolvedValue({
      status: "unavailable",
      evidence_report_version_id: null,
      finding: null,
      reasons: ["no persisted perceptual report"],
    });
    const view = render(<PassageCompare />);

    await captureAndSelectB(user, view);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));

    expect(await screen.findByText("Measured perceptual evidence is not available for this recording.")).toBeVisible();
    expect(screen.queryByText(/not available for this recording yet/i)).not.toBeInTheDocument();
  });
});
