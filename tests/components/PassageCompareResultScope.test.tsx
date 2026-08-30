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
  useTransport: () => ({ seek: mocks.seek }),
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

beforeEach(() => {
  vi.clearAllMocks();
  mocks.workspace.activeWorkId = "work-1";
  mocks.workspace.representations = [
    { kind: "waveform", versionId: "audio-version-1" },
  ];
  mocks.workspace.selection = selection(10, 14);
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

    await user.click(screen.getByRole("button", { name: "Use selection as reference" }));
    mocks.workspace.selection = selection(20, 24);
    view.rerender(<PassageCompare />);
    await user.click(screen.getByRole("button", { name: "Check against selected passage" }));

    expect(await screen.findByText(/do not have enough validated evidence/i)).toBeVisible();

    mocks.workspace.selection = selection(30, 34);
    view.rerender(<PassageCompare />);

    expect(screen.queryByText(/do not have enough validated evidence/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check against selected passage" })).toBeVisible();
  });
});
