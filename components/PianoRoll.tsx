/**
 * Piano roll visualization — SVG-based note display with playhead.
 *
 * UX-015 improvements:
 * - Better note styling with velocity-based opacity
 * - Improved spacing and row height
 * - Active note glow effect for clarity
 * - Footer with zoom hint
 */

"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { pitchToName } from "@/lib/notes";
import { withAlpha } from "@/lib/color";

type Note = { id?: string; pitch: number; start: number; end: number; velocity: number };
type TimeRange = { start: number; end: number };

const PPQ = 16;
const LABEL_W = 40;
const TOP_PAD = 16;

export default function PianoRoll({
  notes,
  bpm = 120,
  playheadTime = 0,
  onSeek,
  selectionTimeRange,
  selectedNoteIds,
  onSelectRange,
  onSelectNotes,
}: {
  notes: Note[];
  bpm?: number;
  playheadTime?: number;
  onSeek?: (seconds: number) => void;
  selectionTimeRange?: TimeRange | null;
  selectedNoteIds?: string[];
  onSelectRange?: (start: number, end: number) => void;
  onSelectNotes?: (ids: string[]) => void;
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

  const rows: { pitch: number; label: string; notes: Note[] }[] = [];
  for (let p = maxPitch; p >= minPitch; p--) {
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
    if (!onSeek) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - rect.left) + scrollRef.current!.scrollLeft;
    onSeek(Math.max(0, (x - LABEL_W) / (PPQ * bpm) * 60));
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
          <rect x={0} y={0} width={LABEL_W} height={h} fill="var(--panel-2)" />

          {/* Row stripes */}
          {rows.map((row, ri) => (
            <rect
              key={`stripe-${row.pitch}`}
              x={LABEL_W}
              y={ri * rowH + TOP_PAD}
              width={totalPx}
              height={rowH}
              fill={ri % 2 === 0 ? "var(--panel-2)" : "transparent"}
            />
          ))}

          {/* Beat grid */}
          {Array.from({ length: Math.floor(totalBeats) + 1 }, (_, i) => {
            const x = LABEL_W + i * PPQ;
            const isMeasure = i % 4 === 0;
            return (
              <line
                key={i}
                x1={x}
                y1={0}
                x2={x}
                y2={h}
                stroke={isMeasure ? "var(--border-strong)" : "var(--border)"}
                strokeWidth={isMeasure ? 1.5 : 0.5}
              />
            );
          })}

          {/* Selected time range highlight */}
          {visibleTimeRange && (
            <rect
              x={timeToX(visibleTimeRange.start)}
              y={0}
              width={Math.max(timeToX(visibleTimeRange.end) - timeToX(visibleTimeRange.start), 2)}
              height={h}
              fill="var(--accent)"
              fillOpacity={0.16}
              stroke="var(--accent)"
              strokeWidth={1}
            />
          )}

          {/* Note rows */}
          {rows.map((row, ri) => {
            const y = ri * rowH + TOP_PAD;
            return (
              <g key={row.pitch}>
                <text
                  x={4}
                  y={y + Math.min(rowH - 3, 13)}
                  fill="var(--muted)"
                  fontSize={Math.min(11, Math.max(8, rowH - 4))}
                  fontFamily="var(--font-mono)"
                >
                  {row.label}
                </text>
                {row.notes.map((n, ni) => {
                  const x = LABEL_W + (n.start / 60) * bpm * PPQ;
                  const dur = n.end - n.start;
                  const w = Math.max((dur / 60) * bpm * PPQ, 4);
                  const active = playheadTime >= n.start && playheadTime <= n.end;
                  const selected = n.id ? highlightIds.has(n.id) : false;
                  const velOpacity = 0.2 + (n.velocity / 127) * 0.6;
                  return (
                    <rect
                      key={ni}
                      x={x}
                      y={y + 2}
                      width={w}
                      height={Math.max(rowH - 3, 6)}
                      rx={3}
                      fill={selected ? "var(--accent-strong)" : "var(--accent)"}
                      opacity={active ? 1 : selected ? 0.95 : velOpacity}
                      style={
                        active
                          ? { filter: "drop-shadow(0 0 6px var(--accent))" }
                          : selected
                            ? { filter: "drop-shadow(0 0 4px var(--accent))" }
                            : undefined
                      }
                    >
                      <title>{row.label} @ {n.start.toFixed(2)}s · velocity {n.velocity}</title>
                    </rect>
                  );
                })}
              </g>
            );
          })}

          {/* Playhead */}
          {playheadTime > 0 && playheadX <= W && (
            <g>
              <line
                x1={playheadX}
                y1={0}
                x2={playheadX}
                y2={h}
                stroke="var(--accent-strong)"
                strokeWidth={2}
              />
              <polygon
                points={`${playheadX},0 ${playheadX + 7},${TOP_PAD - 5} ${playheadX},${TOP_PAD} ${playheadX - 7},${TOP_PAD - 5}`}
                fill="var(--accent-strong)"
              />
            </g>
          )}
        </svg>
      </div>
      <div className="piano-roll-footer">
        <span className="muted">{notes.length} notes · {endTime.toFixed(1)}s</span>
        {playheadTime > 0 && <span className="muted">{playheadTime.toFixed(1)}s</span>}
      </div>
    </div>
  );
}
