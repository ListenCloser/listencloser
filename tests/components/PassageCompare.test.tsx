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

vi.mock("@/lib/inspector/orientation", () => ({
  requestWorkspaceOrientation: mocks.requestWorkspaceOrientation,
}));

vi.mock("@/lib/relation-api-client", () => ({
  comparePerceptualSpans: mocks.comparePerceptualSpans,
}));

function selection(
  start: number,
  end: number,
  domain: "performance" | "notation" = "performance",
  timeExact = true,
): MusicalSelection {
  return {
    timeRange: { start, end, domain },
    provenance: { origin: "waveform", timeExact, measureApproximate: !timeExact },
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

beforeEach(() => {
  vi.clearAllMocks();
  mocks.workspace.activeWorkId = "work-1";
  mocks.workspace.representations = [
    { kind: "waveform", versionId: "audio-version-1" },
  ];
  mocks.workspace.selection = selection(10, 14);
  mocks.transport.activeSource = { role: "original" };
});

describe("PassageCompare", () => {
  it("requires two explicit selections before querying and renders only the supported relation", async () => {
    const user = userEvent.setup();
    mocks.comparePerceptualSpans.mockResolvedValue(supportedResponse());
    const view = render(<PassageCompare />);

    expect(screen.queryByText(/selected passages differ/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use selection as reference" }));

    expect(screen.queryByRole("button", { name: "Check against selected passage" })).not.toBeInTheDocument();
    expect(mocks.comparePerceptualSpans).not.toHaveBeenCalled();

    mocks.workspace.selection = selection(20, 24);
    view.rerender(<PassageCompare />);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));

    expect(mocks.comparePerceptualSpans).toHaveBeenCalledWith("work-1", {
      source_version_id: "audio-version-1",
      subject_start_seconds: 10,
      subject_end_seconds: 14,
      comparison_start_seconds: 20,
      comparison_end_seconds: 24,
    });
    expect(await screen.findByText("The selected passages differ in measured perceptual evidence.")).toBeVisible();
    expect(screen.getByText("One promoted measurement supports this comparison.")).toBeVisible();
    expect(screen.getByText("Median RMS amplitude is 20.0% higher than in the comparison span.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Focus B" }));
    expect(mocks.seek).toHaveBeenCalledWith(20);
    expect(mocks.setSelection).toHaveBeenCalledWith({
      timeRange: { start: 20, end: 24, domain: "performance" },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    expect(mocks.requestWorkspaceOrientation).toHaveBeenCalledTimes(1);
  });

  it("keeps insufficient evidence as an explicit withheld state instead of inventing a finding", async () => {
    const user = userEvent.setup();
    mocks.comparePerceptualSpans.mockResolvedValue({
      status: "withheld",
      evidence_report_version_id: "00000000-0000-0000-0000-000000000010",
      finding: null,
      reasons: ["insufficient selected-span coverage"],
    });
    const view = render(<PassageCompare />);

    await user.click(screen.getByRole("button", { name: "Use selection as reference" }));
    mocks.workspace.selection = selection(20, 24);
    view.rerender(<PassageCompare />);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));

    expect(await screen.findByText(/do not have enough validated evidence/i)).toBeVisible();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("fails closed when a supported response is missing its grounded finding", async () => {
    const user = userEvent.setup();
    mocks.comparePerceptualSpans.mockResolvedValue({
      status: "supported",
      evidence_report_version_id: "00000000-0000-0000-0000-000000000010",
      finding: null,
      reasons: [],
    });
    const view = render(<PassageCompare />);

    await user.click(screen.getByRole("button", { name: "Use selection as reference" }));
    mocks.workspace.selection = selection(20, 24);
    view.rerender(<PassageCompare />);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));

    expect(await screen.findByText(/comparison response was incomplete/i)).toBeVisible();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("invalidates a late response when the user cancels an in-flight comparison", async () => {
    const user = userEvent.setup();
    let resolveRequest: ((value: ReturnType<typeof supportedResponse>) => void) | undefined;
    mocks.comparePerceptualSpans.mockImplementation(
      () => new Promise((resolve) => {
        resolveRequest = resolve;
      }),
    );
    const view = render(<PassageCompare />);

    await user.click(screen.getByRole("button", { name: "Use selection as reference" }));
    mocks.workspace.selection = selection(20, 24);
    view.rerender(<PassageCompare />);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    resolveRequest?.(supportedResponse());
    await Promise.resolve();

    expect(screen.getByRole("button", { name: "Use selection as reference" })).toBeVisible();
    expect(screen.queryByText("The selected passages differ in measured perceptual evidence.")).not.toBeInTheDocument();
  });

  it("does not offer measured-audio comparison for notation-domain selections", () => {
    mocks.workspace.selection = selection(10, 14, "notation");
    render(<PassageCompare />);

    expect(screen.queryByRole("region", { name: "Compare passages" })).not.toBeInTheDocument();
  });

  it("does not treat approximate performance spans as measured-audio selections", () => {
    mocks.workspace.selection = selection(10, 14, "performance", false);
    render(<PassageCompare />);

    expect(screen.queryByRole("region", { name: "Compare passages" })).not.toBeInTheDocument();
  });

  it("resets transient comparison state when the active Work changes", async () => {
    const user = userEvent.setup();
    const view = render(<PassageCompare />);

    await user.click(screen.getByRole("button", { name: "Use selection as reference" }));
    expect(screen.getByText(/Reference/)).toBeVisible();

    mocks.workspace.activeWorkId = "work-2";
    mocks.workspace.selection = selection(30, 34);
    view.rerender(<PassageCompare />);

    expect(await screen.findByRole("button", { name: "Use selection as reference" })).toBeVisible();
    expect(screen.queryByText(/Reference 0:10/)).not.toBeInTheDocument();
  });
});
