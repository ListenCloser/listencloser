import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { deleteWork } from "@/lib/api-client";
import type { Work } from "@/lib/domain.types";
import { serverStateKeys, useDeleteWorkMutation } from "@/lib/server-state";

vi.mock("@/lib/api-client", () => ({
  createProject: vi.fn(),
  deleteWork: vi.fn(),
  listProjects: vi.fn(),
  listWorks: vi.fn(),
}));

const works: Work[] = [
  { id: "work-a", project_id: "project-1", title: "A", composer: null, created_at: "", updated_at: "" },
  { id: "work-b", project_id: "project-1", title: "B", composer: null, created_at: "", updated_at: "" },
];

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const key = serverStateKeys.works("project-1");
  queryClient.setQueryData(key, works);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, key, wrapper };
}

describe("server state cache", () => {
  beforeEach(() => {
    vi.mocked(deleteWork).mockReset();
  });

  it("scopes the library project cache by authenticated user", () => {
    expect(serverStateKeys.libraryProject("user-a")).not.toEqual(serverStateKeys.libraryProject("user-b"));
  });

  it("removes a work optimistically after a successful delete", async () => {
    vi.mocked(deleteWork).mockResolvedValue({ deleted: "work-a" });
    const { queryClient, key, wrapper } = setup();
    const { result } = renderHook(() => useDeleteWorkMutation("project-1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("work-a");
    });

    expect(queryClient.getQueryData<Work[]>(key)?.map((work) => work.id)).toEqual(["work-b"]);
  });

  it("restores the cached list when deletion fails", async () => {
    vi.mocked(deleteWork).mockRejectedValue(new Error("offline"));
    const { queryClient, key, wrapper } = setup();
    const { result } = renderHook(() => useDeleteWorkMutation("project-1"), { wrapper });

    await expect(act(async () => {
      await result.current.mutateAsync("work-a");
    })).rejects.toThrow("offline");

    expect(queryClient.getQueryData<Work[]>(key)).toEqual(works);
  });
});
