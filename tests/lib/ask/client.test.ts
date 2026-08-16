import { afterEach, describe, expect, it, vi } from "vitest";
import { askMusic } from "@/lib/ask/client";
import { deriveAskContext } from "@/lib/ask/context";
import type { AskResponse } from "@/lib/ask/types";
import type { PlaybackSource } from "@/lib/stores/transport";

const perfSource: PlaybackSource = {
  id: "perf",
  label: "Original",
  url: "data:audio/wav;base64,perf",
  kind: "audio",
  role: "original",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("askMusic", () => {
  it("POSTs the question and the derived AskContext to /api/v1/ask", async () => {
    const response: AskResponse = {
      answer: "An answer.",
      references: [{ type: "time", start: 4, end: 8, domain: "performance" }],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => response,
    });
    vi.stubGlobal("fetch", fetchMock);

    const context = deriveAskContext("work-1", "listen", 15, perfSource, null, [], 120);
    expect(context).not.toBeNull();

    const result = await askMusic({ question: "What is this?", context: context! });

    expect(result).toEqual(response);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/ask");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(body.question).toBe("What is this?");
    expect(body.context).toEqual(context);
  });

  it("throws a readable error when the backend returns an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({ error: "Ask is unavailable" }),
    }));

    const context = deriveAskContext("work-1", "listen", 15, perfSource, null, [], 120);
    await expect(askMusic({ question: "Hi", context: context! })).rejects.toThrow("Ask is unavailable");
  });

  it("derives context at send time so selection changes affect the next request", () => {
    const withoutSelection = deriveAskContext("work-1", "listen", 15, perfSource, null, [], 120);
    const withSelection = deriveAskContext(
      "work-1", "listen", 15, perfSource,
      { timeRange: { start: 31, end: 38, domain: "performance" }, provenance: { origin: "waveform", timeExact: true, measureApproximate: false } },
      [], 120,
    );
    expect(withoutSelection?.selection).toBeNull();
    expect(withSelection?.selection?.timeRange).toEqual({ start: 31, end: 38, domain: "performance" });
  });
});