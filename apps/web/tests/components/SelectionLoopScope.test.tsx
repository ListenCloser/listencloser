import { useEffect } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TransportBar from "@/components/workspace/TransportBar";
import { TransportProvider, useTransport, type PlaybackSource } from "@/lib/stores/transport";
import { WorkspaceProvider, useWorkspace } from "@/lib/stores/workspace";

const original: PlaybackSource = {
  id: "original-v1",
  label: "Original",
  url: "/audio/original.wav",
  kind: "audio",
  role: "original",
};

function Harness() {
  const { workspace, setSelection, clearSelection } = useWorkspace();
  const { transport, replaceSources } = useTransport();

  useEffect(() => {
    replaceSources([original], original.id, false);
  }, [replaceSources]);

  const range = workspace.selection?.timeRange;
  return (
    <>
      <button
        type="button"
        onClick={() => setSelection({
          timeRange: { start: 2, end: 4, domain: "performance" },
          provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
        })}
      >
        Select A
      </button>
      <button
        type="button"
        onClick={() => setSelection({
          timeRange: { start: 6, end: 9, domain: "performance" },
          provenance: { origin: "piano_roll", timeExact: true, measureApproximate: false },
        })}
      >
        Select B
      </button>
      <button type="button" onClick={clearSelection}>Clear selection</button>
      <output data-testid="selection-range">
        {range ? `${range.start}-${range.end}` : "none"}
      </output>
      <output data-testid="loop-range">
        {transport.loopStart == null || transport.loopEnd == null
          ? `none:${transport.loopEnabled ? "on" : "off"}`
          : `${transport.loopStart}-${transport.loopEnd}:${transport.loopEnabled ? "on" : "off"}`}
      </output>
    </>
  );
}

function renderHarness() {
  return render(
    <WorkspaceProvider>
      <TransportProvider>
        <TransportBar />
        <Harness />
      </TransportProvider>
    </WorkspaceProvider>,
  );
}

describe("shared selection loop scope", () => {
  beforeEach(() => {
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  });

  it("uses one Loop control and follows the visible passage until deselected", async () => {
    const user = userEvent.setup();
    renderHarness();

    const loopControl = () => screen.getByRole("button", { name: "Toggle selected passage loop" });
    await screen.findByRole("button", { name: "Toggle selected passage loop" });
    expect(loopControl()).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Loop selection" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Select A" }));
    await waitFor(() => expect(loopControl()).toBeEnabled());
    await user.click(loopControl());
    await waitFor(() => expect(screen.getByTestId("loop-range")).toHaveTextContent("2-4:on"));

    await user.click(screen.getByRole("button", { name: "Select B" }));
    await waitFor(() => expect(screen.getByTestId("loop-range")).toHaveTextContent("6-9:on"));

    await user.click(screen.getByRole("button", { name: "Clear selection" }));
    await waitFor(() => expect(screen.getByTestId("loop-range")).toHaveTextContent("none:off"));
    expect(loopControl()).toBeDisabled();
  });
});
