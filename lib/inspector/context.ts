import type { PlaybackSource } from "@/lib/stores/transport";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { InspectorContext } from "./types";

export type { InspectorContext, InspectorMode } from "./types";

export function deriveInspectorContext(
  workId: string | null,
  representationId: string | null,
  currentTime: number,
  activeSource: PlaybackSource | null,
  selection: MusicalSelection | null,
): InspectorContext | null {
  if (!workId) return null;
  return {
    workId,
    representationId: representationId ?? "listen",
    currentTime,
    playbackSourceId: activeSource?.id ?? null,
    selection,
  };
}
