"use client";

import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function TransportBar() {
  const { transport, seek, setActiveSource, setLoop, stop, toggle, toggleLoop } = useTransport();
  const { timeline, totalDuration } = useTimeline();
  const { isPlaying, position, loopEnabled, loopStart, loopEnd, activeSource, sources } = transport;
  const hasSource = Boolean(activeSource);

  return (
    <div className="transport-bar">
      <div className="transport-group">
        <button type="button" className="transport-btn" onClick={toggle} title={hasSource ? (isPlaying ? "Pause" : "Play") : "Import audio to enable playback"} disabled={!hasSource}>
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button type="button" className="transport-btn transport-btn-sm" onClick={stop} title="Stop" disabled={!hasSource}>
          ⏹
        </button>
      </div>

      <span className="transport-time">{formatTime(position)}</span>
      <span className="transport-time-muted">/ {formatTime(totalDuration)}</span>
      <input className="transport-seek" type="range" aria-label="Playback position" min={0} max={Math.max(totalDuration, 0.01)} step={0.01} value={Math.min(position, Math.max(totalDuration, 0.01))} onChange={(event) => seek(Number(event.target.value))} disabled={!hasSource || totalDuration <= 0} />

      <div className="transport-group">
        <button
          className={`transport-btn ${loopEnabled ? "transport-btn-active" : ""}`}
          onClick={() => {
            if (!loopEnabled && (loopStart === null || loopEnd === null) && totalDuration > 0) setLoop(0, totalDuration);
            toggleLoop();
          }}
          title="Toggle loop"
          disabled={!hasSource}
        >
          ↺
        </button>
        {loopEnabled && loopStart !== null && loopEnd !== null && (
          <span className="transport-loop-range">{formatTime(loopStart)} – {formatTime(loopEnd)}</span>
        )}
      </div>

      <div className="transport-spacer" />

      {sources.length > 0 && (
        <select
          aria-label="Playback source"
          value={activeSource?.id ?? ""}
          onChange={(event) => {
            const source = sources.find((item) => item.id === event.target.value);
            if (source) setActiveSource(source);
          }}
          className="input"
          style={{ width: "auto", maxWidth: 280, padding: "4px 8px" }}
        >
          {sources.map((source) => (
            <option key={source.id} value={source.id}>{source.label}</option>
          ))}
        </select>
      )}

      <div className="transport-bpm">{timeline.bpm} BPM</div>

    </div>
  );
}
