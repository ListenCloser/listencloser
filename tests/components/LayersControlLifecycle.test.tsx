import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LayersControl from "@/components/workspace/LayersControl";
import type { WorkBundle } from "@/lib/domain.types";

const mocks = vi.hoisted(() => ({
  bundle: null as WorkBundle | null,
  getJob: vi.fn(),
  getWorkBundle: vi.fn(),
  clearWorkDataCache: vi.fn(),
  post: vi.fn(),
  setActiveSource: vi.fn(),
  waitForJob: vi.fn(),
}));

function versionArtifact(
  id: string,
  kind: string,
  versionId: string,
  {
    parentVersionId = null,
    producedByJobId = null,
    metadata = {},
  }: {
    parentVersionId?: string | null;
    producedByJobId?: string | null;
    metadata?: Record<string, unknown>;
  } = {},
) {
  return {
    artifact: { id, work_id: "work-1", kind },
    latest_version: {
      id: versionId,
      artifact_id: id,
      parent_version_id: parentVersionId,
      produced_by_job_id: producedByJobId,
      metadata,
    },
    versions: [],
    signed_url: `https://example.test/${versionId}.wav`,
  };
}

function stem(role: string) {
  return versionArtifact(`stem-${role}`, "stems", `${role}-v1`, {
    parentVersionId: "original-v1",
    producedByJobId: "separate-job",
    metadata: { representation: "source_stem", stem_role: role },
  });
}

function workBundle({ complete = false, partial = false } = {}): WorkBundle {
  const artifacts = [versionArtifact("original", "audio_original", "original-v1")];
  if (complete) artifacts.push(stem("vocals"), stem("drums"), stem("bass"), stem("other"));
  if (partial) artifacts.push(stem("vocals"), stem("drums"));
  return {
    work: { id: "work-1" },
    artifacts,
    jobs: [],
  } as unknown as WorkBundle;
}

vi.mock("@/lib/api-client", () => ({
  clearWorkDataCache: mocks.clearWorkDataCache,
  getJob: mocks.getJob,
  getWorkBundle: mocks.getWorkBundle,
  retryJob: vi.fn(),
}));

vi.mock("@/lib/openapi-client", () => ({
  openapiClient: { POST: mocks.post },
  requireOpenApiData: (result: { data?: unknown }) => result.data,
}));

vi.mock("@/lib/job-tracking", () => ({
  JobObservationError: class JobObservationError extends Error {},
  sanitizeJobError: (raw: string | null | undefined) => raw || "Layer separation could not be completed.",
  waitForJob: mocks.waitForJob,
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: {
      activeWorkId: "work-1",
      isLoadingWork: false,
    },
  }),
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({
    transport: {
      position: 37.25,
      activeSource: {
        id: "original-v1",
        label: "Original",
        role: "original",
        kind: "audio",
        url: "https://example.test/original-v1.wav",
      },
    },
    setActiveSource: mocks.setActiveSource,
  }),
}));

beforeEach(() => {
  mocks.bundle = workBundle();
  mocks.getWorkBundle.mockReset().mockImplementation(async () => mocks.bundle);
  mocks.getJob.mockReset().mockResolvedValue({
    id: "separate-job",
    capability: "separate",
    stage: "succeeded",
  });
  mocks.clearWorkDataCache.mockReset();
  mocks.post.mockReset().mockResolvedValue({
    data: {
      workflow: { id: "separate-workflow" },
      job: {
        id: "separate-job",
        lifecycle: { current: "queued" },
      },
    },
  });
  mocks.setActiveSource.mockReset();
  mocks.waitForJob.mockReset();
});

describe("Experimental Layers product lifecycle", () => {
  it("keeps Original active until the musician explicitly hears each completed layer", async () => {
    const user = userEvent.setup();
    let finishJob: (() => void) | null = null;
    mocks.waitForJob.mockImplementation(
      () => new Promise((resolve) => {
        finishJob = () => {
          mocks.bundle = workBundle({ complete: true });
          resolve({ id: "separate-job", capability: "separate", stage: "succeeded" });
        };
      }),
    );

    render(<LayersControl projectId="project-1" canProcess />);

    expect(await screen.findByText("Layers")).toBeVisible();
    expect(screen.getByText("Experimental")).toBeVisible();
    const separate = await screen.findByRole("button", { name: "Separate layers" });

    await user.click(separate);

    expect(await screen.findByRole("button", { name: "Separating layers…" })).toBeDisabled();
    expect(screen.getByLabelText("Layer playback sources")).toHaveTextContent("Original");
    expect(mocks.setActiveSource).not.toHaveBeenCalled();

    finishJob?.();

    expect(await screen.findByText("Vocals")).toBeVisible();
    const rows = screen.getByLabelText("Layer playback sources");
    expect(rows.textContent).toMatch(/Original.*Vocals.*Drums.*Bass.*Other/);
    // Generation changes no transport source and therefore cannot silently
    // move playback away from the Original at the existing 37.25 s position.
    expect(mocks.setActiveSource).not.toHaveBeenCalled();

    for (const label of ["Vocals", "Drums", "Bass", "Other"]) {
      const row = screen.getByText(label).closest("div");
      expect(row).not.toBeNull();
      await user.click(withinRowButton(row!, "Hear"));
      expect(mocks.setActiveSource).toHaveBeenLastCalledWith(
        expect.objectContaining({ label, sourceVersionId: "original-v1" }),
      );
    }

    const originalRow = screen.getByText("Original").closest("div");
    expect(originalRow).not.toBeNull();
    await user.click(withinRowButton(originalRow!, "Hearing"));
    expect(mocks.setActiveSource).toHaveBeenLastCalledWith(
      expect.objectContaining({ id: "original-v1", label: "Original" }),
    );
  });

  it("keeps failure local and never exposes a partial stem set", async () => {
    const user = userEvent.setup();
    mocks.waitForJob.mockImplementation(async () => {
      mocks.bundle = workBundle({ partial: true });
      throw new Error("HTDemucs source separation failed");
    });

    render(<LayersControl projectId="project-1" canProcess />);

    await user.click(await screen.findByRole("button", { name: "Separate layers" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "HTDemucs source separation failed",
    );
    expect(screen.getByLabelText("Layer playback sources")).toHaveTextContent("Original");
    expect(screen.queryByText("Vocals")).not.toBeInTheDocument();
    expect(screen.queryByText("Drums")).not.toBeInTheDocument();
    expect(mocks.setActiveSource).not.toHaveBeenCalled();
  });
});

function withinRowButton(row: HTMLElement, name: string): HTMLButtonElement {
  const button = Array.from(row.querySelectorAll("button")).find(
    (candidate) => candidate.textContent === name,
  );
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`Missing ${name} button in layer row`);
  }
  return button;
}
