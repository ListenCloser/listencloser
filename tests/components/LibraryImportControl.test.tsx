import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import LibraryImportControl from "@/components/workspace/LibraryImportControl";

function renderImportControl({
  onUpload = vi.fn(),
  onImport = vi.fn().mockResolvedValue(undefined),
  onTranscriptionProfileChange = vi.fn(),
  onScoreEngineChange = vi.fn(),
  disabled = false,
}: {
  onUpload?: ReturnType<typeof vi.fn>;
  onImport?: ReturnType<typeof vi.fn>;
  onTranscriptionProfileChange?: ReturnType<typeof vi.fn>;
  onScoreEngineChange?: ReturnType<typeof vi.fn>;
  disabled?: boolean;
} = {}) {
  render(
    <LibraryImportControl
      disabled={disabled}
      transcriptionProfile="auto"
      scoreEngine="musescore"
      onTranscriptionProfileChange={onTranscriptionProfileChange}
      onScoreEngineChange={onScoreEngineChange}
      onUpload={onUpload}
      onImport={onImport}
    />,
  );
}

describe("LibraryImportControl", () => {
  it("asks for compact processing choices before opening a local file", async () => {
    const user = userEvent.setup();
    const onUpload = vi.fn();
    const onTranscriptionProfileChange = vi.fn();
    const onScoreEngineChange = vi.fn();
    renderImportControl({ onUpload, onTranscriptionProfileChange, onScoreEngineChange });

    await user.click(screen.getByRole("button", { name: "Import audio" }));
    await user.click(screen.getByRole("menuitem", { name: /Upload recording/ }));

    expect(onUpload).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Process recording" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Auto" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "MuseScore" })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: "Solo piano" }));
    await user.click(screen.getByRole("button", { name: "PM2S" }));
    await user.click(screen.getByRole("button", { name: "Choose audio" }));

    expect(onTranscriptionProfileChange).toHaveBeenCalledWith("solo_piano");
    expect(onScoreEngineChange).toHaveBeenCalledWith("pm2s");
    expect(onUpload).toHaveBeenCalledTimes(1);
  });

  it("keeps the public catalog and applies processing choices only after a recording is selected", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockResolvedValue(undefined);
    renderImportControl({ onImport });

    await user.click(screen.getByRole("button", { name: "Import audio" }));
    await user.click(screen.getByRole("menuitem", { name: /Public recordings/ }));
    expect(screen.getByRole("dialog", { name: "Public recordings" })).toBeInTheDocument();
    expect(screen.getByText("Für Elise")).toBeInTheDocument();
    expect(screen.getByText("Jazz Ride Pattern")).toBeInTheDocument();
    expect(screen.getByText("Jesse James")).toBeInTheDocument();

    await user.type(
      screen.getByRole("searchbox", { name: "Search public recordings" }),
      "jazz",
    );
    expect(screen.queryByText("Für Elise")).not.toBeInTheDocument();
    expect(screen.getByText("Jazz Ride Pattern")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Import" }));
    expect(onImport).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Process recording" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Import recording" }));

    await waitFor(() => {
      expect(onImport).toHaveBeenCalledTimes(1);
      expect(onImport.mock.calls[0][0].id).toBe("jazz-ride-pattern");
      expect(onImport.mock.calls[0][1]).toEqual({
        transcriptionProfile: "auto",
        scoreEngine: "musescore",
      });
    });
  });

  it("keeps the import action disabled while the library is unavailable", () => {
    renderImportControl({ disabled: true });

    expect(screen.getByRole("button", { name: "Import audio" })).toBeDisabled();
  });
});
