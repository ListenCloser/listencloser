"use client";

import { useMemo, type ComponentType } from "react";
import PianoRoll from "./PianoRoll";
import Spectrogram from "./Spectrogram";
import Waveform from "./Waveform";
import SheetMusic from "@/components/SheetMusic";
import { extractAnnotations } from "@/lib/analysis-annotations";
import {
  resolveEvidenceProjection,
  type EvidenceProjectionTarget,
} from "@/lib/evidence-projections";
import {
  REPRESENTATION_CATALOG,
  type RepresentationId,
  type RepresentationMetadata,
} from "@/lib/representations";
import type { RepresentationAvailability } from "@/lib/representation-availability";
import { extractObservedPulseGrid } from "@/lib/pulse-grid";
import {
  composeMeasureSelection,
  composeNoteSelection,
  composeTimeSelection,
  measureRangeFromTime,
  noteIdsInRange,
} from "@/lib/selection";
import { useTimeline } from "@/lib/stores/timeline";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

export type { RepresentationId } from "@/lib/representations";

export type RepresentationViewProps = {
  /** Whether this representation is the currently visible workspace tab. */
  active: boolean;
  /** Briefly strengthen the real shared selection after an evidence jump. */
  orientationCue?: boolean;
};

export type RepresentationDefinition = RepresentationMetadata & {
  component: ComponentType<RepresentationViewProps>;
};

function visibleAnnotations(
  insights: Parameters<typeof extractAnnotations>[0],
  target: EvidenceProjectionTarget,
  inspectorCollapsed: boolean,
) {
  const annotations = extractAnnotations(insights);
  if (!inspectorCollapsed) return annotations;

  // Legacy annotations are temporal locator projections. With the Inspector
  // closed, keep only evidence whose approximate locator policy is passive by
  // default; focused/secondary evidence remains available when inspecting.
  return annotations.filter((annotation) => (
    resolveEvidenceProjection(annotation.kind, target, "approximate").passiveByDefault
  ));
}

function WaveformView({ active, orientationCue = false }: RepresentationViewProps) {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek } = useTransport();
  const waveform = workspace.representations.find((item) => item.kind === "waveform");
  const annotations = useMemo(
    () => visibleAnnotations(workspace.insights, "listen", workspace.inspectorCollapsed),
    [workspace.insights, workspace.inspectorCollapsed],
  );
  const selection = workspace.selection;
  const focusedAnnotationId = useMemo(() => {
    if (!selection?.timeRange || !annotations.length) return null;
    const { start, end } = selection.timeRange;
    const match = annotations.find(
      (annotation) => annotation.startSeconds < end && annotation.endSeconds > start,
    );
    return match?.id ?? null;
  }, [selection, annotations]);
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
        position={active ? transport.position : 0}
        selection={workspace.selection}
        emphasizeSelection={active && orientationCue}
        annotations={annotations}
        focusedAnnotationId={focusedAnnotationId}
        onSeek={seek}
        onSelect={(start, end) =>
          setSelection(composeTimeSelection(start, end, [], "waveform"))
        }
        onAnnotationClick={(annotation) => {
          setSelection({
            timeRange: {
              start: annotation.startSeconds,
              end: annotation.endSeconds,
              domain: "performance",
            },
            provenance: { origin: "waveform", timeExact: true, measureApproximate: false },
          });
        }}
      />
    </div>
  );
}

function PianoRollView({ active, orientationCue = false }: RepresentationViewProps) {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek } = useTransport();
  const { timeline } = useTimeline();
  const entry = workspace.representations.find((item) => item.kind === "piano_roll");
  const notes = entry?.notes ?? [];
  const pulseGrid = useMemo(
    () => extractObservedPulseGrid(workspace.insights, entry?.versionId),
    [workspace.insights, entry?.versionId],
  );
  const selection = workspace.selection;
  const annotations = useMemo(
    () => visibleAnnotations(workspace.insights, "piano_roll", workspace.inspectorCollapsed),
    [workspace.insights, workspace.inspectorCollapsed],
  );
  const focusedAnnotationId = useMemo(() => {
    if (!selection?.timeRange || !annotations.length) return null;
    const { start, end } = selection.timeRange;
    const match = annotations.find(
      (annotation) => annotation.startSeconds < end && annotation.endSeconds > start,
    );
    return match?.id ?? null;
  }, [selection, annotations]);
  const selectedNoteIds = selection?.timeRange
    ? noteIdsInRange(notes, selection.timeRange.start, selection.timeRange.end)
    : [];
  return (
    <div className="representation-body">
      <PianoRoll
        notes={notes}
        bpm={timeline.bpm}
        beatTimes={pulseGrid?.beatsSeconds}
        downbeatTimes={pulseGrid?.downbeatsSeconds}
        playheadTime={active ? transport.position : 0}
        annotations={annotations}
        focusedAnnotationId={focusedAnnotationId}
        onSeek={seek}
        selectionTimeRange={selection?.timeRange}
        selectedNoteIds={selection?.noteIds ?? selectedNoteIds}
        emphasizeSelection={active && orientationCue}
        onSelectRange={(start, end) =>
          setSelection(composeTimeSelection(start, end, notes, "piano_roll"))
        }
        onSelectNotes={(ids) => {
          const composed = composeNoteSelection(notes, ids);
          if (composed) setSelection(composed);
        }}
        onAnnotationClick={(annotation) => {
          setSelection({
            timeRange: {
              start: annotation.startSeconds,
              end: annotation.endSeconds,
              domain: "performance",
            },
            provenance: { origin: "piano_roll", timeExact: true, measureApproximate: false },
          });
        }}
      />
    </div>
  );
}

function SpectrogramView({ active }: RepresentationViewProps) {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek } = useTransport();
  const waveform = workspace.representations.find((item) => item.kind === "waveform");
  const annotations = useMemo(
    () => visibleAnnotations(workspace.insights, "spectrogram", workspace.inspectorCollapsed),
    [workspace.insights, workspace.inspectorCollapsed],
  );
  const selection = workspace.selection;
  const focusedAnnotationId = useMemo(() => {
    if (!selection?.timeRange || !annotations.length) return null;
    return annotations.find(
      (annotation) =>
        annotation.startSeconds < selection.timeRange!.end
        && annotation.endSeconds > selection.timeRange!.start,
    )?.id ?? null;
  }, [annotations, selection]);
  if (!waveform?.audioUrl) {
    return (
      <div className="representation-body">
        <p className="muted">No audio URL provided for spectrogram.</p>
      </div>
    );
  }
  return (
    <div className="representation-body">
      <Spectrogram
        url={waveform.audioUrl}
        cacheIdentity={waveform.versionId}
        position={active ? transport.position : 0}
        selection={selection}
        annotations={annotations}
        focusedAnnotationId={focusedAnnotationId}
        onSeek={seek}
        onSelect={(start, end) =>
          setSelection(composeTimeSelection(start, end, [], "spectrogram"))
        }
      />
    </div>
  );
}

function ScoreView({ active, orientationCue = false }: RepresentationViewProps) {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek } = useTransport();
  const entry = workspace.representations.find((item) => item.kind === "score");
  const measureStarts = entry?.measureStarts ?? [];
  const finalMeasureSpan = measureStarts.length > 1
    ? measureStarts[measureStarts.length - 1] - measureStarts[measureStarts.length - 2]
    : 2;
  const scoreDuration = measureStarts.length > 0
    ? Math.max(
        transport.duration || 0,
        measureStarts[measureStarts.length - 1] + Math.max(finalMeasureSpan, 0.25),
      )
    : (transport.duration || null);
  const selection = workspace.selection;
  const annotations = useMemo(
    () => visibleAnnotations(workspace.insights, "score", workspace.inspectorCollapsed),
    [workspace.insights, workspace.inspectorCollapsed],
  );
  const focusedAnnotationId = useMemo(() => {
    if (!selection?.timeRange || !annotations.length) return null;
    const { start, end } = selection.timeRange;
    const match = annotations.find(
      (annotation) => annotation.startSeconds < end && annotation.endSeconds > start,
    );
    return match?.id ?? null;
  }, [selection, annotations]);
  const selectedMeasures = selection?.measureRange
    ? selection.measureRange
    : selection?.timeRange
      ? measureRangeFromTime(
          selection.timeRange.start,
          selection.timeRange.end,
          measureStarts,
        )
      : null;
  return (
    <div className="representation-body">
      <SheetMusic
        musicXml={entry?.musicxml ?? ""}
        playheadTime={active ? transport.position : 0}
        isPlaying={active && transport.isPlaying}
        isScoreActive={active}
        measureStarts={measureStarts}
        scoreDuration={scoreDuration}
        selectedMeasures={selectedMeasures}
        measureApproximate={Boolean(selection?.timeRange && !selection?.measureRange)}
        emphasizeSelection={active && orientationCue}
        annotations={annotations}
        focusedAnnotationId={focusedAnnotationId}
        onSeek={seek}
        onSelectMeasures={(start, end) =>
          setSelection(composeMeasureSelection(start, end, measureStarts, scoreDuration))
        }
        onAnnotationClick={(annotation) => {
          setSelection({
            timeRange: {
              start: annotation.startSeconds,
              end: annotation.endSeconds,
              domain: "notation",
            },
            provenance: { origin: "score", timeExact: false, measureApproximate: true },
          });
        }}
      />
    </div>
  );
}

const VIEW_COMPONENTS: Record<RepresentationId, ComponentType<RepresentationViewProps>> = {
  listen: WaveformView,
  piano_roll: PianoRollView,
  score: ScoreView,
  spectrogram: SpectrogramView,
};

/** Workspace-owned renderer registry built from the shared pure catalog. */
export const REPRESENTATIONS: readonly RepresentationDefinition[] = REPRESENTATION_CATALOG.map(
  (metadata) => ({ ...metadata, component: VIEW_COMPONENTS[metadata.id] }),
);

export function availableRepresentations(
  availability: RepresentationAvailability,
): RepresentationDefinition[] {
  return REPRESENTATIONS.filter((definition) => definition.available(availability));
}
