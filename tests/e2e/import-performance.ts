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
  elapsedMs: () => number;
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
  if (
    ["POST", "PUT"].includes(method)
    && pathname.includes("/storage/v1/object/upload/sign/")
  ) {
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

/** Observe the real browser import without changing application behavior. */
export function beginImportPerformanceAttempt(page: Page): ImportPerformanceTracker {
  const startedAtMs = performance.now();
  const networkMilestones: Partial<Record<ImportNetworkMilestone, number>> = {};
  const workBundleResponses: number[] = [];

  const elapsedMs = () => performance.now() - startedAtMs;
  const onResponse = (response: Response) => {
    const request = response.request();
    const method = request.method().toUpperCase();
    let pathname = "";
    try {
      pathname = new URL(response.url()).pathname;
    } catch {
      return;
    }

    const milestone = responseMilestone(response);
    if (milestone && networkMilestones[milestone] === undefined) {
      networkMilestones[milestone] = elapsedMs();
    }
    if (method === "GET" && /\/api\/v1\/works\/[^/]+$/.test(pathname)) {
      workBundleResponses.push(elapsedMs());
    }
  };

  page.on("response", onResponse);
  return {
    startedAtMs,
    networkMilestones,
    workBundleResponses,
    elapsedMs,
    stop: () => page.off("response", onResponse),
  };
}
