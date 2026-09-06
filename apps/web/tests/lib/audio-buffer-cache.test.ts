import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearDecodedAudioCache,
  getDecodedAudio,
  stableAudioCacheKey,
} from "@/lib/audio-buffer-cache";

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
};

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("audio-buffer-cache", () => {
  let decodes: Deferred<AudioBuffer>[];
  let decodeCalls: number;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clearDecodedAudioCache();
    decodes = [];
    decodeCalls = 0;

    class FakeAudioContext {
      decodeAudioData(): Promise<AudioBuffer> {
        const next = decodes[decodeCalls];
        decodeCalls += 1;
        if (!next) throw new Error("unexpected decode");
        return next.promise;
      }

      close(): Promise<void> {
        return Promise.resolve();
      }
    }

    fetchMock = vi.fn(async () => ({
      ok: true,
      arrayBuffer: async () => new ArrayBuffer(1),
    }));

    vi.stubGlobal("AudioContext", FakeAudioContext);
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    clearDecodedAudioCache();
    vi.unstubAllGlobals();
  });

  it("deduplicates simultaneous consumers and reuses the decoded buffer", async () => {
    const decode = deferred<AudioBuffer>();
    const buffer = { duration: 12 } as AudioBuffer;
    decodes.push(decode);

    const first = getDecodedAudio("https://audio.test/source.wav");
    const second = getDecodedAudio("https://audio.test/source.wav");

    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(decodeCalls).toBe(1);
    });

    decode.resolve(buffer);

    await expect(first).resolves.toBe(buffer);
    await expect(second).resolves.toBe(buffer);
    await expect(getDecodedAudio("https://audio.test/source.wav")).resolves.toBe(buffer);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("treats rotated signing credentials as the same immutable audio object", async () => {
    const decode = deferred<AudioBuffer>();
    const buffer = { duration: 14 } as AudioBuffer;
    decodes.push(decode);

    const firstUrl = "https://storage.test/object/audio.wav?token=first&expires=1";
    const rotatedUrl = "https://storage.test/object/audio.wav?token=second&expires=2";

    expect(stableAudioCacheKey(firstUrl)).toBe(stableAudioCacheKey(rotatedUrl));

    const first = getDecodedAudio(firstUrl);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    decode.resolve(buffer);
    await expect(first).resolves.toBe(buffer);

    await expect(getDecodedAudio(rotatedUrl)).resolves.toBe(buffer);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(decodeCalls).toBe(1);
  });

  it("lets callers use immutable Version identity across unrelated retrieval URLs", async () => {
    const decode = deferred<AudioBuffer>();
    const buffer = { duration: 16 } as AudioBuffer;
    decodes.push(decode);

    const first = getDecodedAudio(
      "https://storage-a.test/object.wav?token=one",
      "version-1",
    );
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    decode.resolve(buffer);
    await expect(first).resolves.toBe(buffer);

    await expect(
      getDecodedAudio("https://storage-b.test/new-route.wav?token=two", "version-1"),
    ).resolves.toBe(buffer);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(decodeCalls).toBe(1);
  });

  it("keeps distinct immutable storage paths isolated", async () => {
    const firstDecode = deferred<AudioBuffer>();
    const secondDecode = deferred<AudioBuffer>();
    const firstBuffer = { duration: 8 } as AudioBuffer;
    const secondBuffer = { duration: 9 } as AudioBuffer;
    decodes.push(firstDecode, secondDecode);

    const first = getDecodedAudio("https://storage.test/object/a.wav?token=one");
    const second = getDecodedAudio("https://storage.test/object/b.wav?token=one");

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    firstDecode.resolve(firstBuffer);
    secondDecode.resolve(secondBuffer);

    await expect(first).resolves.toBe(firstBuffer);
    await expect(second).resolves.toBe(secondBuffer);
    expect(decodeCalls).toBe(2);
  });

  it("does not let a stale decode repopulate cache or erase a newer in-flight request", async () => {
    const staleDecode = deferred<AudioBuffer>();
    const freshDecode = deferred<AudioBuffer>();
    const staleBuffer = { duration: 10 } as AudioBuffer;
    const freshBuffer = { duration: 20 } as AudioBuffer;
    decodes.push(staleDecode, freshDecode);

    const staleRequest = getDecodedAudio("https://audio.test/source.wav");
    await vi.waitFor(() => expect(decodeCalls).toBe(1));

    clearDecodedAudioCache();

    const freshRequest = getDecodedAudio("https://audio.test/source.wav");
    await vi.waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(decodeCalls).toBe(2);
    });

    staleDecode.resolve(staleBuffer);
    await expect(staleRequest).resolves.toBe(staleBuffer);

    const dedupedFreshRequest = getDecodedAudio("https://audio.test/source.wav");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    freshDecode.resolve(freshBuffer);
    await expect(freshRequest).resolves.toBe(freshBuffer);
    await expect(dedupedFreshRequest).resolves.toBe(freshBuffer);

    await expect(getDecodedAudio("https://audio.test/source.wav")).resolves.toBe(freshBuffer);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
