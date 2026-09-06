import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LibraryPanel from "@/components/workspace/LibraryPanel";

const mocks = vi.hoisted(() => ({
  activeWorkId: "work-a" as string | null,
  clearSelection: vi.fn(),
  clearActiveSource: vi.fn(),
  resetTimeline: vi.fn(),
  setActiveWorkId: vi.fn(),
  mutateAsync: vi.fn(),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({}),
}));

vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: null }),
}));

vi.mock("@/components/ui/Tooltip", () => ({
  default: ({ children }: { children: ReactNode }) => children,
}));

vi.mock("@/components/workspace/LibraryImportControl", () => ({
  default: () => null,
}));

vi.mock("@/lib/api-client", () => ({
  getWorkBundle: vi.fn().mockResolvedValue({}),
  startUnderstandWorkflow: vi.fn(),
  uploadArtifact: vi.fn(),
}));

vi.mock("@/lib/public-recordings", () => ({
  downloadPublicRecording: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: null,
}));

vi.mock("@/lib/stores/transport", () => ({
  useTransport: () => ({ clearActiveSource: mocks.clearActiveSource }),
}));

vi.mock("@/lib/stores/timeline", () => ({
  useTimeline: () => ({ resetTimeline: mocks.resetTimeline }),
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: {
      activeWorkId: mocks.activeWorkId,
      isLoadingWork: false,
      libraryCollapsed: false,
      transcriptionProfile: "auto",
    },
    requestImport: vi.fn(),
    setActiveWorkId: mocks.setActiveWorkId,
    clearSelection: mocks.clearSelection,
    setTranscriptionProfile: vi.fn(),
  }),
}));

vi.mock("@/lib/server-state", () => ({
  refreshProjectWorks: vi.fn(),
  useLibraryProject: () => ({
    data: { id: "project-1" },
    isPending: false,
  }),
  useProjectWorks: () => ({
    data: [
      { id: "work-a", title: "Active recording" },
      { id: "work-b", title: "Other recording" },
    ],
    isPending: false,
  }),
  useDeleteWorkMutation: () => ({ mutateAsync: mocks.mutateAsync }),
}));

beforeEach(() => {
  mocks.activeWorkId = "work-a";
  mocks.clearSelection.mockReset();
  mocks.clearActiveSource.mockReset();
  mocks.resetTimeline.mockReset();
  mocks.setActiveWorkId.mockReset();
  mocks.mutateAsync.mockReset().mockResolvedValue({});
});

describe("LibraryPanel deletion selection ownership", () => {
  it("preserves the active Work passage when deleting another recording", async () => {
    const user = userEvent.setup();
    render(<LibraryPanel />);

    await user.click(screen.getByRole("button", { name: "Delete Other recording" }));

    await waitFor(() => expect(mocks.mutateAsync).toHaveBeenCalledWith("work-b"));
    expect(mocks.clearSelection).not.toHaveBeenCalled();
    expect(mocks.clearActiveSource).not.toHaveBeenCalled();
    expect(mocks.resetTimeline).not.toHaveBeenCalled();
    expect(mocks.setActiveWorkId).not.toHaveBeenCalled();
  });

  it("still clears passage context when deleting the active recording", async () => {
    const user = userEvent.setup();
    render(<LibraryPanel />);

    await user.click(screen.getByRole("button", { name: "Delete Active recording" }));

    await waitFor(() => expect(mocks.mutateAsync).toHaveBeenCalledWith("work-a"));
    expect(mocks.clearSelection).toHaveBeenCalledTimes(1);
    expect(mocks.clearActiveSource).toHaveBeenCalledTimes(1);
    expect(mocks.resetTimeline).toHaveBeenCalledTimes(1);
    expect(mocks.setActiveWorkId).toHaveBeenCalledWith("work-b");
  });
});
