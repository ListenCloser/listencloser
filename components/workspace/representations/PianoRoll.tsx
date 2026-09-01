/**
 * Piano roll visualization — SVG-based note display with playhead.
 *
 * Visual language:
 * - Quiet chromatic lanes with stronger octave/C anchors for pitch orientation
 * - Observed beat/downbeat coordinates when available; conservative tempo scaffold otherwise
 * - Real note events dominate the grid, with velocity preserved through opacity
 * - Shared playback/selection tokens for active time and user-selected evidence
 * - Sparse wall-clock labels for orientation without implying musical structure
 */

"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { pitchToName } from "@/lib/notes";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";

type Note = { id?: string; pitch: number; start: number; end: number; velocity: number };
type TimeRange = { start: number; end: number };
type LayoutNote = Note & {
  key: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  velocityOpacity: number;
};
type LayoutRow = {
  pitch: number;
  label: string;
  y: number;
  isBlack: boolean;
  isOctaveAnchor: boolean;
  notes: LayoutNote[];
};
type PianoRollLayout = {
  rows: LayoutRow[];
  notes: LayoutNote[];
  observedBeats: number[];
  observedDownbeats: number[];
  endTime: number;
  displayEndTime: number;
  totalBeats: number;
  totalPx: number;
  rowH: number;
  height: number;
  width: number;
  timeLabels: number[];
};

const PPQ = 16;
const LABEL_W = 36;
const TOP_PAD = 18;

function validSecondsGrid(values: number[] | undefined, minimumPoints = 1): number[] {
  if (!values || values.length < minimumPoints) return [];
  const result: number[] = [];
  for (const value of values) {
    if (!Number.isFinite(value) || value < 0) return [];
    if (result.length > 0 && value <= result[result.length - 1]) return [];
    result.push(value);
  }
  return result;
}

function timeToX(time: number, bpm: number): number {
  return LABEL_W + (time / 60) * bpm * PPQ;
}

function buildLayout(
  notes: Note[],
  bpm: number,
  beatTimes: number[] | undefined,
  downbeatTimes: number[] | undefined,
): PianoRollLayout {
  const observedBeats = validSecondsGrid(beatTimes, 2);
  const observedDownbeats = observedBeats.length > 0
    ? validSecondsGrid(downbeatTimes)
    : [];
  const endTime = notes.reduce((time, note) => Math.max(time, note.end), 0);
  const displayEndTime = Math.max(
    endTime,
    observedBeats.length > 0 ? observedBeats[observedBeats.length - 1] : 0,
  );
  const totalBeats = (displayEndTime / 60) * bpm;
  const totalPx = Math.max(totalBeats * PPQ, 300);
  const minPitch = Math.min(...notes.map((note) => note.pitch));
  const maxPitch = Math.max(...notes.map((note) => note.pitch));
  const pitchLow = Math.max(0, minPitch - 4);
  const pitchHigh = Math.min(127, maxPitch + 4);
  const rowCount = Math.max(pitchHigh - pitchLow + 1, 1);
  const rowH = Math.max(12, Math.min(22, 520 / rowCount));
  const height = rowCount * rowH + TOP_PAD;
  const width = LABEL_W + totalPx;
  const notesByPitch = new Map<number, Array<{ note: Note; index: number }>>();

  notes.forEach((note, index) => {
    const bucket = notesByPitch.get(note.pitch) ?? [];
    bucket.push({ note, index });
    notesByPitch.set(note.pitch, bucket);
  });

  const rows: LayoutRow[] = [];
  const laidOutNotes: LayoutNote[] = [];
  for (let pitch = pitchHigh, rowIndex = 0; pitch >= pitchLow; pitch--, rowIndex++) {
    const label = pitchToName(pitch);
    const y = rowIndex * rowH + TOP_PAD;
    const rowNotes = (notesByPitch.get(pitch) ?? []).map(({ note, index }) => {
      const duration = note.end - note.start;
      const layoutNote: LayoutNote = {
        ...note,
        key: note.id ?? `${note.pitch}:${note.start}:${note.end}:${index}`,
        label,
        x: timeToX(note.start, bpm),
        y: y + 2,
        width: Math.max((duration / 60) * bpm * PPQ, 3),
        height: Math.max(rowH - 4, 5),
        velocityOpacity: 0.28 + (note.velocity / 127) * 0.5,
      };
      laidOutNotes.push(layoutNote);
      return layoutNote;
    });
    rows.push({
      pitch,
      label,
      y,
      isBlack: [1, 3, 6, 8, 10].includes(pitch % 12),
      isOctaveAnchor: pitch % 12 === 0,
      notes: rowNotes,
    });
  }

  const timeLabelStep = displayEndTime <= 40 ? 5 : displayEndTime <= 120 ? 10 : 30;
  const timeLabels = Array.from(
    { length: Math.floor(displayEndTime / timeLabelStep) + 1 },
    (_, index) => index * timeLabelStep,
  );

  return {
    rows,
    notes: laidOutNotes,
    observedBeats,
    observedDownbeats,
    endTime,
    displayEndTime,
    totalBeats,
    totalPx,
    rowH,
    height,
    width,
    timeLabels,
  };
}

const PianoRollBaseLayer = memo(function PianoRollBaseLayer({
  layout,
  bpm,
}: {
  layout: PianoRollLayout;
  bpm: number;
}) {
  return (
    <g data-piano-roll-static-layer="true">
      <rect x={0} y={0} width={LABEL_W} height={layout.height} fill="var(--panel)" />

      {layout.rows.map((row) => (
        <rect
          key={`stripe-${row.pitch}`}
          data-pitch-lane={row.isOctaveAnchor ? "octave-anchor" : row.isBlack ? "black-key" : "natural"}
          x={LABEL_W}
          y={row.y}
          width={layout.totalPx}
          height={layout.rowH}
          fill={row.isOctaveAnchor ? "var(--text)" : row.isBlack ? "var(--panel-2)" : "transparent"}
          fillOpacity={row.isOctaveAnchor ? 0.035 : row.isBlack ? 0.72 : 1}
        />
      ))}

      {layout.rows.map((row) => (
        <line
          key={`guide-${row.pitch}`}
          x1={LABEL_W}
          y1={row.y + layout.rowH}
          x2={layout.width}
          y2={row.y + layout.rowH}
          stroke="var(--border)"
          strokeWidth={row.isOctaveAnchor ? 0.65 : 0.3}
          strokeOpacity={row.isOctaveAnchor ? 0.36 : 0.17}
        />
      ))}

      {layout.observedBeats.length > 0 ? (
        <>
          {layout.observedBeats.map((seconds, index) => {
            const x = timeToX(seconds, bpm);
            return (
              <line
                key={`observed-beat-${index}`}
                data-grid-kind="observed-beat"
                data-beat-seconds={seconds}
                x1={x}
                y1={TOP_PAD}
                x2={x}
                y2={layout.height}
                stroke="var(--border)"
                strokeWidth={0.5}
                strokeOpacity={0.38}
              />
            );
          })}
          {layout.observedDownbeats.map((seconds, index) => {
            const x = timeToX(seconds, bpm);
            return (
              <line
                key={`observed-downbeat-${index}`}
                data-grid-kind="observed-downbeat"
                data-downbeat-seconds={seconds}
                x1={x}
                y1={TOP_PAD}
                x2={x}
                y2={layout.height}
                stroke="var(--text)"
                strokeWidth={0.75}
                strokeOpacity={0.34}
              />
            );
          })}
        </>
      ) : (
        Array.from({ length: Math.floor(layout.totalBeats) + 1 }, (_, index) => {
          const x = LABEL_W + index * PPQ;
          return (
            <line
              key={`beat-${index}`}
              data-grid-kind="tempo-beat"
              x1={x}
              y1={TOP_PAD}
              x2={x}
              y2={layout.height}
              stroke="var(--border)"
              strokeWidth={0.5}
              strokeOpacity={0.38}
            />
          );
        })
      )}

      {layout.timeLabels.map((seconds) => {
        const x = timeToX(seconds, bpm);
        return (
          <g key={`time-${seconds}`} data-ruler-kind="elapsed-time">
            <line
              x1={x}
              y1={TOP_PAD - 5}
              x2={x}
              y2={TOP_PAD}
              stroke="var(--muted)"
              strokeWidth={0.6}
              strokeOpacity={0.45}
            />
            <text
              x={x + 3}
              y={9}
              fill="var(--muted)"
              fontSize={8.5}
              fontFamily="var(--font-mono)"
              opacity={0.55}
            >
              {seconds}s
            </text>
          </g>
        );
      })}

      {layout.rows.map((row) => (
        <g key={row.pitch}>
          <text
            x={4}
            y={row.y + Math.min(layout.rowH - 3, 12)}
            fill="var(--muted)"
            fontSize={Math.min(10, Math.max(8, layout.rowH - 4))}
            fontFamily="var(--font-mono)"
            fontWeight={row.isOctaveAnchor ? 650 : 400}
            opacity={row.isOctaveAnchor ? 0.82 : row.notes.length ? 0.58 : 0.34}
          >
            {row.label}
          </text>
          {row.notes.map((note) => (
            <rect
              key={note.key}
              data-note-base="true"
              data-note-key={note.key}
              data-note-state="default"
              x={note.x}
              y={note.y}
              width={note.width}
              height={note.height}
              rx={Math.min(2, layout.rowH / 4)}
              fill="var(--text)"
              fillOpacity={note.velocityOpacity}
              stroke="var(--border)"
              strokeWidth={0.45}
              strokeOpacity={0.42}
            >
              <title>{row.label} @ {note.start.toFixed(2)}s · velocity {note.velocity}</title>
            </rect>
          ))}
        </g>
      ))}
    </g>
  );
});

function NoteOverlay({
  notes,
  state,
  rowH,
}: {
  notes: LayoutNote[];
  state: "active" | "selected";
  rowH: number;
}) {
  const active = state === "active";
  return (
    <g data-piano-roll-note-overlay={state} pointerEvents="none">
      {notes.map((note) => (
        <rect
          key={`${state}:${note.key}`}
          data-note-state={state}
          data-note-key={note.key}
          x={note.x}
          y={note.y}
          width={note.width}
          height={note.height}
          rx={Math.min(2, rowH / 4)}
          fill={active ? "var(--score-playback)" : "var(--accent)"}
          fillOpacity={active ? 0.94 : 0.82}
          stroke={active ? "var(--score-playback)" : "var(--accent)"}
          strokeWidth={active ? 1.3 : 1.05}
          strokeOpacity={active ? 0.96 : 0.78}
        />
      ))}
    </g>
  );
}

export default function PianoRoll({
  notes,
  bpm = 120,
  beatTimes,
  downbeatTimes,
  playheadTime = 0,
  annotations,
  focusedAnnotationId,
  onSeek,
  selectionTimeRange,
  selectedNoteIds,
  emphasizeSelection = false,
  onSelectRange,
  onAnnotationClick,
}: {
  notes: Note[];
  bpm?: number;
  beatTimes?: number[];
  downbeatTimes?: number[];
  playheadTime?: number;
  annotations?: AnalysisAnnotation[];
  focusedAnnotationId?: string | null;
  onSeek?: (seconds: number) => void;
  selectionTimeRange?: TimeRange | null;
  selectedNoteIds?: string[];
  emphasizeSelection?: boolean;
  onSelectRange?: (start: number, end: number) => void;
  onSelectNotes?: (ids: string[]) => void;
  onAnnotationClick?: (annotation: AnalysisAnnotation) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [previewRange, setPreviewRange] = useState<TimeRange | null>(null);
  const dragRef = useRef<{ startX: number; moved: boolean } | null>(null);
  const layout = useMemo(
    () => (notes.length ? buildLayout(notes, bpm, beatTimes, downbeatTimes) : null),
    [notes, bpm, beatTimes, downbeatTimes],
  );
  const playheadX = layout ? timeToX(playheadTime, bpm) : 0;
  const visibleTimeRange =
    previewRange ??
    (selectionTimeRange && selectionTimeRange.end > selectionTimeRange.start
      ? selectionTimeRange
      : null);
  const highlightIds = useMemo(() => {
    const ids = new Set(selectedNoteIds ?? []);
    if (!visibleTimeRange) return ids;
    for (const note of notes) {
      if (note.id && note.start < visibleTimeRange.end && note.end > visibleTimeRange.start) {
        ids.add(note.id);
      }
    }
    return ids;
  }, [notes, selectedNoteIds, visibleTimeRange]);
  const activeNotes = useMemo(
    () => layout?.notes.filter((note) => playheadTime >= note.start && playheadTime <= note.end) ?? [],
    [layout, playheadTime],
  );
  const activeKeys = useMemo(
    () => new Set(activeNotes.map((note) => note.key)),
    [activeNotes],
  );
  const selectedNotes = useMemo(
    () => layout?.notes.filter(
      (note) => !activeKeys.has(note.key) && Boolean(note.id && highlightIds.has(note.id)),
    ) ?? [],
    [activeKeys, highlightIds, layout],
  );

  useEffect(() => {
    const element = scrollRef.current;
    if (!element || !layout || playheadTime <= 0) return;
    const viewWidth = element.clientWidth;
    const target = Math.max(0, playheadX - viewWidth / 2);
    element.scrollLeft = target;
  }, [layout, playheadTime, playheadX]);

  function handlePointerDown(event: React.PointerEvent<SVGSVGElement>) {
    dragRef.current = { startX: event.clientX, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    if (Math.abs(event.clientX - drag.startX) > 4) drag.moved = true;
    if (drag.moved && onSelectRange) {
      const rect = event.currentTarget.getBoundingClientRect();
      const scrollLeft = scrollRef.current?.scrollLeft ?? 0;
      const x = event.clientX - rect.left + scrollLeft;
      const time = Math.max(0, ((x - LABEL_W) / (PPQ * bpm)) * 60);
      const startTime = Math.max(
        0,
        ((drag.startX - rect.left + scrollLeft - LABEL_W) / (PPQ * bpm)) * 60,
      );
      setPreviewRange({
        start: Math.max(0, Math.min(startTime, time)),
        end: Math.max(0, Math.max(startTime, time)),
      });
    }
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    const drag = dragRef.current;
    dragRef.current = null;
    if (!drag) return;
    if (drag.moved) {
      if (previewRange && onSelectRange) {
        onSelectRange(previewRange.start, previewRange.end);
      }
      setPreviewRange(null);
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const scrollLeft = scrollRef.current?.scrollLeft ?? 0;
    const x = event.clientX - rect.left + scrollLeft;
    const clickTime = Math.max(0, ((x - LABEL_W) / (PPQ * bpm)) * 60);
    if (onAnnotationClick && annotations) {
      for (const annotation of annotations) {
        if (clickTime >= annotation.startSeconds && clickTime <= annotation.endSeconds) {
          onAnnotationClick(annotation);
          return;
        }
      }
    }
    onSeek?.(clickTime);
  }

  if (!layout) return <p className="muted">No notes to display.</p>;

  return (
    <div className="piano-roll-container" data-testid="piano-roll">
      <div className="piano-roll-scroll" ref={scrollRef}>
        <svg
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          preserveAspectRatio="xMinYMin meet"
          width={layout.width}
          height={layout.height}
          style={{ display: "block" }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          role={onSeek || onSelectRange ? "button" : undefined}
          aria-label={
            onSelectRange
              ? "Select region or seek playback from piano roll"
              : "Seek playback from piano roll"
          }
        >
          <PianoRollBaseLayer layout={layout} bpm={bpm} />

          <g data-piano-roll-dynamic-layer="true">
            {annotations?.map((annotation) => {
              const x1 = timeToX(annotation.startSeconds, bpm);
              const x2 = timeToX(annotation.endSeconds, bpm);
              const isFocused = annotation.id === focusedAnnotationId;
              let colorVar: string;
              switch (annotation.category) {
                case "rhythm":
                  colorVar = "var(--color-rhythm)";
                  break;
                case "theory":
                  colorVar = "var(--color-theory, #8b5cf6)";
                  break;
                default:
                  colorVar = "var(--color-harmony)";
              }
              return (
                <g key={annotation.id} pointerEvents="none">
                  <rect
                    x={x1}
                    y={TOP_PAD}
                    width={Math.max(x2 - x1, 1)}
                    height={layout.height - TOP_PAD}
                    fill={colorVar}
                    fillOpacity={isFocused ? 0.15 : 0.045}
                  />
                  {isFocused && (
                    <rect
                      x={x1}
                      y={TOP_PAD}
                      width={Math.max(x2 - x1, 1)}
                      height={layout.height - TOP_PAD}
                      fill="none"
                      stroke={colorVar}
                      strokeWidth={1.25}
                      strokeOpacity={0.42}
                    />
                  )}
                </g>
              );
            })}

            {visibleTimeRange && (
              <rect
                data-selection-range="true"
                data-selection-emphasized={emphasizeSelection ? "true" : undefined}
                x={timeToX(visibleTimeRange.start, bpm)}
                y={TOP_PAD}
                width={Math.max(
                  timeToX(visibleTimeRange.end, bpm) - timeToX(visibleTimeRange.start, bpm),
                  2,
                )}
                height={layout.height - TOP_PAD}
                fill="var(--accent)"
                fillOpacity={emphasizeSelection ? 0.18 : 0.085}
                stroke="var(--accent)"
                strokeWidth={emphasizeSelection ? 1.4 : 0.75}
                strokeOpacity={emphasizeSelection ? 0.82 : 0.38}
                pointerEvents="none"
              />
            )}

            <NoteOverlay notes={selectedNotes} state="selected" rowH={layout.rowH} />
            <NoteOverlay notes={activeNotes} state="active" rowH={layout.rowH} />

            {playheadTime > 0 && playheadX <= layout.width && (
              <g data-playhead="true" pointerEvents="none">
                <line
                  x1={playheadX}
                  y1={TOP_PAD - 1}
                  x2={playheadX}
                  y2={layout.height}
                  stroke="var(--score-playback)"
                  strokeWidth={1.25}
                  strokeOpacity={0.92}
                />
                <rect
                  x={playheadX - 3}
                  y={TOP_PAD - 5}
                  width={6}
                  height={3}
                  rx={1.5}
                  fill="var(--score-playback)"
                />
              </g>
            )}
          </g>
        </svg>
      </div>
      <div className="piano-roll-footer">
        <span className="muted">{notes.length} notes &middot; {layout.endTime.toFixed(1)}s</span>
        {playheadTime > 0 && <span className="muted">{playheadTime.toFixed(1)}s</span>}
      </div>
    </div>
  );
}
