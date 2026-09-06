import type { MusicalSelection } from "@/lib/stores/workspace";

export type InspectorMode = "analysis" | "ask";

export type InspectorContext = {
  workId: string;
  representationId: string;
  currentTime: number;
  playbackSourceId: string | null;
  selection: MusicalSelection | null;
};
