import { getJob } from "./api-client";
import type { JobStatus } from "./domain.types";

export class JobTerminalError extends Error {
  constructor(
    message: string,
    readonly stage: "failed" | "cancelled",
  ) {
    super(message);
  }
}

export class JobObservationError extends Error {
  constructor(
    message: string,
    readonly reason: "connection" | "timeout",
  ) {
    super(message);
  }
}

type TrackingOptions = {
  fetchJob?: (jobId: string) => Promise<JobStatus>;
  maxAttempts?: number;
  maxConsecutiveFailures?: number;
  pollIntervalMs?: number;
};

const pause = (milliseconds: number) =>
  new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds));

export async function waitForJob(
  jobId: string,
  onUpdate: (job: JobStatus) => void,
  options: TrackingOptions = {},
): Promise<JobStatus> {
  const fetchJob = options.fetchJob ?? getJob;
  const maxAttempts = options.maxAttempts ?? 300;
  const maxConsecutiveFailures = options.maxConsecutiveFailures ?? 5;
  const pollIntervalMs = options.pollIntervalMs ?? 2000;
  let consecutiveFailures = 0;

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    let job: JobStatus;
    try {
      job = await fetchJob(jobId);
      consecutiveFailures = 0;
    } catch {
      consecutiveFailures += 1;
      if (consecutiveFailures >= maxConsecutiveFailures) {
        throw new JobObservationError(
          "The job is still saved, but this browser lost contact with the processing service.",
          "connection",
        );
      }
      await pause(pollIntervalMs);
      continue;
    }

    onUpdate(job);
    if (job.stage === "succeeded") return job;
    if (job.stage === "failed" || job.stage === "cancelled") {
      throw new JobTerminalError(
        job.error || job.message || `${job.capability} ${job.stage}`,
        job.stage,
      );
    }
    await pause(pollIntervalMs);
  }

  throw new JobObservationError(
    "Processing is taking longer than expected. The server job was not restarted.",
    "timeout",
  );
}
