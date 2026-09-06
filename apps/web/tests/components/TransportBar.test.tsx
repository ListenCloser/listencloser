import { render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TransportBar from "@/components/workspace/TransportBar";
import { TransportProvider, useTransport, type PlaybackSource } from "@/lib/stores/transport";
import { WorkspaceProvider } from "@/lib/stores/workspace";

const original: PlaybackSource = {
  id: "original-version",
  label: "Original",
  url: "https://storage.example/original.wav",
  kind: "audio",
  role: "original",
};

const score: PlaybackSource = {
  id: "score-version",
  label: "Score",
  url: "https://storage.example/score.wav",
  kind: "audio",
  role: "score",
};

function Harness({ activeId }: { activeId: string }) {
  const { replaceSources } = useTransport();

  useEffect(() => {
    replaceSources([original, score], activeId);
  }, [activeId, replaceSources]);

  return <TransportBar />;
}

function renderTransport(activeId: string) {
  return render(
    <WorkspaceProvider>
      <TransportProvider>
        <Harness activeId={activeId} />
      </TransportProvider>
    </WorkspaceProvider>,
  );
}

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TransportBar playback source truth", () => {
  it("makes the original recording explicit in both source and play controls", async () => {
    renderTransport(original.id);

    const source = await screen.findByRole("button", { name: "Playback source: Original" });
    expect(source).toHaveTextContent("Listening · Original");
    expect(screen.getByRole("button", { name: "Play Original" })).toBeEnabled();
  });

  it("does not call a score render a recording", async () => {
    renderTransport(score.id);

    const source = await screen.findByRole("button", { name: "Playback source: Score" });
    expect(source).toHaveTextContent("Listening · Score");
    await waitFor(() => expect(screen.getByRole("button", { name: "Play Score" })).toBeEnabled());
    expect(screen.queryByRole("button", { name: "Play recording" })).not.toBeInTheDocument();
  });
});
