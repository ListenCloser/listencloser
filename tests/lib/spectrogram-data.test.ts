import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getDecodedAudio: vi.fn(),
  computeSpectrogram: vi.fn(),
  stableAudioCacheKey: vi.fn((url: string) => url.split("?")[0]),
}));

vi.mock("@/lib/audio-buffer-cache", () => ({
  getDecodedAudio: mocks.getDecodedAudio,
  stableAudioCacheKey: mocks.stableAudioCacheKey,
}));

vi.mock("@/lib/spectrogram", () => ({
  computeSpectrogram: mocks.computeSpectrogram,
}));

import { getSpectrogramData } from "@/lib/spectrogram-data";

const samples = new Float32Array([0, 0.25, -0.25, 0]);
const buffer = {
  numberOfChannels: 1,
  length: samples.length,
  sampleRate: 44_100,
  getChannelData: () => samples,
} as AudioBuffer;

const result = {
  columns: 2,
  bins: 2,
  duration: 1,
  minFrequency: 40,
  maxFrequency: 22_050,
  values: new Uint8Array([1, 2, 3, 4]),
};

function queryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
    },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.stableAudioCacheKey.mockImplementation((url: string) => url.split("?")[0]);
  mocks.getDecodedAudio.mockResolvedValue(buffer);
  mocks.computeSpectrogram.mockResolvedValue(result);
});

describe("getSpectrogramData", () => {
  it("reuses a completed FFT by immutable source Version ID across signed URL changes", async () => {
    const client = queryClient();

    const first = await getSpectrogramData(
      "https://storage.test/audio.wav?token=first",
      { cacheIdentity: "version-1" },
      client,
    );
    const revisited = await getSpectrogramData(
      "https://storage.test/audio.wav?token=refreshed",
      { cacheIdentity: "version-1" },
      client,
    );

    expect(revisited).toBe(first);
    expect(mocks.getDecodedAudio).toHaveBeenCalledTimes(1);
    expect(mocks.getDecodedAudio).toHaveBeenCalledWith(
      "https://storage.test/audio.wav?token=first",
      "version-1",
    );
    expect(mocks.computeSpectrogram).toHaveBeenCalledTimes(1);
  });

  it("joins one in-flight computation for concurrent consumers", async () => {
    const client = queryClient();
    let resolveCompute: ((value: typeof result) => void) | undefined;
    mocks.computeSpectrogram.mockImplementation(
      () => new Promise<typeof result>((resolve) => { resolveCompute = resolve; }),
    );

    const first = getSpectrogramData("https://storage.test/audio.wav", { cacheIdentity: "version-1" }, client);
    const second = getSpectrogramData("https://storage.test/audio.wav", { cacheIdentity: "version-1" }, client);

    await vi.waitFor(() => expect(mocks.computeSpectrogram).toHaveBeenCalledTimes(1));
    resolveCompute?.(result);

    await expect(first).resolves.toBe(result);
    await expect(second).resolves.toBe(result);
    expect(mocks.getDecodedAudio).toHaveBeenCalledTimes(1);
  });

  it("falls back to stable storage identity and preserves first-visit progress", async () => {
    const client = queryClient();
    const onProgress = vi.fn();

    await getSpectrogramData(
      "https://storage.test/audio.wav?token=first",
      { onProgress },
      client,
    );
    await getSpectrogramData(
      "https://storage.test/audio.wav?token=second",
      {},
      client,
    );

    expect(mocks.stableAudioCacheKey).toHaveBeenCalledTimes(2);
    expect(mocks.getDecodedAudio).toHaveBeenCalledTimes(1);
    expect(mocks.computeSpectrogram).toHaveBeenCalledTimes(1);
    expect(mocks.computeSpectrogram.mock.calls[0]?.[2]).toEqual({ onProgress });
  });
});
