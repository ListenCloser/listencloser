import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase", () => ({ supabase: null }));

import { apiFetch, ApiRequestError } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch structured failures", () => {
  it("preserves status and request id from the proxy response body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: "Ask timed out.", request_id: "ask-req-123" }),
      { status: 504, headers: { "content-type": "application/json", "x-request-id": "ask-req-header" } },
    )));

    let failure: unknown;
    try {
      await apiFetch("/api/v1/ask", { method: "POST", body: "{}" });
    } catch (cause) {
      failure = cause;
    }

    expect(failure).toBeInstanceOf(ApiRequestError);
    expect(failure).toMatchObject({
      message: "Ask timed out.",
      status: 504,
      requestId: "ask-req-123",
    });
  });

  it("falls back to the response header correlation id", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ error: "backend error" }),
      { status: 502, headers: { "content-type": "application/json", "x-request-id": "ask-req-header" } },
    )));

    await expect(apiFetch("/api/v1/ask")).rejects.toMatchObject({
      status: 502,
      requestId: "ask-req-header",
    });
  });
});
