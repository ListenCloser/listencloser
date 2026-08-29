import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RepresentationStack from "@/components/workspace/RepresentationStack";
import {
  WorkspaceProvider,
  useWorkspace,
  type RepresentationEntry,
} from "@/lib/stores/workspace";

vi.mock("@/lib/representations", () => {
  const definitions = [
    {
      id: "listen",
      title: "Waveform",
      description: "test waveform",
      temporal: true,
      component: () => <div data-testid="waveform-view">Waveform ready</div>,
    },
    {
      id: "piano_roll",
      title: "Piano Roll",
      description: "test piano roll",
      temporal: true,
      component: () => <div data-testid="piano-roll-view">Piano roll ready</div>,
    },
  ];

  return {
    availableRepresentations: (availability: { originalAudio: boolean; performanceMidi: boolean }) => definitions.filter(
      (definition) => definition.id === "listen" ? availability.originalAudio : availability.performanceMidi,
    ),
    representationById: (id: string) => definitions.find((definition) => definition.id === id),
  };
});

const waveform: RepresentationEntry = {
  kind: "waveform",
  label: "Waveform",
  sourceUrl: "/audio/source.wav",
  sourceLabel: "Original",
  confidence: null,
  provenance: "test",
  versionId: "source-v1",
};

const pianoRoll: RepresentationEntry = {
  kind: "piano_roll",
  label: "Piano Roll",
  sourceUrl: "/midi/source.mid",
  sourceLabel: "Transcription",
  confidence: null,
  provenance: "test",
  versionId: "midi-v1",
};

function RefreshControls() {
  const { workspace, replaceRepresentations } = useWorkspace();
  return (
    <>
      <button type="button" onClick={() => replaceRepresentations([waveform, pianoRoll])}>Both ready</button>
      <button type="button" onClick={() => replaceRepresentations([waveform])}>Transient waveform only</button>
      <output data-testid="shared-selection">{workspace.activeRepresentation ?? "none"}</output>
    </>
  );
}

describe("representation selection continuity", () => {
  it("restores the user's Piano Roll choice after a transient processing poll omits it", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
        <RefreshControls />
      </WorkspaceProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Both ready" }));
    expect(await screen.findByRole("tab", { name: "Waveform" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Piano Roll" }));
    expect(screen.getByTestId("shared-selection")).toHaveTextContent("piano_roll");
    expect(screen.getByTestId("piano-roll-view")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Transient waveform only" }));
    expect(screen.getByTestId("waveform-view")).toBeVisible();
    expect(screen.getByTestId("shared-selection")).toHaveTextContent("piano_roll");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Both ready" }));
    });
    expect(screen.getByRole("tab", { name: "Piano Roll" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("piano-roll-view")).toBeVisible();
    expect(screen.getByTestId("shared-selection")).toHaveTextContent("piano_roll");
  });
});
