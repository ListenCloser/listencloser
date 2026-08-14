"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { withAlpha } from "@/lib/color";
import type { MusicalSelection } from "@/lib/stores/workspace";

/**
 * Selectable audio waveform for the Listen representation.
 *
 * Decodes the original audio once and draws peaks as bars on a canvas. The
 * time axis is the original audio's own timeline (performance time), which is
 * the same timeline the shared transport playhead uses for the original and
 * transcription sources. A horizontal drag defines a shared timeRange
 * selection; a plain click seeks the transport.
 */
export default function Waveform({
  url,
  position,
  durationOverride,
  selection,
  onSeek,
  onSelect,
  height = 260,
}: {
  url: string;
  position: number;
  /** Overrides the decoded duration when the active source differs (e.g. score
      notation time); kept null to use the decoded original duration. */
  durationOverride?: number | null;
  selection?: MusicalSelection | null;
  onSeek?: (time: number) => void;
  onSelect?: (start: number, end: number) => void;
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const canvasCtx = canvas.getContext("2d");
    if (!canvasCtx) return;

    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue("--accent").trim() || "#bd513a";
    const trace = styles.getPropertyValue("--text").trim() || "#191a1b";
    const bg = styles.getPropertyValue("--panel-2").trim() || "#efede7";

    const w = canvas.width;
    const h = canvas.height;
    canvasCtx.fillStyle = bg;
    canvasCtx.fillRect(0, 0, w, h);

    const peaks = peaksRef.current;
    if (peaks.length > 0) {
      const mid = h / 2;
      const barW = w / peaks.length;
      canvasCtx.fillStyle = trace;
      canvasCtx.globalAlpha = 0.65;
      peaks.forEach((peak, i) => {
        const x = i * barW;
        const topPeak = Math.max(2, (peak.max * h) / 2);
        const bottomPeak = Math.max(2, (peak.min * h) / 2);
        canvasCtx.fillRect(x, mid - topPeak, Math.max(barW - 1, 1), topPeak + bottomPeak);
      });
      canvasCtx.globalAlpha = 1;
    } else if (status === "ready") {
      canvasCtx.fillStyle = trace;
      canvasCtx.globalAlpha = 0.4;
      canvasCtx.fillRect(0, h / 2 - 1, w, 2);
      canvasCtx.globalAlpha = 1;
    }

    const range = preview ?? selection?.timeRange ?? null;
    if (range && duration > 0) {
      const x1 = timeToX(range.start);
      const x2 = timeToX(range.end);
      canvasCtx.fillStyle = withAlpha(accent, 0.22);
      canvasCtx.fillRect(x1, 0, Math.max(x2 - x1, 1), h);
      canvasCtx.strokeStyle = accent;
      canvasCtx.lineWidth = 1.5;
      canvasCtx.strokeRect(x1, 1, Math.max(x2 - x1, 1), h - 2);
    }

    if (position > 0 && duration > 0) {
      const x = timeToX(position);
      canvasCtx.strokeStyle = accent;
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
        ref={canvasRef}
        className="waveform"
        data-testid="waveform-canvas"
        width={900}
        height={height}
        style={{ height }}
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
          Loading waveform…
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