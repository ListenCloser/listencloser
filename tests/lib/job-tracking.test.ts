import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import type { JobStatus } from "@/lib/domain.types";
import {
  JobObservationError,
  JobTerminalError,
  sanitizeJobError,
  waitForJob,
} from "@/lib/job-tracking";

const status = (stage: JobStatus["stage"], message: string = stage): JobStatus => ({
  id: "job-1",
  workflow_id: "workflow-1",
  capability: "understand",
  stage,
  progress: stage === "succeeded" ? 1 : 0.5,
  message,
  error: stage === "failed" ? message : null,
  input_version_ids: ["input-1"],
  output_version_ids: [],
});

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        gcTime: 0,
        retry: false,
      },
    },
  });

describe("waitForJob", () => {
  it("recovers from a transient polling error without creating a new job", async () => {
    const fetchJob = vi
      .fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(status("running"))
      .mockResolvedValueOnce(status("succeeded"));
    const updates: string[] = [];

    const result = await waitForJob("job-1", (job) => updates.push(job.stage), {
      fetchJob,
      pollIntervalMs: 0,
      queryClient: createTestQueryClient(),
    });

    expect(result.stage).toBe("succeeded");
    expect(fetchJob).toHaveBeenCalledTimes(3);
    expect(updates).toEqual(["running", "succeeded"]);
  });

  it("reports observation loss separately from a terminal failure", async () => {
    const fetchJob = vi.fn().mockRejectedValue(new Error("offline"));
    await expect(
      waitForJob("job-1", () => undefined, {
        fetchJob,
        maxConsecutiveFailures: 2,
        pollIntervalMs: 0,
        queryClient: createTestQueryClient(),
      }),
    ).rejects.toMatchObject({ reason: "connection" } satisfies Partial<JobObservationError>);
  });

  it("only exposes retry semantics for a confirmed terminal job", async () => {
    await expect(
      waitForJob("job-1", () => undefined, {
        fetchJob: async () => status("failed", "decoder failed"),
        pollIntervalMs: 0,
        queryClient: createTestQueryClient(),
      }),
    ).rejects.toMatchObject({
      stage: "failed",
      message: "decoder failed",
    } satisfies Partial<JobTerminalError>);
  });

  it("times out after the configured observation budget without restarting the job", async () => {
    const fetchJob = vi.fn().mockResolvedValue(status("running"));

    await expect(
      waitForJob("job-1", () => undefined, {
        fetchJob,
        maxAttempts: 2,
        pollIntervalMs: 0,
        queryClient: createTestQueryClient(),
      }),
    ).rejects.toMatchObject({ reason: "timeout" } satisfies Partial<JobObservationError>);

    expect(fetchJob).toHaveBeenCalledTimes(2);
  });

  it("aborts polling when the signal is cancelled and does not schedule another fetch", async () => {
    const controller = new AbortController();
    let markFetchStarted!: () => void;
    const fetchStarted = new Promise<void>((resolve) => {
      markFetchStarted = resolve;
    });
    const fetchJob = vi.fn().mockImplementation(async () => {
      markFetchStarted();
      return status("running");
    });
    const promise = waitForJob("job-1", () => undefined, {
      fetchJob,
      pollIntervalMs: 25,
      queryClient: createTestQueryClient(),
      signal: controller.signal,
    });

    await fetchStarted;
    controller.abort();
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    await new Promise((resolve) => globalThis.setTimeout(resolve, 40));
    expect(fetchJob).toHaveBeenCalledTimes(1);
  });
});

describe("sanitizeJobError", () => {
  it("collapses raw database diagnostics into a stable user message", () => {
    const raw =
      'APIError: null value in column "confidence" of relation "insights" violates not-null constraint';
    expect(sanitizeJobError(raw)).toBe("Processing could not be completed. Retry processing.");
  });

  it("keeps already-safe, concise messages", () => {
    expect(sanitizeJobError("Processing could not be completed. Retry processing.")).toBe(
      "Processing could not be completed. Retry processing.",
    );
  });

  it("falls back for empty input", () => {
    expect(sanitizeJobError(null)).toBe("Processing could not be completed. Retry processing.");
    expect(sanitizeJobError("")).toBe("Processing could not be completed. Retry processing.");
  });
});
