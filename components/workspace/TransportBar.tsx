"use client";

import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function TransportBar() {
  const { transport, play, pause, stop, toggle, toggleLoop } =
    useTransport();
  const { timeline, totalDuration } = useTimeline();

  const { isPlaying, position, loopEnabled, loopStart, loopEnd } = transport;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--s-3)",
        padding: "var(--s-2) var(--s-4)",
        background: "var(--panel-2)",
        borderBottom: "1px solid var(--border)",
        minHeight: 48,
        fontSize: "var(--fs-xs)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "var(--s-1)" }}>
        <button
          className="icon-btn ghost"
          onClick={toggle}
          style={{ padding: "4px 10px", fontSize: 14 }}
          title={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? "⏸" : "▶"}
        </button>

        <button
          className="icon-btn ghost"
          onClick={stop}
          style={{ padding: "4px 10px", fontSize: 12 }}
          title="Stop"
        >
          ⏹
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
        <button
          className="icon-btn ghost"
          style={{ padding: "2px 6px", opacity: 0.4 }}
          disabled
          title="Previous marker (coming soon)"
        >
          ⏮
        </button>

        <button
          className="icon-btn ghost"
          style={{ padding: "2px 6px", opacity: 0.4 }}
          disabled
          title="Next marker (coming soon)"
        >
          ⏭
        </button>
      </div>

      <span
        style={{
          fontFamily: "var(--font-mono)",
          color: "var(--text)",
          minWidth: 54,
          textAlign: "center",
        }}
      >
        {formatTime(position)}
      </span>

      <span style={{ color: "var(--muted)" }}>
        / {formatTime(totalDuration)}
      </span>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
        <button
          className="icon-btn ghost"
          onClick={toggleLoop}
          style={{
            padding: "2px 8px",
            color: loopEnabled ? "var(--accent)" : "var(--muted)",
            background: loopEnabled ? "var(--accent-soft)" : undefined,
          }}
          title="Toggle loop"
        >
          ↺
        </button>

        {loopEnabled && loopStart !== null && loopEnd !== null && (
          <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)" }}>
            {formatTime(loopStart)} – {formatTime(loopEnd)}
          </span>
        )}
      </div>

      <div style={{ flex: 1 }} />

      {transport.activeSource && (
        <span
          style={{
            color: "var(--muted)",
            fontSize: "var(--fs-xs)",
            maxWidth: 180,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {transport.activeSource.label}
        </span>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--s-1)",
          padding: "2px 8px",
          background: "var(--panel-3)",
          borderRadius: "var(--r-full)",
          fontFamily: "var(--font-mono)",
          color: "var(--muted)",
        }}
      >
        {timeline.bpm} BPM
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--s-1)" }}>
        <button
          className="icon-btn ghost"
          style={{ padding: "2px 6px", opacity: 0.4 }}
          disabled
          title="Zoom in (coming soon)"
        >
          +
        </button>
        <button
          className="icon-btn ghost"
          style={{ padding: "2px 6px", opacity: 0.4 }}
          disabled
          title="Zoom out (coming soon)"
        >
          −
        </button>
        <button
          className="icon-btn ghost"
          style={{ padding: "2px 6px", opacity: 0.4 }}
          disabled
          title="Fit to view (coming soon)"
        >
          ⇲
        </button>
      </div>
    </div>
  );
}
