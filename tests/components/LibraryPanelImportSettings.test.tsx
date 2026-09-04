import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LibraryPanel from "@/components/workspace/LibraryPanel";

const mocks = vi.hoisted(() => ({
  profile: "auto" as "auto" | "solo_piano",
  scoreEngine: "musescore" as "musescore" | "pm2s",
  activeWorkId: null as string | null,
  requestAttachScore: vi.fn(),
  requestImport: vi.fn(),
  requestScoreEngine: vi.fn(),
  selectScoreSource: vi.fn(),
  setScoreEngine: vi.fn(),
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
      activeWorkId: mocks.activeWorkId,
      isLoadingWork: false,
      libraryCollapsed: false,
      representations: [],
      scoreDisplaySelection: mocks.activeWorkId ? { kind: "engine", engine: mocks.scoreEngine } : null,
      scoreSources: mocks.activeWorkId
        ? [{ versionId: "source-v1", label: "Attached · source.musicxml" }]
        : [],
      scoreEngine: mocks.scoreEngine,
      transcriptionProfile: mocks.profile,
    },
    requestAttachScore: mocks.requestAttachScore,
    requestImport: mocks.requestImport,
    requestScoreEngine: mocks.requestScoreEngine,
    selectScoreSource: mocks.selectScoreSource,
    setActiveWorkId: vi.fn(),
    clearSelection: vi.fn(),
    setScoreEngine: mocks.setScoreEngine,
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
  mocks.scoreEngine = "musescore";
  mocks.activeWorkId = null;
  mocks.requestAttachScore.mockReset();
  mocks.requestImport.mockReset();
  mocks.requestScoreEngine.mockReset();
  mocks.selectScoreSource.mockReset();
  mocks.setScoreEngine.mockReset();
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

  it("keeps explicit transcription and score reconstruction choices available on demand", async () => {
    const user = userEvent.setup();
    render(<LibraryPanel signedIn canImport />);

    await user.click(screen.getByText("Processing"));

    const processing = screen.getByText("Processing").closest("details");
    expect(processing).toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Auto" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "MuseScore" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "PM2S" })).toHaveAttribute("aria-pressed", "false");

    await user.click(screen.getByRole("button", { name: "Solo piano" }));
    expect(mocks.setTranscriptionProfile).toHaveBeenCalledWith("solo_piano");

    await user.click(screen.getByRole("button", { name: "PM2S" }));
    expect(mocks.setScoreEngine).toHaveBeenCalledWith("pm2s");
  });

  it("shows previously selected non-default processing choices when Processing is opened", async () => {
    const user = userEvent.setup();
    mocks.profile = "solo_piano";
    mocks.scoreEngine = "pm2s";
    render(<LibraryPanel signedIn canImport />);

    await user.click(screen.getByText("Processing"));

    expect(screen.getByRole("button", { name: "Solo piano" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "PM2S" })).toHaveAttribute("aria-pressed", "true");
  });

  it("owns attached source selection and attachment inside Processing", async () => {
    const user = userEvent.setup();
    mocks.activeWorkId = "work-1";
    render(<LibraryPanel signedIn canImport />);

    expect(screen.queryByRole("combobox", { name: "Score source" })).not.toBeInTheDocument();
    await user.click(screen.getByText("Processing"));

    const source = screen.getByRole("combobox", { name: "Score source" });
    expect(source).toHaveValue("engine:musescore");
    expect(screen.getByRole("option", { name: "Attached · source.musicxml" })).toBeInTheDocument();

    await user.selectOptions(source, "source:source-v1");
    expect(mocks.selectScoreSource).toHaveBeenCalledWith("source-v1");

    await user.click(screen.getByRole("button", { name: "Attach score" }));
    expect(mocks.requestAttachScore).toHaveBeenCalledTimes(1);
  });
});
