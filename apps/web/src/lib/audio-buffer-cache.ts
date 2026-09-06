"use client";

const CACHE_LIMIT = 4;
const audioBufferCache = new Map<string, AudioBuffer>();
const audioBufferInflight = new Map<string, Promise<AudioBuffer>>();
let cacheGeneration = 0;

/**
 * Signed storage URLs are retrieval credentials, not artifact identity.
 *
 * Supabase re-signing can change only the query string for the same immutable
 * storage object. Strip query/hash credentials so an A -> B -> A revisit does
 * not redownload/redecode an unchanged recording just because its signed URL
 * was refreshed. Callers that already know an immutable Version ID may pass it
 * explicitly to getDecodedAudio as the stronger cache identity.
 */
export function stableAudioCacheKey(url: string): string {
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  try {
    const parsed = new URL(url, "http://localhost");
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return url;
  }
}

function remember(key: string, buffer: AudioBuffer): AudioBuffer {
  audioBufferCache.delete(key);
  audioBufferCache.set(key, buffer);
  if (audioBufferCache.size > CACHE_LIMIT) {
    const oldest = audioBufferCache.keys().next().value;
    if (oldest) audioBufferCache.delete(oldest);
  }
  return buffer;
}

/**
 * Fetch and decode an audio resource once per browser session.
 *
 * Waveform and Spectrogram share this cache so simultaneous consumers do not
 * redownload/redecode the same source. Cache clears advance a generation so a
 * decode that started before invalidation cannot later repopulate stale state.
 *
 * `cacheIdentity` should be an immutable Version ID when the caller has one.
 * Otherwise the canonical storage URL (without transient signing credentials)
 * is used as a safe fallback.
 */
export async function getDecodedAudio(
  url: string,
  cacheIdentity: string = stableAudioCacheKey(url),
): Promise<AudioBuffer> {
  const cached = audioBufferCache.get(cacheIdentity);
  if (cached) return remember(cacheIdentity, cached);

  const pending = audioBufferInflight.get(cacheIdentity);
  if (pending) return pending;

  const generation = cacheGeneration;
  const request = (async () => {
    const response = await fetch(url);
    if (!response.ok) throw new Error("audio request failed");

    const context = new AudioContext();
    try {
      const decoded = await context.decodeAudioData(await response.arrayBuffer());
      if (generation === cacheGeneration) remember(cacheIdentity, decoded);
      return decoded;
    } finally {
      void context.close();
    }
  })();

  let ownedRequest: Promise<AudioBuffer>;
  ownedRequest = request.finally(() => {
    if (audioBufferInflight.get(cacheIdentity) === ownedRequest) {
      audioBufferInflight.delete(cacheIdentity);
    }
  });

  audioBufferInflight.set(cacheIdentity, ownedRequest);
  return ownedRequest;
}

export function clearDecodedAudioCache(): void {
  cacheGeneration += 1;
  audioBufferCache.clear();
  audioBufferInflight.clear();
}
