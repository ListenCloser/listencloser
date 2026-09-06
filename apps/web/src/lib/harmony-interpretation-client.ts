import { withCurrentSupabaseAuth } from "./openapi-client";

export type HarmonyInterpretationEngine = "lv-chordia" | "chordmini";

type HarmonyInterpretationResponse = {
  job: { id: string };
};

export async function startChordMiniInterpretation(
  workId: string,
  performanceMidiVersionId: string,
  sourceAudioVersionId: string,
): Promise<HarmonyInterpretationResponse> {
  const path = `/api/v1/works/${encodeURIComponent(workId)}/workflows/harmony-interpretation`;
  const request = await withCurrentSupabaseAuth(new Request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      performance_midi_version_id: performanceMidiVersionId,
      source_audio_version_id: sourceAudioVersionId,
      harmony_engine: "chordmini",
    }),
  }));
  const response = await fetch(request);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload
      ? (payload as { detail?: unknown }).detail
      : undefined;
    throw new Error(typeof detail === "string" ? detail : "Could not generate ChordMini interpretation");
  }
  const jobId = (payload as { job?: { id?: unknown } }).job?.id;
  if (typeof jobId !== "string" || !jobId) {
    throw new Error("ChordMini workflow returned no job id");
  }
  return payload as HarmonyInterpretationResponse;
}
