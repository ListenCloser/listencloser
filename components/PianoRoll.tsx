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

import { useRef, useEffect } from "react";
import type { TranscribeResult } from "@/lib/music";
import { pitchToName } from "@/lib/notes";

type Note = TranscribeResult["notes"][number];

const PPQ = 16;
const ROW_H = 24;
const LABEL_W = 40;
const TOP_PAD = 16;

export default function PianoRoll({
  notes,
  bpm = 120,
  playheadTime = 0,
}: {
  notes: Note[];
  bpm?: number;
  playheadTime?: number;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
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
    if (n.length > 0) rows.push({ pitch: p, label, notes: n });
  }

  const h = rows.length * ROW_H + TOP_PAD;
  const W = LABEL_W + totalPx;
  const playheadX = LABEL_W + (playheadTime / 60) * bpm * PPQ;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || playheadTime <= 0) return;
    const viewW = el.clientWidth;
    const target = Math.max(0, playheadX - viewW / 2);
    el.scrollLeft = target;
  }, [playheadX]);

  return (
    <div className="piano-roll-container" data-testid="piano-roll">
      <div className="piano-roll-scroll" ref={scrollRef}>
        <svg
          viewBox={`0 0 ${W} ${h}`}
          preserveAspectRatio="xMinYMin meet"
          width="100%"
          height={h}
          style={{ display: "block" }}
        >
          {/* Left label gutter */}
          <rect x={0} y={0} width={LABEL_W} height={h} fill="var(--panel-2)" />

          {/* Row stripes */}
          {rows.map((row, ri) => (
            <rect
              key={`stripe-${row.pitch}`}
              x={LABEL_W}
              y={ri * ROW_H + TOP_PAD}
              width={totalPx}
              height={ROW_H}
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

          {/* Note rows */}
          {rows.map((row, ri) => {
            const y = ri * ROW_H + TOP_PAD;
            return (
              <g key={row.pitch}>
                <text
                  x={4}
                  y={y + 16}
                  fill="var(--muted)"
                  fontSize={11}
                  fontFamily="var(--font-mono)"
                >
                  {row.label}
                </text>
                {row.notes.map((n, ni) => {
                  const x = LABEL_W + (n.start / 60) * bpm * PPQ;
                  const dur = n.end - n.start;
                  const w = Math.max((dur / 60) * bpm * PPQ, 4);
                  const active = playheadTime >= n.start && playheadTime <= n.end;
                  const velOpacity = 0.2 + (n.velocity / 127) * 0.6;
                  return (
                    <rect
                      key={ni}
                      x={x}
                      y={y + 2}
                      width={w}
                      height={ROW_H - 4}
                      rx={3}
                      fill="var(--accent)"
                      opacity={active ? 1 : velOpacity}
                      style={
                        active
                          ? { filter: "drop-shadow(0 0 6px var(--accent))" }
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
