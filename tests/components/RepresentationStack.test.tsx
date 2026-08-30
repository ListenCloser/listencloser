import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import RepresentationStack from "@/components/workspace/RepresentationStack";
import { WORKSPACE_ORIENTATION_EVENT } from "@/lib/inspector/orientation";
import { WorkspaceProvider } from "@/lib/stores/workspace";

vi.mock("@/lib/representations", () => {
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
