import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

describe("proxyToBackend request correlation", () => {
  beforeEach(() => {
    process.env.MUSIC_BACKEND_URL = "https://backend.example.test";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.MUSIC_BACKEND_URL;
  });

  it("forwards one request id to FastAPI and returns it on an upstream failure", async () => {
    const backendFetch = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Ask provider timed out" }),
      { status: 504, headers: { "content-type": "application/json", "x-request-id": "ask-req-123" } },
    ));
    vi.stubGlobal("fetch", backendFetch);
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    const request = new NextRequest("http://localhost/api/v1/ask", {
      method: "POST",
      headers: {
        authorization: "Bearer token",
        "content-type": "application/json",
        "x-request-id": "ask-req-123",
      },
      body: JSON.stringify({ question: "Why?" }),
    });

    const response = await proxyToBackend(request, "/api/v1/ask", 60_000);
    const body = await response.json();

    expect(backendFetch).toHaveBeenCalledOnce();
    expect(backendFetch).toHaveBeenCalledWith(
      "https://backend.example.test/api/v1/ask",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer token",
          "x-request-id": "ask-req-123",
        }),
      }),
    );
    expect(response.status).toBe(504);
    expect(response.headers.get("x-request-id")).toBe("ask-req-123");
    expect(body).toEqual({ error: "Ask provider timed out", request_id: "ask-req-123" });
    expect(console.error).toHaveBeenCalledWith(
      "backend_proxy_upstream_error",
      expect.objectContaining({ requestId: "ask-req-123", path: "/api/v1/ask", status: 504 }),
    );
  });

  it("returns the proxy request id when the backend cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("unreachable")));
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    const request = new NextRequest("http://localhost/api/v1/ask", {
      method: "POST",
      headers: { "x-request-id": "ask-req-456" },
      body: "{}",
    });

    const response = await proxyToBackend(request, "/api/v1/ask", 60_000);
    const body = await response.json();

    expect(response.status).toBe(502);
    expect(response.headers.get("x-request-id")).toBe("ask-req-456");
    expect(body).toEqual({ error: "Processing service unavailable", request_id: "ask-req-456" });
    expect(console.error).toHaveBeenCalledWith(
      "backend_proxy_failed",
      expect.objectContaining({ requestId: "ask-req-456", path: "/api/v1/ask" }),
    );
  });
});
