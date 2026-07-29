"use client";

import { pitchToName } from "@/lib/notes";

type DiffNote = {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
  status: "unchanged" | "added" | "removed" | "modified";
  counterpart?: { pitch: number; start: number; end: number; velocity: number };
};

type DiffLaneProps = {
  diffNotes: DiffNote[];
  minPitch: number;
  maxPitch: number;
  bpm?: number;
};

const PPQ = 16;
const ROW_H = 22;
const TOP_PAD = 14;
const LANE_W = 24;

const STATUS_FILL: Record<string, string> = {
  added: "var(--success)",
  removed: "var(--danger)",
  modified: "var(--accent-2)",
};

export default function DiffLane({
  diffNotes,
  minPitch,
  maxPitch,
  bpm = 120,
}: DiffLaneProps) {
  const rows: { pitch: number; label: string }[] = [];
  for (let p = maxPitch; p >= minPitch; p--) {
    rows.push({ pitch: p, label: pitchToName(p) });
  }
  const h = rows.length * ROW_H + TOP_PAD;

  const endTime = diffNotes.reduce((t, n) => Math.max(t, n.end, n.counterpart?.end ?? 0), 0);
  const totalBeats = (endTime / 60) * bpm;
  const totalPx = Math.max(totalBeats * PPQ, 300);
  const W = LANE_W + totalPx;

  const diffVisible = diffNotes.filter((d) => d.status !== "unchanged");

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minWidth: 28,
        background: "var(--panel-2)",
        borderLeft: "1px solid var(--border)",
        borderRight: "1px solid var(--border)",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          fontSize: "var(--fs-xs)",
          fontWeight: "var(--fw-medium)",
          color: "var(--muted)",
          textAlign: "center",
          padding: "var(--s-1) 0",
          borderBottom: "1px solid var(--border)",
          background: "var(--panel-3)",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        Diff
      </div>
      <div style={{ flex: 1, overflow: "auto", minHeight: 0 }}>
        <svg
          viewBox={`0 0 ${W} ${h}`}
          preserveAspectRatio="xMinYMin meet"
          width={LANE_W}
          height={h}
          style={{ display: "block" }}
        >
          <rect x={0} y={0} width={LANE_W} height={h} fill="var(--panel-2)" />

          {rows.map((row, ri) => (
            <rect
              key={`lane-stripe-${row.pitch}`}
              x={0}
              y={ri * ROW_H + TOP_PAD}
              width={LANE_W}
              height={ROW_H}
              fill={ri % 2 === 0 ? "var(--panel-3)" : "var(--panel-2)"}
            />
          ))}

          {diffVisible.map((d, i) => {
            const rowIdx = maxPitch - d.pitch;
            const y = rowIdx * ROW_H + TOP_PAD + ROW_H / 2;
            const x = LANE_W / 2;
            const fill = STATUS_FILL[d.status] ?? "var(--muted)";
            const r = 4;

            return (
              <g key={i}>
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={fill}
                  opacity={0.85}
                >
                  <title>
                    {d.status}: pitch {d.pitch} @ {d.start.toFixed(2)}s
                    {d.counterpart ? ` → pitch ${d.counterpart.pitch} @ ${d.counterpart.start.toFixed(2)}s` : ""}
                  </title>
                </circle>
                {d.status === "modified" && d.counterpart && (
                  <line
                    x1={x}
                    y1={y}
                    x2={x}
                    y2={(maxPitch - d.counterpart.pitch) * ROW_H + TOP_PAD + ROW_H / 2}
                    stroke={fill}
                    strokeWidth={1}
                    strokeDasharray="2 2"
                    opacity={0.5}
                  />
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
