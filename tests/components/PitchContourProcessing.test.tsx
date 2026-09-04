import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PitchContourProcessing from "@/components/workspace/PitchContourProcessing";
import { useWorkspace, WorkspaceProvider } from "@/lib/stores/workspace";

const mocks = vi.hoisted(() => ({
  getWorkBundle: vi.fn(),
  retryJob: vi.fn(),
  startPitchContourWorkflow: vi.fn(),
  waitForJob: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  getWorkBundle: mocks.getWorkBundle,
  retryJob: mocks.retryJob,
  startPitchContourWorkflow: mocks.startPitchContourWorkflow,
}));

vi.mock("@/lib/job-tracking", () => ({
  waitForJob: mocks.waitForJob,
}));

function Harness() {
  const {
    workspace,
    setActiveWorkId,
    setLoadingWork,
    replaceRepresentations,
  } = useWorkspace();

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setActiveWorkId("work-1");
          setLoadingWork(false);
          replaceRepresentations([
            {
              kind: "waveform",
              label: "Waveform",
              sourceUrl: "https://audio.example/source.wav",
              sourceLabel: "Original",
              confidence: null,
              provenance: "uploaded source",
              versionId: "source-version-1",
            },
          ]);
        }}
      >
        Load work
      </button>
      <span data-testid="pitch-open-state">{workspace.pitchContourOpen ? "open" : "closed"}</span>
    </>
  );
}

describe("PitchContourProcessing", () => {
  it("derives status from server truth, waits through shared job tracking, and opens only on explicit Open", async () => {
    const user = userEvent.setup();
    let finishJob!: () => void;
    const terminal = new Promise<void>((resolve) => {
      finishJob = resolve;
    });

    mocks.getWorkBundle
      .mockResolvedValueOnce({
        work: { project_id: "project-1" },
        artifacts: [],
        jobs: [],
      })
      .mockResolvedValueOnce({
        work: { project_id: "project-1" },
        artifacts: [
          {
            artifact: { kind: "analysis_report" },
            latest_version: { metadata: { representation_type: "pitch_contour" } },
          },
        ],
        jobs: [],
      });
    mocks.startPitchContourWorkflow.mockResolvedValue({ job: { id: "pitch-job-1" } });
    mocks.waitForJob.mockImplementation(() => terminal);

    render(
      <WorkspaceProvider>
        <Harness />
        <PitchContourProcessing />
      </WorkspaceProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Load work" }));
    const add = await screen.findByRole("button", { name: "Add" });
    expect(screen.getByTestId("pitch-open-state")).toHaveTextContent("closed");

    await user.click(add);
    expect(mocks.startPitchContourWorkflow).toHaveBeenCalledWith("source-version-1", "project-1");
    expect(await screen.findByRole("button", { name: "Processing pitch contour…" })).toBeDisabled();
    expect(mocks.waitForJob).toHaveBeenCalledWith(
      "pitch-job-1",
      expect.any(Function),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    await act(async () => {
      finishJob();
      await terminal;
    });

    const open = await screen.findByRole("button", { name: "Open" });
    expect(screen.getByTestId("pitch-open-state")).toHaveTextContent("closed");

    await user.click(open);
    expect(screen.getByTestId("pitch-open-state")).toHaveTextContent("open");
  });
});
