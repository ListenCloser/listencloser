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

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { pitchToName } from "@/lib/notes";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";

type Note = { id?: string; pitch: number; start: number; end: number; velocity: number };
type TimeRange = { start: number; end: number };
type PianoRollRow = { pitch: number; label: string; notes: Note[] };
type NoteGeometry = {
  key: string;
  note: Note;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  rx: number;
  velocityOpacity: number;
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

const StaticNoteLayer = memo(function StaticNoteLayer({
  rows,
  noteGeometry,
  rowH,
}: {
  rows: PianoRollRow[];
  noteGeometry: NoteGeometry[];
  rowH: number;
}) {
  return (
    <g data-piano-roll-layer="static-notes">
      {rows.map((row, ri) => {
        const y = ri * rowH + TOP_PAD;
        const isOctaveAnchor = row.pitch % 12 === 0;
        return (
          <text
            key={`label-${row.pitch}`}
            x={4}
            y={y + Math.min(rowH - 3, 12)}
            fill="var(--muted)"
            fontSize={Math.min(10, Math.max(8, rowH - 4))}
            fontFamily="var(--font-mono)"
            fontWeight={isOctaveAnchor ? 650 : 400}
            opacity={isOctaveAnchor ? 0.82 : row.notes.length ? 0.58 : 0.34}
          >
            {row.label}
          </text>
        );
      })}
      {noteGeometry.map(({ key, note, label, x, y, width, height, rx, velocityOpacity }) => (
        <rect
          key={key}
          data-note-state="default"
          x={x}
          y={y}
          width={width}
          height={height}
          rx={rx}
          fill="var(--text)"
          fillOpacity={velocityOpacity}
          stroke="var(--border)"
          strokeWidth={0.45}
          strokeOpacity={0.42}
        >
          <title>{label} @ {note.start.toFixed(2)}s · velocity {note.velocity}</title>
        </rect>
      ))}
    </g>
  );
});

function DynamicNoteOverlay({
  noteGeometry,
  playheadTime,
  highlightIds,
}: {
  noteGeometry: NoteGeometry[];
  playheadTime: number;
  highlightIds: Set<string>;
}) {
  const overlays = noteGeometry.filter(({ note }) => {
    const active = playheadTime >= note.start && playheadTime <= note.end;
    const selected = note.id ? highlightIds.has(note.id) : false;
    return active || selected;
  });

  if (!overlays.length) return null;

  return (
    <g data-piano-roll-layer="dynamic-notes" pointerEvents="none">
      {overlays.map(({ key, note, x, y, width, height, rx }) => {
        const active = playheadTime >= note.start && playheadTime <= note.end;
        return (
          <rect
            key={`overlay-${key}`}
            data-note-state={active ? "active" : "selected"}
            x={x}
            y={y}
            width={width}
            height={height}
            rx={rx}
            fill={active ? "var(--score-playback)" : "var(--accent)"}
            fillOpacity={active ? 0.94 : 0.82}
            stroke={active ? "var(--score-playback)" : "var(--accent)"}
            strokeWidth={active ? 1.3 : 1.05}
            strokeOpacity={active ? 0.96 : 0.78}
          />
        );
      })}
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
  const svgRef = useRef<SVGSVGElement>(null);

  const timeToX = useCallback(
    (time: number) => LABEL_W + (time / 60) * bpm * PPQ,
    [bpm],
  );

  const observedBeats = validSecondsGrid(beatTimes, 2);
  const observedDownbeats = observedBeats.length > 0
    ? validSecondsGrid(downbeatTimes)
    : [];
  const sorted = [...notes].sort((a, b) => a.start - b.start);
  const endTime = sorted.reduce((t, n) => Math.max(t, n.end), 0);
  const displayEndTime = Math.max(
    endTime,
    observedBeats.length > 0 ? observedBeats[observedBeats.length - 1] : 0,
  );
  const totalBeats = (displayEndTime / 60) * bpm;
  const totalPx = Math.max(totalBeats * PPQ, 300);

  const rows = useMemo<PianoRollRow[]>(() => {
    if (!notes.length) return [];
    const minPitch = Math.min(...notes.map((note) => note.pitch));
    const maxPitch = Math.max(...notes.map((note) => note.pitch));
    const pitchLow = Math.max(0, minPitch - 4);
    const pitchHigh = Math.min(127, maxPitch + 4);
    const notesByPitch = new Map<number, Note[]>();
    for (const note of notes) {
      const pitchNotes = notesByPitch.get(note.pitch);
      if (pitchNotes) pitchNotes.push(note);
      else notesByPitch.set(note.pitch, [note]);
    }
    const nextRows: PianoRollRow[] = [];
    for (let pitch = pitchHigh; pitch >= pitchLow; pitch--) {
      nextRows.push({
        pitch,
        label: pitchToName(pitch),
        notes: notesByPitch.get(pitch) ?? [],
      });
    }
    return nextRows;
  }, [notes]);

  const rowH = Math.max(12, Math.min(22, 520 / Math.max(rows.length, 1)));
  const h = rows.length * rowH + TOP_PAD;
  const W = LABEL_W + totalPx;
  const playheadX = LABEL_W + (playheadTime / 60) * bpm * PPQ;
  const timeLabelStep = displayEndTime <= 40 ? 5 : displayEndTime <= 120 ? 10 : 30;
  const timeLabels = Array.from(
    { length: Math.floor(displayEndTime / timeLabelStep) + 1 },
    (_, index) => index * timeLabelStep,
  );

  const noteGeometry = useMemo<NoteGeometry[]>(() => {
    const geometry: NoteGeometry[] = [];
    rows.forEach((row, rowIndex) => {
      const y = rowIndex * rowH + TOP_PAD + 2;
      row.notes.forEach((note, noteIndex) => {
        const x = LABEL_W + (note.start / 60) * bpm * PPQ;
        const duration = note.end - note.start;
        geometry.push({
          key: note.id ?? `${row.pitch}-${note.start}-${note.end}-${noteIndex}`,
          note,
          label: row.label,
          x,
          y,
          width: Math.max((duration / 60) * bpm * PPQ, 3),
          height: Math.max(rowH - 4, 5),
          rx: Math.min(2, rowH / 4),
          velocityOpacity: 0.28 + (note.velocity / 127) * 0.5,
        });
      });
    });
    return geometry;
  }, [bpm, rowH, rows]);

  const visibleTimeRange =
    previewRange ??
    (selectionTimeRange && selectionTimeRange.end > selectionTimeRange.start
      ? selectionTimeRange
      : null);

  const highlightIds = useMemo(() => {
    const ids = new Set(selectedNoteIds ?? []);
    if (visibleTimeRange) {
      for (const note of notes) {
        if (
          note.id &&
          note.start < visibleTimeRange.end &&
          note.end > visibleTimeRange.start
        ) {
          ids.add(note.id);
        }
      }
    }
    return ids;
  }, [notes, selectedNoteIds, visibleTimeRange]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || playheadTime <= 0) return;
    const viewW = el.clientWidth;
    const target = Math.max(0, playheadX - viewW / 2);
    el.scrollLeft = target;
  }, [playheadTime, playheadX]);

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
      const startT = Math.max(
        0,
        ((drag.startX - rect.left + scrollLeft - LABEL_W) / (PPQ * bpm)) * 60,
      );
      setPreviewRange({
        start: Math.max(0, Math.min(startT, time)),
        end: Math.max(0, Math.max(startT, time)),
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
    const x = event.clientX - rect.left + (scrollRef.current?.scrollLeft ?? 0);
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

  if (!notes.length) return <p className="muted">No notes to display.</p>;

  return (
    <div className="piano-roll-container" data-testid="piano-roll">
      <div className="piano-roll-scroll" ref={scrollRef}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${h}`}
          preserveAspectRatio="xMinYMin meet"
          width={W}
          height={h}
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
          <rect x={0} y={0} width={LABEL_W} height={h} fill="var(--panel)" />

          {rows.map((row, rowIndex) => {
            const isBlack = [1, 3, 6, 8, 10].includes(row.pitch % 12);
            const isOctaveAnchor = row.pitch % 12 === 0;
            return (
              <rect
                key={`stripe-${row.pitch}`}
                data-pitch-lane={isOctaveAnchor ? "octave-anchor" : isBlack ? "black-key" : "natural"}
                x={LABEL_W}
                y={rowIndex * rowH + TOP_PAD}
                width={totalPx}
                height={rowH}
                fill={isOctaveAnchor ? "var(--text)" : isBlack ? "var(--panel-2)" : "transparent"}
                fillOpacity={isOctaveAnchor ? 0.035 : isBlack ? 0.72 : 1}
              />
            );
          })}

          {rows.map((row, rowIndex) => {
            const isOctaveAnchor = row.pitch % 12 === 0;
            return (
              <line
                key={`guide-${row.pitch}`}
                x1={LABEL_W}
                y1={rowIndex * rowH + TOP_PAD + rowH}
                x2={W}
                y2={rowIndex * rowH + TOP_PAD + rowH}
                stroke="var(--border)"
                strokeWidth={isOctaveAnchor ? 0.65 : 0.3}
                strokeOpacity={isOctaveAnchor ? 0.36 : 0.17}
              />
            );
          })}

          {observedBeats.length > 0 ? (
            <>
              {observedBeats.map((seconds, index) => {
                const x = timeToX(seconds);
                return (
                  <line
                    key={`observed-beat-${index}`}
                    data-grid-kind="observed-beat"
                    data-beat-seconds={seconds}
                    x1={x}
                    y1={TOP_PAD}
                    x2={x}
                    y2={h}
                    stroke="var(--border)"
                    strokeWidth={0.5}
                    strokeOpacity={0.38}
                  />
                );
              })}
              {observedDownbeats.map((seconds, index) => {
                const x = timeToX(seconds);
                return (
                  <line
                    key={`observed-downbeat-${index}`}
                    data-grid-kind="observed-downbeat"
                    data-downbeat-seconds={seconds}
                    x1={x}
                    y1={TOP_PAD}
                    x2={x}
                    y2={h}
                    stroke="var(--text)"
                    strokeWidth={0.75}
                    strokeOpacity={0.34}
                  />
                );
              })}
            </>
          ) : (
            Array.from({ length: Math.floor(totalBeats) + 1 }, (_, index) => {
              const x = LABEL_W + index * PPQ;
              return (
                <line
                  key={`beat-${index}`}
                  data-grid-kind="tempo-beat"
                  x1={x}
                  y1={TOP_PAD}
                  x2={x}
                  y2={h}
                  stroke="var(--border)"
                  strokeWidth={0.5}
                  strokeOpacity={0.38}
                />
              );
            })
          )}

          {timeLabels.map((seconds) => {
            const x = timeToX(seconds);
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

          {annotations?.map((annotation) => {
            const x1 = timeToX(annotation.startSeconds);
            const x2 = timeToX(annotation.endSeconds);
            const isFocused = annotation.id === focusedAnnotationId;
            const colorVar = annotation.category === "rhythm"
              ? "var(--color-rhythm)"
              : annotation.category === "theory"
                ? "var(--color-theory, #8b5cf6)"
                : "var(--color-harmony)";
            return (
              <g key={annotation.id}>
                <rect
                  x={x1}
                  y={TOP_PAD}
                  width={Math.max(x2 - x1, 1)}
                  height={h - TOP_PAD}
                  fill={colorVar}
                  fillOpacity={isFocused ? 0.15 : 0.045}
                />
                {isFocused && (
                  <rect
                    x={x1}
                    y={TOP_PAD}
                    width={Math.max(x2 - x1, 1)}
                    height={h - TOP_PAD}
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
              x={timeToX(visibleTimeRange.start)}
              y={TOP_PAD}
              width={Math.max(timeToX(visibleTimeRange.end) - timeToX(visibleTimeRange.start), 2)}
              height={h - TOP_PAD}
              fill="var(--accent)"
              fillOpacity={emphasizeSelection ? 0.18 : 0.085}
              stroke="var(--accent)"
              strokeWidth={emphasizeSelection ? 1.4 : 0.75}
              strokeOpacity={emphasizeSelection ? 0.82 : 0.38}
            />
          )}

          <StaticNoteLayer rows={rows} noteGeometry={noteGeometry} rowH={rowH} />
          <DynamicNoteOverlay
            noteGeometry={noteGeometry}
            playheadTime={playheadTime}
            highlightIds={highlightIds}
          />

          {playheadTime > 0 && playheadX <= W && (
            <g data-playhead="true">
              <line
                x1={playheadX}
                y1={TOP_PAD - 1}
                x2={playheadX}
                y2={h}
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
        </svg>
      </div>
      <div className="piano-roll-footer">
        <span className="muted">{notes.length} notes &middot; {endTime.toFixed(1)}s</span>
        {playheadTime > 0 && <span className="muted">{playheadTime.toFixed(1)}s</span>}
      </div>
    </div>
  );
}
