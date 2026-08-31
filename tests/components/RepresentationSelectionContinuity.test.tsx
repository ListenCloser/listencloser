import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RepresentationStack from "@/components/workspace/RepresentationStack";
import {
  WorkspaceProvider,
  useWorkspace,
  type RepresentationEntry,
} from "@/lib/stores/workspace";

vi.mock("@/components/workspace/representations/registry", () => {
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
    REPRESENTATIONS: definitions,
    availableRepresentations: (availability: { originalAudio: boolean; performanceMidi: boolean }) => definitions.filter(
      (definition) => definition.id === "listen" ? availability.originalAudio : availability.performanceMidi,
    ),
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
      <button type="button" onClick={() => replaceRepresentations([waveform])}>Waveform ready</button>
      <button type="button" onClick={() => replaceRepresentations([waveform, pianoRoll])}>Both ready</button>
      <button type="button" onClick={() => replaceRepresentations([waveform])}>Transient waveform only</button>
      <output data-testid="shared-selection">{workspace.activeRepresentation ?? "none"}</output>
    </>
  );
}

function SelectionProbe() {
  const { workspace, replaceRepresentations, setSelection } = useWorkspace();
  return (
    <>
      <button type="button" onClick={() => replaceRepresentations([waveform])}>Open waveform</button>
      <button
        type="button"
        onClick={() => setSelection({
          timeRange: { start: 3, end: 7, domain: "performance" },
          provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
        })}
      >
        Select passage
      </button>
      <output data-testid="passage-scope">{workspace.selection?.timeRange ? "selected" : "none"}</output>
    </>
  );
}

describe("representation selection continuity", () => {
  it("does not let a newly available representation steal the active view", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
        <RefreshControls />
      </WorkspaceProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Waveform ready" }));
    expect(await screen.findByRole("tab", { name: "Waveform" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("shared-selection")).toHaveTextContent("listen");

    await user.click(screen.getByRole("button", { name: "Both ready" }));
    expect(screen.getByRole("tab", { name: "Waveform" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Piano Roll" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByTestId("waveform-view")).toBeVisible();
    expect(screen.getByTestId("shared-selection")).toHaveTextContent("listen");
  });

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

    await user.click(screen.getByRole("button", { name: "Both ready" }));
    expect(screen.getByRole("tab", { name: "Piano Roll" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("piano-roll-view")).toBeVisible();
    expect(screen.getByTestId("shared-selection")).toHaveTextContent("piano_roll");
  });

  it("clears the shared passage with Escape", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
        <SelectionProbe />
      </WorkspaceProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Open waveform" }));
    await screen.findByRole("tab", { name: "Waveform" });
    await user.click(screen.getByRole("button", { name: "Select passage" }));
    expect(screen.getByTestId("passage-scope")).toHaveTextContent("selected");

    await user.keyboard("{Escape}");
    expect(screen.getByTestId("passage-scope")).toHaveTextContent("none");
  });
});
