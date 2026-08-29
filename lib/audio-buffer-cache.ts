"use client";

const CACHE_LIMIT = 4;
const audioBufferCache = new Map<string, AudioBuffer>();
const audioBufferInflight = new Map<string, Promise<AudioBuffer>>();

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
 * Waveform and spectrogram previously maintained separate decode lifecycles,
 * so returning to a saved recording could download/decode the same source
 * again. This shared LRU also deduplicates simultaneous consumers.
 */
export async function getDecodedAudio(url: string): Promise<AudioBuffer> {
  const cached = audioBufferCache.get(url);
  if (cached) return remember(url, cached);

  const pending = audioBufferInflight.get(url);
  if (pending) return pending;

  const request = (async () => {
    const response = await fetch(url);
    if (!response.ok) throw new Error("audio request failed");
    const context = new AudioContext();
    try {
      const decoded = await context.decodeAudioData(await response.arrayBuffer());
      return remember(url, decoded);
    } finally {
      void context.close();
    }
  })().finally(() => {
    audioBufferInflight.delete(url);
  });

  audioBufferInflight.set(url, request);
  return request;
}

export function clearDecodedAudioCache(): void {
  audioBufferCache.clear();
  audioBufferInflight.clear();
}
