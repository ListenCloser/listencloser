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
    <section className="piece-transport" aria-label="Playback controls">
      <div className="piece-transport-controls">
        <button type="button" className="piece-play" onClick={toggle} aria-label={hasSource ? (isPlaying ? "Pause" : "Play") : "Import audio to enable playback"} disabled={!hasSource}>
          {isPlaying ? "⏸" : "▶"}
        </button>
        <button type="button" className="piece-stop" onClick={stop} aria-label="Stop" disabled={!hasSource}>
          ■
        </button>
      </div>
      <div className="piece-timeline">
        <div className="piece-time"><span>{formatTime(position)}</span><span>{formatTime(totalDuration)}</span></div>
        <input className="piece-seek" type="range" aria-label="Playback position" min={0} max={Math.max(totalDuration, 0.01)} step={0.01} value={Math.min(position, Math.max(totalDuration, 0.01))} onChange={(event) => seek(Number(event.target.value))} disabled={!hasSource || totalDuration <= 0} />
      </div>
      <div className="piece-transport-controls">
        <button
          className={`piece-stop ${loopEnabled ? "piece-control-active" : ""}`}
          onClick={() => {
            if (!loopEnabled && (loopStart === null || loopEnd === null) && totalDuration > 0) setLoop(0, totalDuration);
            toggleLoop();
          }}
          aria-label="Toggle loop"
          disabled={!hasSource}
        >
          ↺
        </button>
      </div>
      {sources.length > 0 && (
        <div className="piece-sources" role="group" aria-label="Compare playback sources">
          {sources.map((source) => (
            <button key={source.id} type="button" className={`piece-source${activeSource?.id === source.id ? " active" : ""}`} onClick={() => setActiveSource(source)}>
              {source.label.replace(" playback", "")}
            </button>
          ))}
        </div>
      )}
      <div className="piece-meter">{timeline.bpm} BPM</div>
    </section>
  );
}
