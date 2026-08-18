"use client";

import type { ComponentType } from "react";
import type { RepresentationAvailability } from "@/lib/representation-availability";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";
import {
  composeMeasureSelection,
  composeNoteSelection,
  composeTimeSelection,
  measureRangeFromTime,
  noteIdsInRange,
} from "@/lib/selection";
import Waveform from "@/components/Waveform";
import PianoRoll from "@/components/PianoRoll";
import SheetMusic from "@/components/SheetMusic";


/**
 * The representation registry.
 *
 * The workspace session shows exactly ONE representation at a time, selected
 * by `activeRepresentation` on the workspace store. New views (spectrogram,
 * chromagram, pitch contour, structure, …) are registered here and become
 * reachable through the same navigation without touching RepresentationStack.
 *
 * The id field is a stable key (may differ from the user-facing title).
 * The title is the user-facing label shown in the tab bar.
 */
export type RepresentationId = "listen" | "piano_roll" | "score";

export type RepresentationDefinition = {
  id: RepresentationId;
  title: string;
  description: string;
  /** Whether this view follows the moving playhead. */
  temporal: boolean;
  available: (availability: RepresentationAvailability) => boolean;
  component: ComponentType;
};

function WaveformView() {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek } = useTransport();
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
      <Waveform
        url={waveform.audioUrl}
        position={transport.position}
        selection={workspace.selection}
        onSeek={seek}
        onSelect={(start, end) =>
          setSelection(composeTimeSelection(start, end, [], "waveform"))
        }
      />
    </div>
  );
}

function PianoRollView() {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek } = useTransport();
  const { timeline } = useTimeline();
  const entry = workspace.representations.find((item) => item.kind === "piano_roll");
  const notes = entry?.notes ?? [];
  const selection = workspace.selection;
  const selectedNoteIds =
    selection?.timeRange
      ? noteIdsInRange(notes, selection.timeRange.start, selection.timeRange.end)
      : [];
  return (
    <div className="representation-body">
      <PianoRoll
        notes={notes}
        bpm={timeline.bpm}
        playheadTime={transport.position}
        onSeek={seek}
        selectionTimeRange={selection?.timeRange}
        selectedNoteIds={selection?.noteIds ?? selectedNoteIds}
        onSelectRange={(start, end) =>
          setSelection(composeTimeSelection(start, end, notes, "piano_roll"))
        }
        onSelectNotes={(ids) => {
          const composed = composeNoteSelection(notes, ids);
          if (composed) setSelection(composed);
        }}
      />
    </div>
  );
}

function ScoreView() {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek } = useTransport();
  const entry = workspace.representations.find((item) => item.kind === "score");
  const measureStarts = entry?.measureStarts ?? [];
  const scoreDuration = entry?.audioUrl ? transport.duration : null;
  const selection = workspace.selection;
  const selectedMeasures = selection?.measureRange
    ? selection.measureRange
    : selection?.timeRange
      ? measureRangeFromTime(selection.timeRange.start, selection.timeRange.end, measureStarts)
      : null;
  return (
    <div className="representation-body">
      <SheetMusic
        musicXml={entry?.musicxml ?? ""}
        playheadTime={transport.position}
        isScoreActive={transport.activeSource?.role === "score"}
        hasScorePlayback={transport.sources.some((source) => source.role === "score")}
        measureStarts={measureStarts}
        scoreDuration={scoreDuration}
        selectedMeasures={selectedMeasures}
        measureApproximate={Boolean(
          selection?.timeRange && !selection?.measureRange,
        )}
        onSeek={seek}
        onSelectMeasures={(start, end) =>
          setSelection(
            composeMeasureSelection(start, end, measureStarts, scoreDuration),
          )
        }
      />
    </div>
  );
}

export const REPRESENTATIONS: readonly RepresentationDefinition[] = [
  {
    id: "listen",
    title: "Waveform",
    description: "Audio waveform visualization with time ruler and selection.",
    temporal: true,
    available: (availability) => availability.originalAudio,
    component: WaveformView,
  },
  {
    id: "piano_roll",
    title: "Piano Roll",
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
];

export function availableRepresentations(availability: RepresentationAvailability): RepresentationDefinition[] {
  return REPRESENTATIONS.filter((definition) => definition.available(availability));
}

export function representationById(id: RepresentationId): RepresentationDefinition | undefined {
  return REPRESENTATIONS.find((definition) => definition.id === id);
}
