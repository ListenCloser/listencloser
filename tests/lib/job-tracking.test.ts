import { describe, expect, it, vi } from "vitest";
import { JobObservationError, JobTerminalError, sanitizeJobError, waitForJob } from "@/lib/job-tracking";
import type { JobStatus } from "@/lib/domain.types";

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

describe("waitForJob", () => {
  it("recovers from a transient polling error without creating a new job", async () => {
    const fetchJob = vi.fn()
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(status("running"))
      .mockResolvedValueOnce(status("succeeded"));
    const updates: string[] = [];

    const result = await waitForJob("job-1", (job) => updates.push(job.stage), {
      fetchJob,
      pollIntervalMs: 0,
    });

    expect(result.stage).toBe("succeeded");
    expect(fetchJob).toHaveBeenCalledTimes(3);
    expect(updates).toEqual(["running", "succeeded"]);
  });

  it("reports observation loss separately from a terminal failure", async () => {
    const fetchJob = vi.fn().mockRejectedValue(new Error("offline"));
    await expect(waitForJob("job-1", () => undefined, {
      fetchJob,
      maxConsecutiveFailures: 2,
      pollIntervalMs: 0,
    })).rejects.toMatchObject({ reason: "connection" } satisfies Partial<JobObservationError>);
  });

  it("only exposes retry semantics for a confirmed terminal job", async () => {
    await expect(waitForJob("job-1", () => undefined, {
      fetchJob: async () => status("failed", "decoder failed"),
      pollIntervalMs: 0,
    })).rejects.toMatchObject({ stage: "failed", message: "decoder failed" } satisfies Partial<JobTerminalError>);
  });

  it("aborts polling when the signal is cancelled", async () => {
    const controller = new AbortController();
    const fetchJob = vi.fn().mockResolvedValue(status("running"));
    const promise = waitForJob("job-1", () => undefined, {
      fetchJob,
      pollIntervalMs: 0,
      signal: controller.signal,
    });
    controller.abort();
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
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
