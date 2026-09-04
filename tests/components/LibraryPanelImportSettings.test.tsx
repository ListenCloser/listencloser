import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LibraryPanel from "@/components/workspace/LibraryPanel";

const mocks = vi.hoisted(() => ({
  profile: "auto" as "auto" | "solo_piano",
  scoreEngine: "musescore" as "musescore" | "pm2s",
  requestImport: vi.fn(),
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
  default: ({
    onUpload,
    transcriptionProfile,
    scoreEngine,
    onTranscriptionProfileChange,
    onScoreEngineChange,
  }: {
    onUpload: () => void;
    transcriptionProfile: "auto" | "solo_piano";
    scoreEngine: "musescore" | "pm2s";
    onTranscriptionProfileChange: (profile: "auto" | "solo_piano") => void;
    onScoreEngineChange: (engine: "musescore" | "pm2s") => void;
  }) => (
    <div>
      <button type="button" onClick={onUpload}>Import audio</button>
      <span>Transcription default: {transcriptionProfile}</span>
      <span>Score default: {scoreEngine}</span>
      <button type="button" onClick={() => onTranscriptionProfileChange("solo_piano")}>Choose solo piano</button>
      <button type="button" onClick={() => onScoreEngineChange("pm2s")}>Choose PM2S</button>
    </div>
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
      representations: [],
      scoreEngine: mocks.scoreEngine,
      transcriptionProfile: mocks.profile,
    },
    requestImport: mocks.requestImport,
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
  mocks.requestImport.mockReset();
  mocks.setScoreEngine.mockReset();
  mocks.setTranscriptionProfile.mockReset();
});

describe("LibraryPanel import processing handoff", () => {
  it("keeps Import primary and removes the persistent Processing panel from the sidebar", () => {
    render(<LibraryPanel signedIn canImport />);

    expect(screen.getByRole("button", { name: "Import audio" })).toBeVisible();
    expect(screen.queryByText("Processing")).not.toBeInTheDocument();
    expect(document.querySelector(".library-import-settings")).toBeNull();
  });

  it("hands current processing defaults and setters to the import control", async () => {
    const user = userEvent.setup();
    render(<LibraryPanel signedIn canImport />);

    expect(screen.getByText("Transcription default: auto")).toBeVisible();
    expect(screen.getByText("Score default: musescore")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Choose solo piano" }));
    expect(mocks.setTranscriptionProfile).toHaveBeenCalledWith("solo_piano");

    await user.click(screen.getByRole("button", { name: "Choose PM2S" }));
    expect(mocks.setScoreEngine).toHaveBeenCalledWith("pm2s");
  });

  it("preserves previously selected processing defaults for the next import", () => {
    mocks.profile = "solo_piano";
    mocks.scoreEngine = "pm2s";
    render(<LibraryPanel signedIn canImport />);

    expect(screen.getByText("Transcription default: solo_piano")).toBeVisible();
    expect(screen.getByText("Score default: pm2s")).toBeVisible();
  });
});
