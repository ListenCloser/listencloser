"use client";

const CACHE_LIMIT = 4;
const audioBufferCache = new Map<string, AudioBuffer>();
const audioBufferInflight = new Map<string, Promise<AudioBuffer>>();
let cacheGeneration = 0;

function remember(url: string, buffer: AudioBuffer): AudioBuffer {
  audioBufferCache.delete(url);
  audioBufferCache.set(url, buffer);
  if (audioBufferCache.size > CACHE_LIMIT) {
    const oldest = audioBufferCache.keys().next().value;
    if (oldest) audioBufferCache.delete(oldest);
  }
  return buffer;
}

/**
 * Fetch and decode an audio URL once per browser session.
 *
 * Waveform and Spectrogram share this cache so simultaneous consumers do not
 * redownload/redecode the same source. Cache clears advance a generation so a
 * decode that started before invalidation cannot later repopulate stale state.
 */
export async function getDecodedAudio(url: string): Promise<AudioBuffer> {
  const cached = audioBufferCache.get(url);
  if (cached) return remember(url, cached);

  const pending = audioBufferInflight.get(url);
  if (pending) return pending;

  const generation = cacheGeneration;
  const request = (async () => {
    const response = await fetch(url);
    if (!response.ok) throw new Error("audio request failed");

    const context = new AudioContext();
    try {
      const decoded = await context.decodeAudioData(await response.arrayBuffer());
      if (generation === cacheGeneration) remember(url, decoded);
      return decoded;
    } finally {
      void context.close();
    }
  })();

  let ownedRequest: Promise<AudioBuffer>;
  ownedRequest = request.finally(() => {
    if (audioBufferInflight.get(url) === ownedRequest) {
      audioBufferInflight.delete(url);
    }
  });

  audioBufferInflight.set(url, ownedRequest);
  return ownedRequest;
}

export function clearDecodedAudioCache(): void {
  cacheGeneration += 1;
  audioBufferCache.clear();
  audioBufferInflight.clear();
}
