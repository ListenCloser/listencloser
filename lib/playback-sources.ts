import type { PlaybackSource } from "@/lib/stores/transport";

export type SourceRef = { id: string; url: string };

export function buildPlaybackSources({
  original,
  transcription,
  extraTakes,
  score,
}: {
  original: SourceRef | null;
  transcription: SourceRef | null;
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
  extraTakes.forEach((take, index) => {
    sources.push({ id: take.id, label: `Take ${index + 1}`, role: "derived", url: take.url, kind: "audio" });
  });
  // Score playback is a distinct source: it is only offered when a
  // notation-derived render exists, and it never aliases the transcription.
  if (score) {
    sources.push({ id: score.id, label: "Score", role: "score", url: score.url, kind: "audio" });
  }

  // The uploaded recording is the stable product default. Derived sources are
  // opt-in listening choices and representation tabs never choose them
  // implicitly. If no Original exists, fall back to the first useful derived
  // source so older/partial Works remain playable.
  const activeId = original?.id ?? transcription?.id ?? score?.id ?? extraTakes[0]?.id ?? null;
  return { sources, activeId };
}
