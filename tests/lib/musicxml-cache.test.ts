import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getMusicXml } from "@/lib/musicxml-cache";

function queryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getMusicXml", () => {
  it("reuses immutable score text across signed URL rotation", async () => {
    const client = queryClient();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue("<score-partwise>cached</score-partwise>"),
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = await getMusicXml("score-version-1", "https://storage.test/score.xml?token=first", client);
    const revisited = await getMusicXml("score-version-1", "https://storage.test/score.xml?token=rotated", client);

    expect(first).toBe(revisited);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("https://storage.test/score.xml?token=first");
  });

  it("joins one in-flight fetch for concurrent consumers", async () => {
    const client = queryClient();
    let resolveText: ((value: string) => void) | undefined;
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: () => new Promise<string>((resolve) => { resolveText = resolve; }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const first = getMusicXml("score-version-1", "https://storage.test/score.xml", client);
    const second = getMusicXml("score-version-1", "https://storage.test/score.xml", client);

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    resolveText?.("<score-partwise>shared</score-partwise>");

    await expect(first).resolves.toContain("shared");
    await expect(second).resolves.toContain("shared");
  });

  it("keeps different score Versions isolated", async () => {
    const client = queryClient();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, text: vi.fn().mockResolvedValue("<score>A</score>") })
      .mockResolvedValueOnce({ ok: true, text: vi.fn().mockResolvedValue("<score>B</score>") });
    vi.stubGlobal("fetch", fetchMock);

    await getMusicXml("score-version-a", "https://storage.test/a.xml", client);
    await getMusicXml("score-version-b", "https://storage.test/b.xml", client);

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not cache failed score requests", async () => {
    const client = queryClient();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, text: vi.fn() })
      .mockResolvedValueOnce({ ok: true, text: vi.fn().mockResolvedValue("<score>retry</score>") });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getMusicXml("score-version-1", "https://storage.test/score.xml", client)).rejects.toThrow("score request failed");
    await expect(getMusicXml("score-version-1", "https://storage.test/score.xml", client)).resolves.toContain("retry");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
