import { beforeEach, describe, expect, it, vi } from "vitest";

const { getSession } = vi.hoisted(() => ({
  getSession: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: { getSession } },
}));

import {
  requireOpenApiData,
  throwOpenApiError,
  withCurrentSupabaseAuth,
} from "@/lib/openapi-client";

describe("OpenAPI transport", () => {
  beforeEach(() => {
    getSession.mockReset();
  });

  it("reads the current Supabase access token for every request", async () => {
    getSession
      .mockResolvedValueOnce({ data: { session: { access_token: "token-a" } } })
      .mockResolvedValueOnce({ data: { session: { access_token: "token-b" } } });

    const first = await withCurrentSupabaseAuth(new Request("https://listencloser.test/api/v1/projects"));
    const second = await withCurrentSupabaseAuth(new Request("https://listencloser.test/api/v1/projects"));

    expect(getSession).toHaveBeenCalledTimes(2);
    expect(first.headers.get("Authorization")).toBe("Bearer token-a");
    expect(second.headers.get("Authorization")).toBe("Bearer token-b");
  });

  it("keeps requests anonymous when no session exists", async () => {
    getSession.mockResolvedValue({ data: { session: null } });
    const request = await withCurrentSupabaseAuth(new Request("https://listencloser.test/api/v1/projects"));
    expect(request.headers.has("Authorization")).toBe(false);
  });

  it("preserves the existing structured API error message contract", () => {
    expect(() => throwOpenApiError({ error: "denied" }, new Response(null, { status: 403 }))).toThrow("denied");
    expect(() => throwOpenApiError({ detail: "invalid" }, new Response(null, { status: 422 }))).toThrow("Request failed: 422");
  });

  it("returns successful generated data and rejects missing data", () => {
    const response = new Response(null, { status: 200 });
    expect(requireOpenApiData({ data: ["ok"], response })).toEqual(["ok"]);
    expect(() => requireOpenApiData({ error: { error: "missing" }, response: new Response(null, { status: 404 }) })).toThrow("missing");
  });
});
