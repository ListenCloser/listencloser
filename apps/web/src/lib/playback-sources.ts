import type { PlaybackSource } from "@/lib/stores/transport";

export type SourceRef = { id: string; url: string };

export function buildPlaybackSources({
  original,
  transcription,
  melody = null,
  extraTakes,
  score,
}: {
  original: SourceRef | null;
  transcription: SourceRef | null;
  melody?: SourceRef | null;
  extraTakes: SourceRef[];
  score: SourceRef | null;
}): { sources: PlaybackSource[]; activeId: string | null } {
  const sources: PlaybackSource[] = [];
  if (original) {
    sources.push({ id: original.id, label: "Original", role: "original", url: original.url, kind: "audio" });
  }
  if (transcription) {
    sources.push({ id: transcription.id, label: "Transcription", role: "transcription", url: transcription.url, kind: "audio" });
  }
  if (melody) {
    sources.push({ id: melody.id, label: "Melody", role: "derived", url: melody.url, kind: "audio" });
  }
  extraTakes.forEach((take, index) => {
    sources.push({ id: take.id, label: `Take ${index + 1}`, role: "derived", url: take.url, kind: "audio" });
  });
  // Score playback is a distinct source: it is only offered when a
  // notation-derived render exists, and it never aliases the transcription.
  if (score) {
    sources.push({ id: score.id, label: "Score", role: "score", url: score.url, kind: "audio" });
  }

  // The uploaded recording is the stable product default. Experimental/derived
  // sources never become the default merely because they were generated. If no
  // Original exists, prefer the canonical transcription/score/take before the
  // optional Melody source so older and partial Works stay predictable.
  const activeId = original?.id
    ?? transcription?.id
    ?? score?.id
    ?? extraTakes[0]?.id
    ?? melody?.id
    ?? null;
  return { sources, activeId };
}
