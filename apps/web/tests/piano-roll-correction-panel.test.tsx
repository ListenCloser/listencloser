import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PianoRollCorrectionPanel from "@/components/workspace/PianoRollCorrectionPanel";
import type { EditablePianoRollNote } from "@/lib/piano-roll-correction";
import { useWorkspace, WorkspaceProvider } from "@/lib/stores/workspace";

const source: EditablePianoRollNote[] = [
  { id: "target", pitch: 60, start: 0.5, end: 1.0, velocity: 90 },
  { id: "neighbor", pitch: 64, start: 0.6, end: 0.9, velocity: 80 },
];

function Harness() {
  const { workspace } = useWorkspace();
  const [draft, setDraft] = useState<EditablePianoRollNote[] | null>(source.map((note) => ({ ...note })));
  const [selected, setSelected] = useState(["target"]);
  return (
    <>
      <PianoRollCorrectionPanel
        sourceNotes={source}
        sourceVersionId="source-v1"
        draftNotes={draft}
        selectedNoteIds={selected}
        selectionTimeRange={{ start: 0.5, end: 1.0 }}
        onDraftChange={setDraft}
        onCancel={() => setDraft(null)}
        onSelectNote={(id) => setSelected([id])}
      />
      <output data-testid="draft">{JSON.stringify(draft)}</output>
      <output data-testid="action">{JSON.stringify(workspace.pianoRollCorrectionAction)}</output>
    </>
  );
}

function renderHarness() {
  return render(
    <WorkspaceProvider>
      <Harness />
    </WorkspaceProvider>,
  );
}

describe("PianoRollCorrectionPanel", () => {
  it("changes selected pitch and saves a region-safe correction action", () => {
    renderHarness();
    fireEvent.click(screen.getByRole("button", { name: "Pitch +1" }));
    expect(screen.getByTestId("draft").textContent).toContain('"pitch":61');

    fireEvent.click(screen.getByRole("button", { name: "Save correction" }));
    const action = screen.getByTestId("action").textContent ?? "";
    expect(action).toContain('"sourceVersionId":"source-v1"');
    expect(action).toContain('"pitch":61');
    expect(action).toContain('"pitch":64');
  });

  it("removes a selected note without discarding its in-span neighbor", () => {
    renderHarness();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByTestId("draft").textContent).not.toContain('"id":"target"');
    expect(screen.getByTestId("draft").textContent).toContain('"id":"neighbor"');
  });

  it("adds a missing note across the selected duration", () => {
    renderHarness();
    fireEvent.change(screen.getByLabelText("MIDI pitch for missing note"), { target: { value: "72" } });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));
    const draft = screen.getByTestId("draft").textContent ?? "";
    expect(draft).toContain('"pitch":72');
    expect(draft).toContain('"start":0.5');
    expect(draft).toContain('"end":1');
  });

  it("cancels without creating a correction action", () => {
    renderHarness();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByTestId("draft").textContent).toBe("null");
    expect(screen.getByTestId("action").textContent).toBe("null");
  });
});
