import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: { getSession: mocks.getSession },
  },
}));

describe("generated authenticated API transport", () => {
  beforeEach(() => {
    vi.resetModules();
    mocks.fetch.mockReset();
    mocks.getSession.mockReset();
    vi.stubGlobal("fetch", mocks.fetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads the current Supabase token for every generated request", async () => {
    mocks.getSession
      .mockResolvedValueOnce({ data: { session: { access_token: "token-a" } } })
      .mockResolvedValueOnce({ data: { session: { access_token: "token-b" } } });
    mocks.fetch.mockImplementation(async () =>
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const { apiClient } = await import("@/lib/api");
    await apiClient.GET("/api/v1/projects");
    await apiClient.GET("/api/v1/projects");

    expect(mocks.getSession).toHaveBeenCalledTimes(2);
    expect(mocks.fetch).toHaveBeenCalledTimes(2);

    const first = mocks.fetch.mock.calls[0]?.[0] as Request;
    const second = mocks.fetch.mock.calls[1]?.[0] as Request;
    expect(new URL(first.url).pathname).toBe("/api/v1/projects");
    expect(first.headers.get("Authorization")).toBe("Bearer token-a");
    expect(second.headers.get("Authorization")).toBe("Bearer token-b");
  });

  it("preserves the legacy structured API error message contract", async () => {
    const { apiResponseError } = await import("@/lib/api");
    expect(apiResponseError({ error: "not allowed" }, 403).message).toBe("not allowed");
    expect(apiResponseError({ detail: "ignored" }, 503).message).toBe("Request failed: 503");
  });
});
