/**
 * Piano roll visualization — SVG-based note display with playhead.
 *
 * Visual language:
 * - Subtle keyboard/pitch context with faint pitch guides
 * - Uniform beat grid (no implied meter unless backed by known data)
 * - Restrained neutral notes with velocity-based opacity
 * - Blue playhead (shared playback color)
 * - Terracotta selection (shared selection color)
 */

"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { pitchToName } from "@/lib/notes";
import { withAlpha } from "@/lib/color";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";

type Note = { id?: string; pitch: number; start: number; end: number; velocity: number };
type TimeRange = { start: number; end: number };

const PPQ = 16;
const LABEL_W = 36;
const TOP_PAD = 14;

export default function PianoRoll({
  notes,
  bpm = 120,
  playheadTime = 0,
  annotations,
  onSeek,
  selectionTimeRange,
  selectedNoteIds,
  onSelectRange,
  onSelectNotes,
  onAnnotationClick,
}: {
  notes: Note[];
  bpm?: number;
  playheadTime?: number;
  annotations?: AnalysisAnnotation[];
  onSeek?: (seconds: number) => void;
  selectionTimeRange?: TimeRange | null;
  selectedNoteIds?: string[];
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

  // Add margin above/below detected range for visual breathing room
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
    // Check if click is on an annotation
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

          {/* Row stripes — alternating for pitch context */}
          {rows.map((row, ri) => {
            const isBlack = [1, 3, 6, 8, 10].includes(row.pitch % 12);
            return (
              <rect
                key={`stripe-${row.pitch}`}
                x={LABEL_W}
                y={ri * rowH + TOP_PAD}
                width={totalPx}
                height={rowH}
                fill={isBlack ? "var(--panel-2)" : "transparent"}
              />
            );
          })}

          {/* Pitch guide lines (faint horizontal) */}
          {rows.map((row, ri) => (
            <line
              key={`guide-${row.pitch}`}
              x1={LABEL_W}
              y1={ri * rowH + TOP_PAD + rowH}
              x2={W}
              y2={ri * rowH + TOP_PAD + rowH}
              stroke="var(--border)"
              strokeWidth={0.3}
            />
          ))}

          {/* Beat grid — uniform temporal lines (no implied meter) */}
          {Array.from({ length: Math.floor(totalBeats) + 1 }, (_, i) => {
            const x = LABEL_W + i * PPQ;
            return (
              <line
                key={i}
                x1={x}
                y1={TOP_PAD}
                x2={x}
                y2={h}
                stroke="var(--border)"
                strokeWidth={0.4}
                strokeOpacity={0.4}
              />
            );
          })}

          {/* Analysis annotation bands (behind notes, above grid) */}
          {annotations &&
            annotations.map((ann) => {
              const x1 = timeToX(ann.startSeconds);
              const x2 = timeToX(ann.endSeconds);
              let colorVar: string;
              switch (ann.category) {
                case "rhythm":
                  colorVar = "var(--color-rhythm)";
                  break;
                case "theory":
                  colorVar = "var(--color-theory, #8b5cf6)";
                  break;
                case "cadence":
                  colorVar = "var(--color-cadence, #d97706)";
                  break;
                default:
                  colorVar = "var(--color-harmony)";
              }
              return (
                <rect
                  key={ann.id}
                  x={x1}
                  y={TOP_PAD}
                  width={Math.max(x2 - x1, 1)}
                  height={h - TOP_PAD}
                  fill={colorVar}
                  fillOpacity={0.06}
                />
              );
            })}

          {/* Selected time range highlight (terracotta) */}
          {visibleTimeRange && (
            <rect
              x={timeToX(visibleTimeRange.start)}
              y={0}
              width={Math.max(timeToX(visibleTimeRange.end) - timeToX(visibleTimeRange.start), 2)}
              height={h}
              fill="var(--accent)"
              fillOpacity={0.1}
              stroke="var(--accent)"
              strokeWidth={0.8}
              strokeOpacity={0.4}
            />
          )}

          {/* Note rows */}
          {rows.map((row, ri) => {
            const y = ri * rowH + TOP_PAD;
            return (
              <g key={row.pitch}>
                <text
                  x={4}
                  y={y + Math.min(rowH - 3, 12)}
                  fill="var(--muted)"
                  fontSize={Math.min(10, Math.max(8, rowH - 4))}
                  fontFamily="var(--font-mono)"
                  opacity={0.7}
                >
                  {row.label}
                </text>
                {row.notes.map((n, ni) => {
                  const x = LABEL_W + (n.start / 60) * bpm * PPQ;
                  const dur = n.end - n.start;
                  const w = Math.max((dur / 60) * bpm * PPQ, 3);
                  const active = playheadTime >= n.start && playheadTime <= n.end;
                  const selected = n.id ? highlightIds.has(n.id) : false;
                  const velOpacity = 0.15 + (n.velocity / 127) * 0.5;
                  return (
                    <rect
                      key={ni}
                      x={x}
                      y={y + 2}
                      width={w}
                      height={Math.max(rowH - 3, 5)}
                      rx={1}
                      fill={
                        active
                          ? "var(--score-playback)"
                          : selected
                            ? "var(--accent)"
                            : "var(--text)"
                      }
                      opacity={active ? 0.9 : selected ? 0.7 : velOpacity}
                    >
                      <title>{row.label} @ {n.start.toFixed(2)}s · velocity {n.velocity}</title>
                    </rect>
                  );
                })}
              </g>
            );
          })}

          {/* Playhead (blue) */}
          {playheadTime > 0 && playheadX <= W && (
            <g>
              <line
                x1={playheadX}
                y1={0}
                x2={playheadX}
                y2={h}
                stroke="var(--score-playback)"
                strokeWidth={1.5}
              />
              <polygon
                points={`${playheadX},0 ${playheadX + 5},${TOP_PAD - 4} ${playheadX},${TOP_PAD} ${playheadX - 5},${TOP_PAD - 4}`}
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
