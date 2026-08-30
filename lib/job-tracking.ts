import { QueryObserver, type QueryClient } from "@tanstack/react-query";

import { getJob } from "./api-client";
import type { JobStatus } from "./domain.types";
import { getQueryClient } from "./query-client";

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

const DEFAULT_SAFE_MESSAGE = "Processing could not be completed. Retry processing.";
const JOB_OBSERVATION_CONNECTION_MESSAGE =
  "The job is still saved, but this browser lost contact with the processing service.";
const JOB_OBSERVATION_TIMEOUT_MESSAGE =
  "Processing is taking longer than expected. The server job was not restarted.";

/**
 * Collapse raw backend/database diagnostics (Postgres constraint errors,
 * Supabase APIError payloads, etc.) into a stable user-facing message.
 * Detailed errors stay available in logs/dev diagnostics.
 */
export function sanitizeJobError(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_SAFE_MESSAGE;
  const suspicious =
    raw.length > 200 ||
    /APIError|Postgres|not-null|constraint|Supabase|relation|column|pgsql|\{|\}|code\s*[=:]/i.test(raw);
  return suspicious ? DEFAULT_SAFE_MESSAGE : raw;
}

type TrackingOptions = {
  fetchJob?: (jobId: string) => Promise<JobStatus>;
  maxAttempts?: number;
  maxConsecutiveFailures?: number;
  pollIntervalMs?: number;
  queryClient?: QueryClient;
  signal?: AbortSignal;
};

const jobQueryKey = (jobId: string) => ["job", jobId] as const;

const isTerminal = (job: JobStatus | undefined) =>
  job?.stage === "succeeded" || job?.stage === "failed" || job?.stage === "cancelled";

const abortError = () => new DOMException("Aborted", "AbortError");

export async function waitForJob(
  jobId: string,
  onUpdate: (job: JobStatus) => void,
  options: TrackingOptions = {},
): Promise<JobStatus> {
  const fetchJob = options.fetchJob ?? getJob;
  const maxAttempts = options.maxAttempts ?? 300;
  const maxConsecutiveFailures = options.maxConsecutiveFailures ?? 5;
  const pollIntervalMs = options.pollIntervalMs ?? 2000;
  const queryClient = options.queryClient ?? getQueryClient();
  const { signal } = options;

  if (signal?.aborted) throw abortError();
  if (maxAttempts <= 0) {
    throw new JobObservationError(JOB_OBSERVATION_TIMEOUT_MESSAGE, "timeout");
  }

  const queryKey = jobQueryKey(jobId);
  const initialState = queryClient.getQueryState<JobStatus>(queryKey);
  let lastDataUpdateCount = initialState?.dataUpdateCount ?? 0;
  let lastErrorUpdateCount = initialState?.errorUpdateCount ?? 0;
  let attempts = 0;

  const observer = new QueryObserver<JobStatus, Error>(queryClient, {
    queryKey,
    queryFn: async () => {
      attempts += 1;
      return fetchJob(jobId);
    },
    networkMode: "always",
    staleTime: 0,
    retry: (failureCount) =>
      attempts < maxAttempts && failureCount < maxConsecutiveFailures - 1,
    retryDelay: Math.max(0, pollIntervalMs),
    refetchInterval: (query) => {
      if (attempts >= maxAttempts || isTerminal(query.state.data)) return false;
      // TanStack treats a zero refetch interval as disabled. Preserve the old
      // "poll immediately" test/override semantics with the smallest interval.
      return Math.max(1, pollIntervalMs);
    },
    refetchIntervalInBackground: true,
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
  });

  return new Promise<JobStatus>((resolve, reject) => {
    let settled = false;
    let unsubscribe: () => void = () => undefined;

    const cleanup = () => {
      signal?.removeEventListener("abort", onAbort);
      unsubscribe();
    };

    const settle = (callback: () => void) => {
      if (settled) return;
      settled = true;
      cleanup();
      callback();
    };

    const onAbort = () => settle(() => reject(abortError()));
    signal?.addEventListener("abort", onAbort, { once: true });

    unsubscribe = observer.subscribe((result) => {
      if (settled) return;

      const state = queryClient.getQueryState<JobStatus>(queryKey);
      if (!state) return;

      if (result.isSuccess && result.data && state.dataUpdateCount > lastDataUpdateCount) {
        lastDataUpdateCount = state.dataUpdateCount;
        const job = result.data;

        try {
          onUpdate(job);
        } catch (error) {
          settle(() => reject(error));
          return;
        }

        if (job.stage === "succeeded") {
          settle(() => resolve(job));
          return;
        }
        const stage = job.stage;
        if (stage === "failed" || stage === "cancelled") {
          settle(() =>
            reject(
              new JobTerminalError(
                sanitizeJobError(job.error || job.message) || `${job.capability} ${stage}`,
                stage,
              ),
            ),
          );
          return;
        }
        if (attempts >= maxAttempts) {
          settle(() =>
            reject(new JobObservationError(JOB_OBSERVATION_TIMEOUT_MESSAGE, "timeout")),
          );
        }
        return;
      }

      if (result.isError && state.errorUpdateCount > lastErrorUpdateCount) {
        lastErrorUpdateCount = state.errorUpdateCount;
        const reason =
          result.failureCount >= maxConsecutiveFailures ? "connection" : "timeout";
        const message =
          reason === "connection"
            ? JOB_OBSERVATION_CONNECTION_MESSAGE
            : JOB_OBSERVATION_TIMEOUT_MESSAGE;
        settle(() => reject(new JobObservationError(message, reason)));
      }
    });
  });
}
