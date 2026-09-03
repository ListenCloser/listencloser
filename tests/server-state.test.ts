import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  createProject: vi.fn(),
  deleteWork: vi.fn(),
  getWorkBundle: vi.fn(),
  listProjects: vi.fn(),
  listWorks: vi.fn(),
}));

vi.mock("@/lib/api-client", () => api);

import { fetchWorkBundle, serverStateKeys } from "@/lib/server-state";

function queryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
}

describe("Work bundle server state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keys bundle state by immutable Work identity", () => {
    expect(serverStateKeys.workBundle("work-a")).toEqual(["works", "work-a", "bundle"]);
    expect(serverStateKeys.workBundle("work-b")).toEqual(["works", "work-b", "bundle"]);
  });

  it("deduplicates concurrent reads for the same Work through React Query", async () => {
    const client = queryClient();
    const bundle = { work: { id: "work-a" }, jobs: [], artifacts: [] };
    let resolveBundle: ((value: typeof bundle) => void) | undefined;
    api.getWorkBundle.mockImplementation(() => new Promise((resolve) => {
      resolveBundle = resolve;
    }));

    const first = fetchWorkBundle(client, "work-a");
    const second = fetchWorkBundle(client, "work-a");

    expect(api.getWorkBundle).toHaveBeenCalledTimes(1);
    resolveBundle?.(bundle);

    await expect(first).resolves.toBe(bundle);
    await expect(second).resolves.toBe(bundle);
    expect(client.getQueryData(serverStateKeys.workBundle("work-a"))).toBe(bundle);
  });

  it("keeps explicit refreshes fresh instead of treating cached bundle data as durable", async () => {
    const client = queryClient();
    api.getWorkBundle
      .mockResolvedValueOnce({ work: { id: "work-a", title: "first" }, jobs: [], artifacts: [] })
      .mockResolvedValueOnce({ work: { id: "work-a", title: "second" }, jobs: [], artifacts: [] });

    const first = await fetchWorkBundle(client, "work-a");
    const second = await fetchWorkBundle(client, "work-a");

    expect(first.work.title).toBe("first");
    expect(second.work.title).toBe("second");
    expect(api.getWorkBundle).toHaveBeenCalledTimes(2);
  });

  it("rejects an empty Work identity before issuing a request", async () => {
    await expect(fetchWorkBundle(queryClient(), "")).rejects.toThrow("workId is required");
    expect(api.getWorkBundle).not.toHaveBeenCalled();
  });
});
