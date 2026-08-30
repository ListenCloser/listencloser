/**
 * Piano roll visualization — SVG-based note display with playhead.
 *
 * Visual language:
 * - Quiet chromatic lanes with stronger octave/C anchors for pitch orientation
 * - Beat + half-beat hierarchy only; no fabricated measure grid without meter evidence
 * - Real note events dominate the grid, with velocity preserved through opacity
 * - Shared playback/selection tokens for active time and user-selected evidence
 * - Sparse wall-clock labels for orientation without implying musical structure
 */

"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { pitchToName } from "@/lib/notes";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";

type Note = { id?: string; pitch: number; start: number; end: number; velocity: number };
type TimeRange = { start: number; end: number };

const PPQ = 16;
const LABEL_W = 36;
const TOP_PAD = 18;

export default function PianoRoll({
  notes,
  bpm = 120,
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

  if (!notes.length) return <p className="muted">No notes to display.</p>;

  const sorted = [...notes].sort((a, b) => a.start - b.start);
  const endTime = sorted.reduce((t, n) => Math.max(t, n.end), 0);
  const totalBeats = (endTime / 60) * bpm;
  const totalPx = Math.max(totalBeats * PPQ, 300);

  const minPitch = Math.min(...notes.map((n) => n.pitch));
  const maxPitch = Math.max(...notes.map((n) => n.pitch));

  // Add margin above/below detected range for visual breathing room.
  const pitchLow = Math.max(0, minPitch - 4);
  const pitchHigh = Math.min(127, maxPitch + 4);

  const rows: { pitch: number; label: string; notes: Note[] }[] = [];
  for (let p = pitchHigh; p >= pitchLow; p--) {
    const label = pitchToName(p);
    const n = notes.filter((x) => x.pitch === p);
    rows.push({ pitch: p, label, notes: n });
  }

  const rowH = Math.max(12, Math.min(22, 520 / Math.max(rows.length, 1)));
  const h = rows.length * rowH + TOP_PAD;
  const W = LABEL_W + totalPx;
  const playheadX = LABEL_W + (playheadTime / 60) * bpm * PPQ;
  const timeLabelStep = endTime <= 40 ? 5 : endTime <= 120 ? 10 : 30;
  const timeLabels = Array.from(
    { length: Math.floor(endTime / timeLabelStep) + 1 },
    (_, index) => index * timeLabelStep,
  );

  const visibleTimeRange =
    previewRange ??
    (selectionTimeRange && selectionTimeRange.end > selectionTimeRange.start
      ? selectionTimeRange
      : null);

  const selectedIds = new Set(selectedNoteIds ?? []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || playheadTime <= 0) return;
    const viewW = el.clientWidth;
    const target = Math.max(0, playheadX - viewW / 2);
    el.scrollLeft = target;
  }, [playheadX]);

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
      const x = event.clientX - rect.left + scrollRef.current!.scrollLeft;
      const time = Math.max(0, ((x - LABEL_W) / (PPQ * bpm)) * 60);
      const startT = Math.max(0, ((drag.startX - rect.left + scrollRef.current!.scrollLeft - LABEL_W) / (PPQ * bpm)) * 60);
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
    const x = (event.clientX - rect.left) + scrollRef.current!.scrollLeft;
    const clickTime = Math.max(0, (x - LABEL_W) / (PPQ * bpm) * 60);
    // Check if click is on an annotation.
    if (onAnnotationClick && annotations) {
      for (const ann of annotations) {
        if (clickTime >= ann.startSeconds && clickTime <= ann.endSeconds) {
          onAnnotationClick(ann);
          return;
        }
      }
    }
    if (onSeek) {
      onSeek(clickTime);
    }
  }

  const rangeSelectedIds = visibleTimeRange
    ? notes
        .filter((n) => n.start < visibleTimeRange.end && n.end > visibleTimeRange.start)
        .map((n) => n.id)
        .filter((id): id is string => Boolean(id))
    : [];
  const highlightIds = new Set([...selectedIds, ...rangeSelectedIds]);

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
          {/* Left label gutter */}
          <rect x={0} y={0} width={LABEL_W} height={h} fill="var(--panel)" />

          {/* Pitch lanes: black-key context stays quiet; C anchors orient octaves. */}
          {rows.map((row, ri) => {
            const isBlack = [1, 3, 6, 8, 10].includes(row.pitch % 12);
            const isOctaveAnchor = row.pitch % 12 === 0;
            return (
              <rect
                key={`stripe-${row.pitch}`}
                data-pitch-lane={isOctaveAnchor ? "octave-anchor" : isBlack ? "black-key" : "natural"}
                x={LABEL_W}
                y={ri * rowH + TOP_PAD}
                width={totalPx}
                height={rowH}
                fill={isOctaveAnchor ? "var(--text)" : isBlack ? "var(--panel-2)" : "transparent"}
                fillOpacity={isOctaveAnchor ? 0.035 : isBlack ? 0.72 : 1}
              />
            );
          })}

          {/* Pitch guides: octave anchors are visible without turning into a piano keyboard. */}
          {rows.map((row, ri) => {
            const isOctaveAnchor = row.pitch % 12 === 0;
            return (
              <line
                key={`guide-${row.pitch}`}
                x1={LABEL_W}
                y1={ri * rowH + TOP_PAD + rowH}
                x2={W}
                y2={ri * rowH + TOP_PAD + rowH}
                stroke="var(--border)"
                strokeWidth={isOctaveAnchor ? 0.65 : 0.3}
                strokeOpacity={isOctaveAnchor ? 0.36 : 0.17}
              />
            );
          })}

          {/* Half-beat subdivisions improve timing precision without implying meter. */}
          {Array.from({ length: Math.floor(totalBeats * 2) + 1 }, (_, index) => {
            if (index % 2 === 0) return null;
            const x = LABEL_W + (index / 2) * PPQ;
            return (
              <line
                key={`subdivision-${index}`}
                data-grid-kind="subdivision"
                x1={x}
                y1={TOP_PAD}
                x2={x}
                y2={h}
                stroke="var(--border)"
                strokeWidth={0.3}
                strokeOpacity={0.16}
              />
            );
          })}

          {/* Beat grid — deliberately uniform because meter/downbeats are not inputs here. */}
          {Array.from({ length: Math.floor(totalBeats) + 1 }, (_, i) => {
            const x = LABEL_W + i * PPQ;
            return (
              <line
                key={`beat-${i}`}
                data-grid-kind="beat"
                x1={x}
                y1={TOP_PAD}
                x2={x}
                y2={h}
                stroke="var(--border)"
                strokeWidth={0.5}
                strokeOpacity={0.42}
              />
            );
          })}

          {/* Sparse elapsed-time labels orient long passages without inventing measures. */}
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

          {/* Analysis annotation bands (behind notes, above grid) */}
          {annotations &&
            annotations.map((ann) => {
              const x1 = timeToX(ann.startSeconds);
              const x2 = timeToX(ann.endSeconds);
              const isFocused = ann.id === focusedAnnotationId;
              let colorVar: string;
              switch (ann.category) {
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
                <g key={ann.id}>
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

          {/* Selected time range stays subordinate to notes and active time. */}
          {visibleTimeRange && (
            <rect
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

          {/* Note rows */}
          {rows.map((row, ri) => {
            const y = ri * rowH + TOP_PAD;
            const isOctaveAnchor = row.pitch % 12 === 0;
            return (
              <g key={row.pitch}>
                <text
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
                {row.notes.map((n, ni) => {
                  const x = LABEL_W + (n.start / 60) * bpm * PPQ;
                  const dur = n.end - n.start;
                  const w = Math.max((dur / 60) * bpm * PPQ, 3);
                  const active = playheadTime >= n.start && playheadTime <= n.end;
                  const selected = n.id ? highlightIds.has(n.id) : false;
                  const noteState = active ? "active" : selected ? "selected" : "default";
                  const velocityOpacity = 0.28 + (n.velocity / 127) * 0.5;
                  return (
                    <rect
                      key={ni}
                      data-note-state={noteState}
                      x={x}
                      y={y + 2}
                      width={w}
                      height={Math.max(rowH - 4, 5)}
                      rx={Math.min(2, rowH / 4)}
                      fill={active ? "var(--score-playback)" : selected ? "var(--accent)" : "var(--text)"}
                      fillOpacity={active ? 0.94 : selected ? 0.82 : velocityOpacity}
                      stroke={active ? "var(--score-playback)" : selected ? "var(--accent)" : "var(--border)"}
                      strokeWidth={active ? 1.3 : selected ? 1.05 : 0.45}
                      strokeOpacity={active ? 0.96 : selected ? 0.78 : 0.42}
                    >
                      <title>{row.label} @ {n.start.toFixed(2)}s · velocity {n.velocity}</title>
                    </rect>
                  );
                })}
              </g>
            );
          })}

          {/* Precise shared-time playhead with a quiet cap instead of a large marker. */}
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
