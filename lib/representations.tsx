"use client";

import type { ComponentType } from "react";
import type { RepresentationAvailability } from "@/lib/representation-availability";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";
import Visualizer from "@/components/Visualizer";
import PianoRoll from "@/components/PianoRoll";
import SheetMusic from "@/components/SheetMusic";
import { AnalysisSummary } from "@/components/workspace/AnalysisSummary";

/**
 * The representation registry (Psr: "Representation").
 *
 * The workspace session shows exactly ONE representation at a time, selected
 * by `activeRepresentation` on the workspace store. New views (structure,
 * harmony, rhythm, …) are registered here and become reachable through the
 * same navigation without touching RepresentationStack.
 */
export type RepresentationId = "listen" | "piano_roll" | "score" | "analysis";

export type RepresentationDefinition = {
  id: RepresentationId;
  title: string;
  description: string;
  /** Whether this view follows the moving playhead. */
  temporal: boolean;
  available: (availability: RepresentationAvailability) => boolean;
  component: ComponentType;
};

function ListenView() {
  const { workspace } = useWorkspace();
  const { audioRef } = useTransport();
  const waveform = workspace.representations.find((item) => item.kind === "waveform");
  if (!waveform?.audioUrl) {
    return (
      <div className="representation-body">
        <p className="muted">No audio URL provided for waveform.</p>
      </div>
    );
  }
  return (
    <div className="representation-body">
      <Visualizer audioRef={audioRef} />
    </div>
  );
}

function PianoRollView() {
  const { workspace } = useWorkspace();
  const { transport, seek } = useTransport();
  const { timeline } = useTimeline();
  const entry = workspace.representations.find((item) => item.kind === "piano_roll");
  return (
    <div className="representation-body">
      <PianoRoll
        notes={entry?.notes ?? []}
        bpm={timeline.bpm}
        playheadTime={transport.position}
        onSeek={seek}
      />
    </div>
  );
}

function ScoreView() {
  const { workspace } = useWorkspace();
  const { transport, seek } = useTransport();
  const entry = workspace.representations.find((item) => item.kind === "score");
  return (
    <div className="representation-body">
      <SheetMusic
        musicXml={entry?.musicxml ?? ""}
        playheadTime={transport.position}
        isScoreActive={transport.activeSource?.role === "score"}
        hasScorePlayback={transport.sources.some((source) => source.role === "score")}
        measureStarts={entry?.measureStarts}
        onSeek={seek}
      />
    </div>
  );
}

function AnalysisView() {
  const { seek } = useTransport();
  const { timeline } = useTimeline();
  return (
    <div className="piece-analysis">
      <AnalysisSummary onSeek={seek} bpm={timeline.bpm} />
    </div>
  );
}

export const REPRESENTATIONS: readonly RepresentationDefinition[] = [
  {
    id: "listen",
    title: "Listen",
    description: "Hear your recording and its transcription — choose what you're hearing in the transport.",
    temporal: true,
    available: (availability) => availability.originalAudio,
    component: ListenView,
  },
  {
    id: "piano_roll",
    title: "Piano roll",
    description: "Every detected note with its timing and pitch.",
    temporal: true,
    available: (availability) => availability.performanceMidi,
    component: PianoRollView,
  },
  {
    id: "score",
    title: "Score",
    description: "Score playback follows the written timing.",
    temporal: true,
    available: (availability) => availability.score,
    component: ScoreView,
  },
  {
    id: "analysis",
    title: "Analysis",
    description: "A musical summary of the transcription. Select an item to hear that moment.",
    temporal: false,
    available: (availability) => availability.analysis,
    component: AnalysisView,
  },
];

export function availableRepresentations(availability: RepresentationAvailability): RepresentationDefinition[] {
  return REPRESENTATIONS.filter((definition) => definition.available(availability));
}

export function representationById(id: RepresentationId): RepresentationDefinition | undefined {
  return REPRESENTATIONS.find((definition) => definition.id === id);
}