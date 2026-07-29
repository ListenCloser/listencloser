"use client";

import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function TransportBar() {
  const { transport, play, pause, stop, toggle, toggleLoop } = useTransport();
  const { timeline, totalDuration } = useTimeline();
  const { isPlaying, position, loopEnabled, loopStart, loopEnd, activeSource } = transport;

  return (
    <div className="transport-bar">
      <div className="transport-group">
        <button className="transport-btn" onClick={toggle} title={isPlaying ? "Pause" : "Play"}>
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button className="transport-btn transport-btn-sm" onClick={stop} title="Stop">
          ⏹
        </button>
      </div>

      <div className="transport-group">
        <button className="transport-btn transport-btn-disabled" disabled title="Previous marker (coming soon)">⏮</button>
        <button className="transport-btn transport-btn-disabled" disabled title="Next marker (coming soon)">⏭</button>
      </div>

      <span className="transport-time">{formatTime(position)}</span>
      <span className="transport-time-muted">/ {formatTime(totalDuration)}</span>

      <div className="transport-group">
        <button
          className={`transport-btn ${loopEnabled ? "transport-btn-active" : ""}`}
          onClick={toggleLoop}
          title="Toggle loop"
        >
          ↺
        </button>
        {loopEnabled && loopStart !== null && loopEnd !== null && (
          <span className="transport-loop-range">{formatTime(loopStart)} – {formatTime(loopEnd)}</span>
        )}
      </div>

      <div className="transport-spacer" />

      {activeSource && <span className="transport-source">{activeSource.label}</span>}

      <div className="transport-bpm">{timeline.bpm} BPM</div>

      <div className="transport-group">
        <button className="transport-btn transport-btn-disabled" disabled title="Zoom in (coming soon)">+</button>
        <button className="transport-btn transport-btn-disabled" disabled title="Zoom out (coming soon)">−</button>
        <button className="transport-btn transport-btn-disabled" disabled title="Fit to view (coming soon)">⇲</button>
      </div>
    </div>
  );
}
