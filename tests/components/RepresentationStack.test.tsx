import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RepresentationStack from "@/components/workspace/RepresentationStack";
import { WorkspaceProvider } from "@/lib/stores/workspace";

vi.mock("@/lib/representations", () => {
  const definitions = [
    {
      id: "listen",
      title: "Waveform",
      description: "test waveform",
      temporal: true,
      available: () => true,
      component: () => <input aria-label="Waveform local state" />,
    },
    {
      id: "score",
      title: "Score",
      description: "test score",
      temporal: true,
      available: () => true,
      component: () => <input aria-label="Score local state" />,
    },
  ];

  return {
    availableRepresentations: () => definitions,
    representationById: (id: string) => definitions.find((definition) => definition.id === id),
  };
});

describe("RepresentationStack", () => {
  it("keeps visited representation DOM mounted across tab switches", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    const waveformState = await screen.findByRole("textbox", { name: "Waveform local state" });
    await user.type(waveformState, "preserved-view-state");

    await user.click(screen.getByRole("tab", { name: "Score" }));
    expect(screen.getByRole("textbox", { name: "Score local state" })).toBeVisible();
    expect(waveformState).not.toBeVisible();
    expect(waveformState.closest("section")).toHaveAttribute("hidden");

    await user.click(screen.getByRole("tab", { name: "Waveform" }));
    expect(screen.getByRole("textbox", { name: "Waveform local state" })).toHaveValue("preserved-view-state");
  });
});
