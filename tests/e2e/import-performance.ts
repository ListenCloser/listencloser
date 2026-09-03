import type { Page, Response } from "@playwright/test";

export type ImportNetworkMilestone =
  | "upload_intent_ready_ms"
  | "storage_upload_complete_ms"
  | "artifact_finalize_complete_ms"
  | "workflow_created_ms";

export type ImportPerformanceTracker = {
  readonly startedAtMs: number;
  readonly networkMilestones: Partial<Record<ImportNetworkMilestone, number>>;
  readonly workBundleResponses: number[];
  readonly firstInsightResponseMs: () => number | null;
  readonly workflowTerminalResponseMs: () => number | null;
  elapsedMs: () => number;
  settle: () => Promise<void>;
  stop: () => void;
};

function responseMilestone(response: Response): ImportNetworkMilestone | null {
  const request = response.request();
  const method = request.method().toUpperCase();
  let pathname: string;
  try {
    pathname = new URL(response.url()).pathname;
  } catch {
    return null;
  }

  if (method === "POST" && /\/api\/v1\/projects\/[^/]+\/artifacts\/upload-intent$/.test(pathname)) {
    return "upload_intent_ready_ms";
  }
  if (["POST", "PUT"].includes(method) && pathname.includes("/storage/v1/object/upload/sign/")) {
    return "storage_upload_complete_ms";
  }
  if (method === "POST" && /\/api\/v1\/projects\/[^/]+\/artifacts\/finalize-upload$/.test(pathname)) {
    return "artifact_finalize_complete_ms";
  }
  if (method === "POST" && pathname === "/api/v1/workflows/understand") {
    return "workflow_created_ms";
  }
  return null;
}

// Keep this vocabulary aligned with the public Job lifecycle, not worker internals.
const TERMINAL_JOB_STAGES = new Set(["succeeded", "failed", "cancelled"]);

/**
 * Observe the real browser import without changing application behavior.
 *
 * The product-level clock starts at file selection. The tracker intentionally
 * records only bounded timing categories: no Work/Version/Job IDs, filenames,
 * titles, or musical content are persisted in the report.
 */
export function beginImportPerformanceAttempt(page: Page): ImportPerformanceTracker {
  const startedAtMs = performance.now();
  const networkMilestones: Partial<Record<ImportNetworkMilestone, number>> = {};
  const workBundleResponses: number[] = [];
  const pending = new Set<Promise<void>>();
  let firstInsightMs: number | null = null;
  let workflowTerminalMs: number | null = null;

  const elapsedMs = () => performance.now() - startedAtMs;
  const observeJson = (response: Response, observedAtMs: number, pathname: string) => {
    const promise = response
      .json()
      .then((body: unknown) => {
        if (/\/api\/v1\/versions\/[^/]+\/insights$/.test(pathname)) {
          if (firstInsightMs === null && Array.isArray(body) && body.length > 0) {
            firstInsightMs = observedAtMs;
          }
          return;
        }

        if (/\/api\/v1\/works\/[^/]+$/.test(pathname)) {
          const jobs =
            typeof body === "object" && body !== null && Array.isArray((body as { jobs?: unknown }).jobs)
              ? (body as { jobs: Array<{ lifecycle?: { current?: string } }> }).jobs
              : [];
          if (
            workflowTerminalMs === null &&
            jobs.length > 0 &&
            jobs.every((job) => TERMINAL_JOB_STAGES.has(job.lifecycle?.current ?? ""))
          ) {
            workflowTerminalMs = observedAtMs;
          }
        }
      })
      .catch(() => undefined)
      .then(() => undefined);
    pending.add(promise);
    void promise.finally(() => pending.delete(promise));
  };

  const onResponse = (response: Response) => {
    const request = response.request();
    const method = request.method().toUpperCase();
    let pathname = "";
    try {
      pathname = new URL(response.url()).pathname;
    } catch {
      return;
    }

    const observedAtMs = elapsedMs();
    const milestone = responseMilestone(response);
    if (milestone && networkMilestones[milestone] === undefined) {
      networkMilestones[milestone] = observedAtMs;
    }

    if (method === "GET" && /\/api\/v1\/works\/[^/]+$/.test(pathname)) {
      workBundleResponses.push(observedAtMs);
      observeJson(response, observedAtMs, pathname);
    } else if (method === "GET" && /\/api\/v1\/versions\/[^/]+\/insights$/.test(pathname)) {
      observeJson(response, observedAtMs, pathname);
    }
  };

  page.on("response", onResponse);
  return {
    startedAtMs,
    networkMilestones,
    workBundleResponses,
    firstInsightResponseMs: () => firstInsightMs,
    workflowTerminalResponseMs: () => workflowTerminalMs,
    elapsedMs,
    settle: async () => {
      await Promise.allSettled([...pending]);
    },
    stop: () => page.off("response", onResponse),
  };
}
