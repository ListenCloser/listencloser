"use client";

import { useTransport } from "@/lib/stores/transport";

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function TransportBar() {
  const { transport, seek, setActiveSource, setLoop, stop, toggle, toggleLoop } = useTransport();
  const { isPlaying, position, duration, loopEnabled, loopStart, loopEnd, activeSource, sources } = transport;
  const hasSource = Boolean(activeSource);

  return (
    <section className="piece-transport" aria-label="Playback">
      <div className="piece-transport-controls">
        <button
          type="button"
          className="piece-play"
          onClick={toggle}
          aria-label={hasSource ? (isPlaying ? "Pause" : "Play") : "Import audio to enable playback"}
          disabled={!hasSource}
        >
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button type="button" className="piece-stop" onClick={stop} aria-label="Stop" disabled={!hasSource}>
          ■
        </button>
      </div>

      <div className="piece-timeline">
        <div className="piece-time">
          <span>{formatTime(position)}</span>
          <span>{formatTime(duration)}</span>
        </div>
        <input
          className="piece-seek"
          type="range"
          aria-label="Playback position"
          min={0}
          max={Math.max(duration, 0.01)}
          step={0.01}
          value={Math.min(position, Math.max(duration, 0.01))}
          onChange={(event) => seek(Number(event.target.value))}
          disabled={!hasSource || duration <= 0}
        />
      </div>

      <div className="piece-transport-controls">
        <button
          className={`piece-stop ${loopEnabled ? "piece-control-active" : ""}`}
          onClick={() => {
            if (!loopEnabled && (loopStart === null || loopEnd === null) && duration > 0) setLoop(0, duration);
            toggleLoop();
          }}
          aria-label="Toggle loop"
          disabled={!hasSource}
        >
          ↺
        </button>
      </div>

      {sources.length > 0 && (
        <div className="piece-hearing">
          <span className="piece-hearing-label">Hearing</span>
          <div className="piece-sources" role="group" aria-label="What you're hearing">
            {sources.map((source) => (
              <button
                key={source.id}
                type="button"
                className={`piece-source${activeSource?.id === source.id ? " active" : ""}`}
                aria-pressed={activeSource?.id === source.id}
                title={source.role === "score" ? "Notation time" : "Performance time"}
                onClick={() => setActiveSource(source)}
              >
                {source.label}
              </button>
            ))}
          </div>
          {activeSource?.role === "score" && (
            <span
              className="piece-hearing-note"
              style={{ fontSize: "var(--fs-xs)", color: "var(--muted)", whiteSpace: "nowrap" }}
              title="Original and Transcription play in performance time; the Score rendition plays in notation time."
            >
              notation time
            </span>
          )}
        </div>
      )}
    </section>
  );
}
