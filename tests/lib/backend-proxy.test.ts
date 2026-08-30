import type { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { proxyToBackend } from "@/lib/backend";

function requestWithId(requestId: string): NextRequest {
  return {
    headers: new Headers({
      authorization: "Bearer test-token",
      "x-request-id": requestId,
    }),
    method: "POST",
    text: async () => JSON.stringify({ question: "What changed?" }),
  } as unknown as NextRequest;
}

describe("proxyToBackend request correlation", () => {
  const previousBackendUrl = process.env.MUSIC_BACKEND_URL;

  beforeEach(() => {
    process.env.MUSIC_BACKEND_URL = "https://backend.example.test";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    if (previousBackendUrl === undefined) delete process.env.MUSIC_BACKEND_URL;
    else process.env.MUSIC_BACKEND_URL = previousBackendUrl;
  });

  it("forwards the request id and returns the backend correlation id on upstream failures", async () => {
    const fetchMock = vi.fn(async (_url: string, init: RequestInit) => {
      const headers = init.headers as Record<string, string>;
      expect(headers["x-request-id"]).toBe("frontend-123");
      expect(headers.Authorization).toBe("Bearer test-token");
      return new Response(JSON.stringify({ detail: "Ask timed out." }), {
        status: 504,
        headers: {
          "Content-Type": "application/json",
          "x-request-id": "backend-456",
        },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const response = await proxyToBackend(requestWithId("frontend-123"), "/api/v1/ask", 1_000);

    expect(response.status).toBe(504);
    expect(response.headers.get("x-request-id")).toBe("backend-456");
    await expect(response.json()).resolves.toEqual({
      error: "Ask timed out.",
      request_id: "backend-456",
    });
    expect(errorSpy).toHaveBeenCalledWith(
      "backend_proxy_upstream_error",
      expect.objectContaining({
        requestId: "backend-456",
        path: "/api/v1/ask",
        status: 504,
      }),
    );
  });

  it("keeps the original correlation id when the backend cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const response = await proxyToBackend(requestWithId("frontend-789"), "/api/v1/ask", 1_000);

    expect(response.status).toBe(502);
    expect(response.headers.get("x-request-id")).toBe("frontend-789");
    await expect(response.json()).resolves.toEqual({
      error: "Processing service unavailable",
      request_id: "frontend-789",
    });
    expect(errorSpy).toHaveBeenCalledWith(
      "backend_proxy_failed",
      expect.objectContaining({
        requestId: "frontend-789",
        path: "/api/v1/ask",
      }),
    );
  });
});
