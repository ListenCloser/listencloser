import { withCurrentSupabaseAuth } from "@/lib/openapi-client";

export type PitchContourWorkflowResponse = {
  workflow: { id: string };
  job: { id: string };
};

function errorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return `Pitch contour request failed (${status})`;
}

export async function startPitchContourWorkflow(
  versionId: string,
): Promise<PitchContourWorkflowResponse> {
  const url = new URL("/api/v1/workflows/pitch-contour", window.location.origin);
  const request = await withCurrentSupabaseAuth(
    new Request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version_id: versionId }),
    }),
  );
  const response = await fetch(request);
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessage(payload, response.status));
  return payload as PitchContourWorkflowResponse;
}
