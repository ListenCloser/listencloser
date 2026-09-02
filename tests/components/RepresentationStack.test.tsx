import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import RepresentationStack from "@/components/workspace/RepresentationStack";
import { WORKSPACE_ORIENTATION_EVENT } from "@/lib/inspector/orientation";
import { useWorkspace, WorkspaceProvider } from "@/lib/stores/workspace";

const scoreRendererMocks = vi.hoisted(() => ({
  preloadScoreRenderer: vi.fn(),
}));

vi.mock("@/lib/score-renderer", () => ({
  preloadScoreRenderer: scoreRendererMocks.preloadScoreRenderer,
}));

vi.mock("@/components/workspace/representations/registry", () => {
  const definitions = [
    {
      id: "listen",
      title: "Waveform",
      description: "test waveform",
      temporal: true,
      available: () => true,
      component: ({ orientationCue = false }: { orientationCue?: boolean }) => (
        <div data-testid="waveform-view" data-selection-emphasized={orientationCue ? "true" : undefined}>
          <input aria-label="Waveform local state" />
        </div>
      ),
    },
    {
      id: "score",
      title: "Score",
      description: "test score",
      temporal: true,
      available: () => true,
      component: ({ orientationCue = false }: { orientationCue?: boolean }) => (
        <div data-testid="score-view" data-selection-emphasized={orientationCue ? "true" : undefined}>
          <input aria-label="Score local state" />
        </div>
      ),
    },
    {
      id: "spectrogram",
      title: "Spectrogram",
      description: "test unavailable representation",
      temporal: true,
      available: () => false,
      component: () => <div data-testid="spectrogram-view" />,
    },
  ];
  const availableDefinitions = definitions.slice(0, 2);

  return {
    REPRESENTATIONS: definitions,
    availableRepresentations: () => availableDefinitions,
    representationById: (id: string) => definitions.find((definition) => definition.id === id),
  };
});

afterEach(() => {
  scoreRendererMocks.preloadScoreRenderer.mockReset();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function mockAnimationFrame() {
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => (
    window.setTimeout(() => callback(0), 1)
  ));
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => window.clearTimeout(id));
}

function SelectionHarness() {
  const { workspace, setSelection } = useWorkspace();

  return (
    <div>
      <button
        type="button"
        onClick={() => setSelection({
          timeRange: { start: 12, end: 18, domain: "performance" },
          provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
        })}
      >
        Select passage
      </button>
      <span data-testid="selection-state">{workspace.selection ? "selected" : "none"}</span>
      <input aria-label="Editable input" />
      <textarea aria-label="Editable textarea" />
      <select aria-label="Editable select" defaultValue="draft">
        <option value="draft">Draft</option>
      </select>
      <div contentEditable suppressContentEditableWarning aria-label="Editable content">
        Draft
      </div>
      <button
        type="button"
        onKeyDown={(event) => {
          if (event.key === "Escape") event.preventDefault();
        }}
      >
        Consumed escape
      </button>
    </div>
  );
}

describe("RepresentationStack", () => {
  it("keeps unavailable representations in the tab shell instead of inserting them later", () => {
    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    expect(screen.getByRole("tab", { name: "Waveform" })).toBeEnabled();
    expect(screen.getByRole("tab", { name: "Score" })).toBeEnabled();
    expect(screen.getByRole("tab", { name: "Spectrogram" })).toBeDisabled();
    expect(screen.queryByTestId("spectrogram-view")).not.toBeInTheDocument();
  });

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

  it("keeps passage selection when Escape belongs to an editable or consumed control", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <SelectionHarness />
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Select passage" }));
    expect(screen.getByTestId("selection-state")).toHaveTextContent("selected");

    for (const label of ["Editable input", "Editable textarea", "Editable select", "Editable content"]) {
      fireEvent.keyDown(screen.getByLabelText(label), { key: "Escape" });
      expect(screen.getByTestId("selection-state")).toHaveTextContent("selected");
    }

    fireEvent.keyDown(screen.getByRole("button", { name: "Consumed escape" }), { key: "Escape" });
    expect(screen.getByTestId("selection-state")).toHaveTextContent("selected");
  });

  it("clears passage selection for an unconsumed workspace Escape", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceProvider>
        <SelectionHarness />
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Select passage" }));
    expect(screen.getByTestId("selection-state")).toHaveTextContent("selected");

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.getByTestId("selection-state")).toHaveTextContent("none");
  });

  it("warms the Score renderer only after deliberate pointer dwell and cancels incidental hover", () => {
    vi.useFakeTimers();
    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    const scoreTab = screen.getByRole("tab", { name: "Score" });

    fireEvent.pointerEnter(scoreTab);
    act(() => {
      vi.advanceTimersByTime(119);
    });
    expect(scoreRendererMocks.preloadScoreRenderer).not.toHaveBeenCalled();

    fireEvent.pointerLeave(scoreTab);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(scoreRendererMocks.preloadScoreRenderer).not.toHaveBeenCalled();

    fireEvent.pointerEnter(scoreTab);
    act(() => {
      vi.advanceTimersByTime(120);
    });
    expect(scoreRendererMocks.preloadScoreRenderer).toHaveBeenCalledTimes(1);
  });

  it("warms the Score renderer immediately for keyboard focus intent", () => {
    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    fireEvent.focus(screen.getByRole("tab", { name: "Score" }));

    expect(scoreRendererMocks.preloadScoreRenderer).toHaveBeenCalledTimes(1);
  });

  it("briefly strengthens the active representation's real selection without remounting it", () => {
    vi.useFakeTimers();
    mockAnimationFrame();

    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    const waveformView = screen.getByTestId("waveform-view");
    const waveformState = screen.getByRole("textbox", { name: "Waveform local state" });
    expect(waveformView).not.toHaveAttribute("data-selection-emphasized");

    act(() => {
      window.dispatchEvent(new Event(WORKSPACE_ORIENTATION_EVENT));
      vi.advanceTimersByTime(1);
    });

    expect(waveformView).toHaveAttribute("data-selection-emphasized", "true");
    expect(screen.getByRole("textbox", { name: "Waveform local state" })).toBe(waveformState);

    act(() => {
      vi.advanceTimersByTime(560);
    });

    expect(waveformView).not.toHaveAttribute("data-selection-emphasized");
  });

  it("skips the transient cue for reduced-motion users", () => {
    vi.useFakeTimers();
    mockAnimationFrame();
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));

    render(
      <WorkspaceProvider>
        <RepresentationStack signedIn canImport />
      </WorkspaceProvider>,
    );

    act(() => {
      window.dispatchEvent(new Event(WORKSPACE_ORIENTATION_EVENT));
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByTestId("waveform-view")).not.toHaveAttribute("data-selection-emphasized");
  });
});
