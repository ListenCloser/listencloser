"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";

import { createProject, deleteWork, listProjects, listWorks } from "@/lib/api-client";
import type { Project, Work } from "@/lib/domain.types";

export const serverStateKeys = {
  libraryProject: (userId: string) => ["library", "project", userId] as const,
  works: (projectId: string) => ["projects", projectId, "works"] as const,
  processingHealth: ["health", "processing"] as const,
};

async function ensureLibraryProject(): Promise<Project> {
  const projects = await listProjects();
  return projects.find((project) => !project.archived_at)
    ?? createProject("Library", "Music workspace");
}

export function useLibraryProject(userId: string) {
  return useQuery({
    queryKey: serverStateKeys.libraryProject(userId),
    queryFn: ensureLibraryProject,
    enabled: Boolean(userId),
    staleTime: Infinity,
  });
}

export function useProjectWorks(projectId: string) {
  return useQuery({
    queryKey: serverStateKeys.works(projectId),
    queryFn: () => listWorks(projectId),
    enabled: Boolean(projectId),
  });
}

export async function refreshProjectWorks(queryClient: QueryClient, projectId: string) {
  if (!projectId) return;
  await queryClient.invalidateQueries({ queryKey: serverStateKeys.works(projectId) });
}

export function useDeleteWorkMutation(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: ["works", "delete"],
    mutationFn: deleteWork,
    onMutate: async (workId: string) => {
      const key = serverStateKeys.works(projectId);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Work[]>(key);
      queryClient.setQueryData<Work[]>(key, (works = []) => works.filter((work) => work.id !== workId));
      return { previous };
    },
    onError: (_error, _workId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(serverStateKeys.works(projectId), context.previous);
      }
    },
    onSettled: async () => {
      await refreshProjectWorks(queryClient, projectId);
    },
  });
}

type ProcessingHealth = {
  status?: string;
};

async function fetchProcessingHealth(): Promise<ProcessingHealth> {
  const response = await fetch("/api/health/queue", { cache: "no-store" });
  if (!response.ok) throw new Error("service unavailable");
  return response.json() as Promise<ProcessingHealth>;
}

export function useProcessingHealth() {
  return useQuery({
    queryKey: serverStateKeys.processingHealth,
    queryFn: fetchProcessingHealth,
    refetchInterval: 30_000,
    retry: false,
    staleTime: 0,
  });
}
