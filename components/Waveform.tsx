"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { withAlpha } from "@/lib/color";
import type { MusicalSelection } from "@/lib/stores/workspace";

/**
 * Waveform visualization — large horizontal canvas with time ruler,
 * shared blue playhead, and terracotta selection.
 *
 * Decodes the original audio once and draws peaks as bars. The time axis is
 * the original audio's own timeline (performance time). A horizontal drag
 * defines a shared timeRange selection; a plain click seeks the transport.
 */
export default function Waveform({
  url,
  position,
  durationOverride,
  selection,
  onSeek,
  onSelect,
}: {
  url: string;
  position: number;
  durationOverride?: number | null;
  selection?: MusicalSelection | null;
  onSeek?: (time: number) => void;
  onSelect?: (start: number, end: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rulerRef = useRef<HTMLCanvasElement>(null);
  const peaksRef = useRef<{ min: number; max: number }[]>([]);
  const durationRef = useRef(0);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const draggingRef = useRef<{ startX: number; startTime: number; moved: boolean } | null>(null);
  const [preview, setPreview] = useState<{ start: number; end: number } | null>(null);

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    setStatus("loading");
    const audioCtx = new AudioContext();
    window
      .fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error("waveform request failed");
        return response.arrayBuffer();
      })
      .then((buffer) => audioCtx.decodeAudioData(buffer))
      .then((decoded) => {
        if (cancelled) return;
        const channel = decoded.getChannelData(0);
        const segments = Math.max(240, Math.floor(decoded.duration * 24));
        const per = Math.max(1, Math.floor(channel.length / segments));
        const peaks: { min: number; max: number }[] = [];
        for (let i = 0; i < segments; i += 1) {
          let min = 0;
          let max = 0;
          for (let j = 0; j < per; j += 1) {
            const sample = channel[i * per + j] ?? 0;
            if (sample < min) min = sample;
            if (sample > max) max = sample;
          }
          peaks.push({ min: Math.abs(min), max });
        }
        peaksRef.current = peaks;
        durationRef.current = decoded.duration;
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      })
      .finally(() => {
        void audioCtx.close();
      });
    return () => {
      cancelled = true;
      void audioCtx.close();
    };
  }, [url]);

  const duration = durationOverride && durationOverride > 0 ? durationOverride : durationRef.current;
  const timeToX = useCallback(
    (time: number) => (duration > 0 ? (time / duration) * canvasRef.current!.width : 0),
    [duration],
  );

  // Draw time ruler
  useEffect(() => {
    const canvas = rulerRef.current;
    if (!canvas || duration <= 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const styles = getComputedStyle(document.documentElement);
    const muted = styles.getPropertyValue("--muted").trim() || "#575a5e";

    ctx.fillStyle = muted;
    ctx.font = "10px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "center";

    // Determine tick interval based on duration
    let interval = 1;
    if (duration > 120) interval = 30;
    else if (duration > 60) interval = 15;
    else if (duration > 30) interval = 5;
    else if (duration > 10) interval = 2;

    for (let t = 0; t <= duration; t += interval) {
      const x = (t / duration) * w;
      ctx.globalAlpha = 0.5;
      ctx.fillRect(x, h - 4, 1, 4);
      ctx.globalAlpha = 0.7;
      const m = Math.floor(t / 60);
      const s = Math.floor(t % 60);
      ctx.fillText(`${m}:${s.toString().padStart(2, "0")}`, x, h - 6);
    }
    ctx.globalAlpha = 1;
  }, [duration]);

  // Draw waveform + selection + playhead
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const canvasCtx = canvas.getContext("2d");
    if (!canvasCtx) return;

    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue("--accent").trim() || "#bd513a";
    const playhead = styles.getPropertyValue("--score-playback").trim() || "#5a89a8";
    const trace = styles.getPropertyValue("--text").trim() || "#191a1b";
    const bg = styles.getPropertyValue("--panel").trim() || "#f4f1eb";

    const w = canvas.width;
    const h = canvas.height;
    canvasCtx.fillStyle = bg;
    canvasCtx.fillRect(0, 0, w, h);

    const peaks = peaksRef.current;
    if (peaks.length > 0) {
      const mid = h / 2;
      const barW = w / peaks.length;
      canvasCtx.fillStyle = trace;
      canvasCtx.globalAlpha = 0.5;
      peaks.forEach((peak, i) => {
        const x = i * barW;
        const topPeak = Math.max(2, (peak.max * h) / 2);
        const bottomPeak = Math.max(2, (peak.min * h) / 2);
        canvasCtx.fillRect(x, mid - topPeak, Math.max(barW - 1, 1), topPeak + bottomPeak);
      });
      canvasCtx.globalAlpha = 1;
    } else if (status === "ready") {
      canvasCtx.fillStyle = trace;
      canvasCtx.globalAlpha = 0.3;
      canvasCtx.fillRect(0, h / 2 - 1, w, 2);
      canvasCtx.globalAlpha = 1;
    }

    // Selection (terracotta)
    const range = preview ?? selection?.timeRange ?? null;
    if (range && duration > 0) {
      const x1 = timeToX(range.start);
      const x2 = timeToX(range.end);
      canvasCtx.fillStyle = withAlpha(accent, 0.18);
      canvasCtx.fillRect(x1, 0, Math.max(x2 - x1, 1), h);
      canvasCtx.strokeStyle = accent;
      canvasCtx.lineWidth = 1;
      canvasCtx.strokeRect(x1, 0, Math.max(x2 - x1, 1), h);
    }

    // Playhead (blue)
    if (position > 0 && duration > 0) {
      const x = timeToX(position);
      canvasCtx.strokeStyle = playhead;
      canvasCtx.lineWidth = 1.5;
      canvasCtx.beginPath();
      canvasCtx.moveTo(x, 0);
      canvasCtx.lineTo(x, h);
      canvasCtx.stroke();
    }
  }, [position, selection, preview, status, duration, timeToX]);

  function handlePointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas || duration <= 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const time = (x / rect.width) * duration;
    draggingRef.current = { startX: x, startTime: time, moved: false };
    canvas.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const drag = draggingRef.current;
    const canvas = canvasRef.current;
    if (!drag || !canvas || duration <= 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    if (Math.abs(x - drag.startX) > 3) drag.moved = true;
    if (drag.moved) {
      const time = (x / rect.width) * duration;
      setPreview({
        start: Math.max(0, Math.min(drag.startTime, time)),
        end: Math.max(0, Math.max(drag.startTime, time)),
      });
    }
  }

  function handlePointerUp(event: React.PointerEvent<HTMLCanvasElement>) {
    const drag = draggingRef.current;
    const canvas = canvasRef.current;
    draggingRef.current = null;
    if (!drag || !canvas || duration <= 0) return;
    if (drag.moved) {
      const body = preview ?? { start: drag.startTime, end: drag.startTime };
      if (body.end - body.start >= 0.05 && onSelect) {
        onSelect(body.start, body.end);
      }
      setPreview(null);
    } else if (onSeek) {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      onSeek((x / rect.width) * duration);
    }
  }

  return (
    <div className="waveform-wrap" data-testid="waveform">
      <canvas
        ref={rulerRef}
        className="waveform-ruler"
        width={900}
        height={18}
        style={{ width: "100%", height: 18 }}
      />
      <canvas
        ref={canvasRef}
        className="waveform"
        data-testid="waveform-canvas"
        width={900}
        height={180}
        style={{ height: 180 }}
        role="slider"
        aria-label="Waveform selection"
        aria-valuetext={`${duration.toFixed(1)} seconds`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={() => {
          if (draggingRef.current?.moved) setPreview(null);
          draggingRef.current = null;
        }}
      />
      {status === "loading" && (
        <p className="muted" style={{ fontSize: "var(--fs-xs)", marginTop: 4 }}>
          Loading waveform&hellip;
        </p>
      )}
      {status === "error" && (
        <p className="muted" style={{ fontSize: "var(--fs-xs)", marginTop: 4 }}>
          Waveform unavailable.
        </p>
      )}
    </div>
  );
}
