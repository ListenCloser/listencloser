import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import RepresentationStack from "@/components/workspace/RepresentationStack";
import { useWorkspace, WorkspaceProvider } from "@/lib/stores/workspace";

vi.mock("@/lib/score-renderer", () => ({
  preloadScoreRenderer: vi.fn(),
}));

vi.mock("@/components/workspace/PitchContourLane", () => ({
  default: ({ onClose }: { onClose: () => void }) => (
    <section data-testid="pitch-contour-lane">
      <span>Pitch contour · Experimental interpretation</span>
      <button type="button" onClick={onClose}>Hide</button>
    </section>
  ),
}));

vi.mock("@/components/workspace/representations/registry", () => {
  const definitions = [
    ["listen", "Waveform"],
    ["piano_roll", "Piano Roll"],
    ["score", "Score"],
    ["spectrogram", "Spectrogram"],
  ].map(([id, title]) => ({
    id,
    title,
    description: title,
    temporal: true,
    available: () => true,
    component: () => <div data-testid={`${id}-view`}>{title}</div>,
  }));

  return {
    REPRESENTATIONS: definitions,
    availableRepresentations: () => definitions,
    representationById: (id: string) => definitions.find((definition) => definition.id === id),
  };
});

function Harness() {
  const { setPitchContourOpen } = useWorkspace();
  return (
    <button type="button" onClick={() => setPitchContourOpen(true)}>
      Open pitch contour
    </button>
  );
}

describe("Pitch contour workspace placement", () => {
  it("keeps four primary representations while the optional lane survives tab switches and can hide/reopen", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <Harness />
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    expect(screen.getAllByRole("tab")).toHaveLength(4);
    expect(screen.queryByTestId("pitch-contour-lane")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open pitch contour" }));
    expect(screen.getByTestId("pitch-contour-lane")).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "Score" }));
    expect(screen.getByTestId("pitch-contour-lane")).toBeVisible();
    expect(screen.getByTestId("score-view")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByTestId("pitch-contour-lane")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open pitch contour" }));
    expect(screen.getByTestId("pitch-contour-lane")).toBeVisible();
    expect(screen.getAllByRole("tab")).toHaveLength(4);
  });
});
