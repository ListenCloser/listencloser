"use client";

import { useMemo } from "react";
import type { TranscribeResult } from "@/lib/music";
import { SHARP_NOTE_NAMES, computeChroma } from "@/lib/notes";

type Note = TranscribeResult["notes"][number];

// Hexagonal grid positions for 12 pitch classes arranged in a Tonnetz.
// Laid out so fifths go horizontal, major thirds diagonal-up, minor thirds diagonal-down.
const HEX_POSITIONS = [
  { pc: 0, x: 0, y: 2 },    // C
  { pc: 7, x: 1, y: 2 },    // G
  { pc: 2, x: 2, y: 2 },    // D
  { pc: 9, x: 3, y: 2 },    // A
  { pc: 4, x: 4, y: 2 },    // E
  { pc: 11, x: 5, y: 2 },   // B
  { pc: 6, x: 0.5, y: 1 },  // F#
  { pc: 1, x: 1.5, y: 1 },  // C#
  { pc: 8, x: 2.5, y: 1 },  // G#
  { pc: 3, x: 3.5, y: 1 },  // D#
  { pc: 10, x: 4.5, y: 1 }, // A#
  { pc: 5, x: 2, y: 0 },    // F
];

const HEX_R = 22;

function hexPath(cx: number, cy: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i - Math.PI / 6;
    pts.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`);
  }
  return `M${pts.join("L")}Z`;
}

export default function Tonnetz({ notes }: { notes: Note[] }) {
  const chroma = useMemo(() => computeChroma(notes), [notes]);
  if (!notes.length) return null;

  const SCALE = 50;
  const PAD_X = 40;
  const PAD_Y = 30;
  const W = 6 * SCALE + PAD_X * 2;
  const H = 3 * SCALE + PAD_Y * 2;

  // Build edge list (fifth connections only for clarity)
  const edges: { from: number; to: number }[] = [];
  for (const node of HEX_POSITIONS) {
    for (const inc of [7]) {
      const target = (node.pc + inc) % 12;
      const targetNode = HEX_POSITIONS.find((n) => n.pc === target);
      if (targetNode) {
        edges.push({ from: node.pc, to: target });
      }
    }
  }

  return (
    <div className="viz-panel">
      <div className="section-label">Tonnetz (harmonic relationships)</div>
      <div style={{ overflowX: "auto" }}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: "block" }}>
          {/* edges */}
          {edges.map((e, i) => {
            const a = HEX_POSITIONS.find((n) => n.pc === e.from)!;
            const b = HEX_POSITIONS.find((n) => n.pc === e.to)!;
            return (
              <line
                key={i}
                x1={PAD_X + a.x * SCALE}
                y1={PAD_Y + (2 - a.y) * SCALE}
                x2={PAD_X + b.x * SCALE}
                y2={PAD_Y + (2 - b.y) * SCALE}
                stroke="var(--border-strong)"
                strokeWidth={1}
                opacity={0.4}
              />
            );
          })}

          {/* hex nodes */}
          {HEX_POSITIONS.map((node) => {
            const cx = PAD_X + node.x * SCALE;
            const cy = PAD_Y + (2 - node.y) * SCALE;
            const intensity = chroma[node.pc];
            return (
              <g key={node.pc}>
                <path
                  d={hexPath(cx, cy, HEX_R)}
                  fill="var(--accent)"
                  opacity={0.1 + intensity * 0.7}
                  stroke="var(--border-strong)"
                  strokeWidth={1}
                />
                <text
                  x={cx}
                  y={cy - 2}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={intensity > 0.3 ? "var(--bg)" : "var(--text)"}
                  fontSize={12}
                  fontFamily="var(--font-mono)"
                  fontWeight="var(--fw-semibold)"
                >
                  {SHARP_NOTE_NAMES[node.pc]}
                </text>
                <text
                  x={cx}
                  y={cy + 12}
                  textAnchor="middle"
                  fill="var(--muted)"
                  fontSize={9}
                  fontFamily="var(--font-mono)"
                >
                  {Math.round(intensity * 100)}%
                </text>
              </g>
            );
          })}

          {/* axis labels */}
          <text x={PAD_X - 20} y={PAD_Y + SCALE + 4} fill="var(--muted)" fontSize={9} fontFamily="var(--font-mono)">→ fifths</text>
          <text x={W - 50} y={PAD_Y + SCALE * 2 - 10} fill="var(--muted)" fontSize={9} fontFamily="var(--font-mono)">↗ maj3</text>
        </svg>
      </div>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 0" }}>
        Horizontal = fifths, diagonal = thirds. Size/opacity = pitch class frequency.
      </p>
    </div>
  );
}
