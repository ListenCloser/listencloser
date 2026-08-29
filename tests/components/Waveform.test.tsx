import { act, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Waveform from "@/components/Waveform";
import { getDecodedAudio } from "@/lib/audio-buffer-cache";

vi.mock("@/lib/audio-buffer-cache", () => ({
  getDecodedAudio: vi.fn(),
}));

const mockGetDecodedAudio = vi.mocked(getDecodedAudio);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function decoded(duration: number) {
  return {
    duration,
    getChannelData: () => new Float32Array([0, 0.25, -0.4, 0.6, -0.2, 0.1]),
  } as unknown as AudioBuffer;
}

const canvasContext = {
  clearRect: vi.fn(),
  fillRect: vi.fn(),
  fillText: vi.fn(),
  strokeRect: vi.fn(),
  beginPath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  stroke: vi.fn(),
  fillStyle: "",
  strokeStyle: "",
  globalAlpha: 1,
  lineWidth: 1,
  font: "",
  textAlign: "center" as CanvasTextAlign,
};

describe("Waveform source continuity", () => {
  beforeEach(() => {
    mockGetDecodedAudio.mockReset();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(canvasContext as unknown as CanvasRenderingContext2D);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns to a neutral frame immediately when the source changes", async () => {
    const first = deferred<AudioBuffer>();
    const second = deferred<AudioBuffer>();
    mockGetDecodedAudio
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const { rerender } = render(<Waveform url="source-a.wav" position={0} />);
    const canvas = screen.getByTestId("waveform-canvas");

    expect(canvas).toHaveAttribute("data-waveform-state", "loading");
    expect(canvas).toHaveAttribute("data-waveform-segments", "0");
    expect(canvas).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Decoding recording…")).toBeInTheDocument();

    await act(async () => {
      first.resolve(decoded(2));
      await first.promise;
    });
    await waitFor(() => expect(canvas).toHaveAttribute("data-waveform-state", "ready"));
    expect(Number(canvas.getAttribute("data-waveform-segments"))).toBeGreaterThan(0);

    rerender(<Waveform url="source-b.wav" position={0} />);

    expect(canvas).toHaveAttribute("data-waveform-state", "loading");
    expect(canvas).toHaveAttribute("data-waveform-segments", "0");
    expect(screen.getByText("Decoding recording…")).toBeInTheDocument();

    await act(async () => {
      second.resolve(decoded(3));
      await second.promise;
    });
    await waitFor(() => expect(canvas).toHaveAttribute("data-waveform-state", "ready"));
    expect(Number(canvas.getAttribute("data-waveform-segments"))).toBeGreaterThan(0);
  });
});
