import { afterEach, describe, expect, it, vi } from "vitest";
import { AskRequestError, askMusic } from "@/lib/ask/client";
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

function context() {
  const value = deriveAskContext("work-1", "listen", 15, perfSource, null, [], 120);
  expect(value).not.toBeNull();
  return value!;
}

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

    const askContext = context();
    const result = await askMusic({ question: "What is this?", context: askContext });

    expect(result).toEqual(response);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/ask");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(body.question).toBe("What is this?");
    expect(body.context).toEqual(askContext);
  });

  it.each([
    [401, "Sign in again to use Ask."],
    [403, "Ask is not available for this workspace."],
    [429, "Ask is busy right now. Try again shortly."],
    [502, "Ask is temporarily unavailable."],
    [503, "Ask is temporarily unavailable."],
    [504, "Ask took too long."],
  ])("maps HTTP %s to bounded user-facing copy", async (status, expectedMessage) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status,
      headers: { get: () => null },
      json: async () => ({ error: "raw provider detail must not escape" }),
    }));

    try {
      await askMusic({ question: "Hi", context: context() });
      throw new Error("expected Ask failure");
    } catch (cause) {
      expect(cause).toBeInstanceOf(AskRequestError);
      expect(cause).toMatchObject({
        status,
        requestId: null,
        message: expectedMessage,
      });
      expect((cause as Error).message).not.toContain("raw provider detail");
    }
  });

  it("preserves the echoed request ID header while bounding backend details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: {
        get: (name: string) => name.toLowerCase() === "x-request-id" ? "req-header-123" : null,
      },
      json: async () => ({ error: "sensitive upstream provider failure" }),
    }));

    await expect(askMusic({ question: "Hi", context: context() })).rejects.toMatchObject({
      name: "AskRequestError",
      status: 503,
      requestId: "req-header-123",
      message: "Ask is temporarily unavailable.",
    });
  });

  it("falls back to a response request_id when the header is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 504,
      headers: { get: () => null },
      json: async () => ({ error: "gateway timeout detail", request_id: "req-body-456" }),
    }));

    await expect(askMusic({ question: "Hi", context: context() })).rejects.toMatchObject({
      name: "AskRequestError",
      status: 504,
      requestId: "req-body-456",
      message: "Ask took too long.",
    });
  });

  it("retains the bounded not-configured classification without exposing raw prose", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: { get: () => null },
      json: async () => ({ error: "Ask is not configured: provider secret missing" }),
    }));

    await expect(askMusic({ question: "Hi", context: context() })).rejects.toMatchObject({
      message: "Ask is not configured for this workspace.",
      status: 503,
    });
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
