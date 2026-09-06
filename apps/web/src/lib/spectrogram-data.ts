"use client";

import type { QueryClient } from "@tanstack/react-query";
import { getDecodedAudio, stableAudioCacheKey } from "@/lib/audio-buffer-cache";
import { getQueryClient } from "@/lib/query-client";
import { computeSpectrogram, type SpectrogramData } from "@/lib/spectrogram";

const SPECTROGRAM_GC_MS = 5 * 60_000;

type SpectrogramLoadOptions = {
  cacheIdentity?: string;
  onProgress?: (completed: number, total: number) => void;
};

function mergedSamples(buffer: AudioBuffer): Float32Array {
  if (buffer.numberOfChannels === 1) return buffer.getChannelData(0);
  const length = buffer.length;
  const mixed = new Float32Array(length);
  for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let index = 0; index < length; index += 1) mixed[index] += data[index] / buffer.numberOfChannels;
  }
  return mixed;
}

function spectrogramQueryKey(cacheIdentity: string) {
  return ["representation-data", "spectrogram", cacheIdentity] as const;
}

/**
 * Lazily compute one spectrogram per immutable audio version and let the
 * application QueryClient own in-flight dedupe and bounded retention.
 *
 * This intentionally does not precompute Spectrogram for every Work. The first
 * actual consumer pays the FFT cost; a same-version remount or concurrent
 * consumer joins/reuses that result instead of repeating deterministic work.
 */
export async function getSpectrogramData(
  url: string,
  options: SpectrogramLoadOptions = {},
  queryClient: QueryClient = getQueryClient(),
): Promise<SpectrogramData> {
  const cacheIdentity = options.cacheIdentity ?? stableAudioCacheKey(url);
  const queryKey = spectrogramQueryKey(cacheIdentity);

  const cached = queryClient.getQueryData<SpectrogramData>(queryKey);
  if (cached) return cached;

  return queryClient.fetchQuery({
    queryKey,
    staleTime: Infinity,
    gcTime: SPECTROGRAM_GC_MS,
    queryFn: async () => {
      const buffer = await getDecodedAudio(url, cacheIdentity);
      return computeSpectrogram(mergedSamples(buffer), buffer.sampleRate, {
        onProgress: options.onProgress,
      });
    },
  });
}
