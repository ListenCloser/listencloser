import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LibraryPanel from "@/components/workspace/LibraryPanel";

const mocks = vi.hoisted(() => ({
  profile: "auto" as "auto" | "solo_piano",
  requestImport: vi.fn(),
  setTranscriptionProfile: vi.fn(),
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({}),
}));

vi.mock("@/components/AuthProvider", () => ({
  useAuth: () => ({ user: { id: "user-1" } }),
}));

vi.mock("@/components/ui/Tooltip", () => ({
  default: ({ children }: { children: ReactNode }) => children,
}));

vi.mock("@/components/workspace/LibraryImportControl", () => ({
  default: ({ onUpload }: { onUpload: () => void }) => (
    <button type="button" onClick={onUpload}>Import audio</button>
  ),
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
  useTransport: () => ({ clearActiveSource: vi.fn() }),
}));

vi.mock("@/lib/stores/timeline", () => ({
  useTimeline: () => ({ resetTimeline: vi.fn() }),
}));

vi.mock("@/lib/stores/workspace", () => ({
  useWorkspace: () => ({
    workspace: {
      activeWorkId: null,
      isLoadingWork: false,
      libraryCollapsed: false,
      transcriptionProfile: mocks.profile,
    },
    requestImport: mocks.requestImport,
    setActiveWorkId: vi.fn(),
    clearSelection: vi.fn(),
    setTranscriptionProfile: mocks.setTranscriptionProfile,
  }),
}));

vi.mock("@/lib/server-state", () => ({
  refreshProjectWorks: vi.fn(),
  useLibraryProject: () => ({
    data: { id: "project-1" },
    isPending: false,
  }),
  useProjectWorks: () => ({ data: [], isPending: false }),
  useDeleteWorkMutation: () => ({ mutateAsync: vi.fn() }),
}));

beforeEach(() => {
  mocks.profile = "auto";
  mocks.requestImport.mockReset();
  mocks.setTranscriptionProfile.mockReset();
});

describe("LibraryPanel processing disclosure", () => {
  it("keeps Import primary while processing choices start collapsed", () => {
    render(<LibraryPanel signedIn canImport />);

    expect(screen.getByRole("button", { name: "Import audio" })).toBeVisible();
    const processing = screen.getByText("Processing").closest("details");
    expect(processing).not.toBeNull();
    expect(processing).not.toHaveAttribute("open");
  });

  it("keeps explicit transcription profile selection available on demand", async () => {
    const user = userEvent.setup();
    render(<LibraryPanel signedIn canImport />);

    await user.click(screen.getByText("Processing"));

    const processing = screen.getByText("Processing").closest("details");
    expect(processing).toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Auto" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "Solo piano" }));
    expect(mocks.setTranscriptionProfile).toHaveBeenCalledWith("solo_piano");
  });

  it("shows a previously selected non-default profile when Processing is opened", async () => {
    const user = userEvent.setup();
    mocks.profile = "solo_piano";
    render(<LibraryPanel signedIn canImport />);

    await user.click(screen.getByText("Processing"));

    expect(screen.getByRole("button", { name: "Solo piano" })).toHaveAttribute("aria-pressed", "true");
  });
});
