"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getDecodedAudio } from "@/lib/audio-buffer-cache";
import { withAlpha } from "@/lib/color";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";

/**
 * Waveform visualization — large horizontal canvas with sparse time ruler,
 * shared blue playhead, terracotta selection, and optional analysis overlays.
 *
 * Visual language: quiet, neutral, minimal chrome.
 */
export default function Waveform({
  url,
  position,
  durationOverride,
  selection,
  emphasizeSelection = false,
  annotations,
  focusedAnnotationId,
  onSeek,
  onSelect,
  onAnnotationClick,
}: {
  url: string;
  position: number;
  durationOverride?: number | null;
  selection?: MusicalSelection | null;
  emphasizeSelection?: boolean;
  annotations?: AnalysisAnnotation[];
  focusedAnnotationId?: string | null;
  onSeek?: (time: number) => void;
  onSelect?: (start: number, end: number) => void;
  onAnnotationClick?: (annotation: AnalysisAnnotation) => void;
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

    // A new source must never inherit the prior recording's visual evidence.
    // Keep the same canvas object in place, but return it to a truthful neutral
    // frame until this exact source has decoded.
    peaksRef.current = [];
    durationRef.current = 0;
    draggingRef.current = null;
    setPreview(null);
    setStatus("loading");

    getDecodedAudio(url)
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
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  const duration = durationOverride && durationOverride > 0 ? durationOverride : durationRef.current;
  const timeToX = useCallback(
    (time: number) => (duration > 0 ? (time / duration) * canvasRef.current!.width : 0),
    [duration],
  );

  // Draw sparse time ruler — very minimal, just subtle tick marks
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

    // Very sparse: aim for 3-5 labels
    const targets = [0, 15, 30, 45, 60, 90, 120, 180, 240, 300, 600];
    let interval = 60;
    for (const t of targets) {
      if (duration / t <= 5) { interval = t; break; }
    }
    if (duration > 1200) interval = 300;

    for (let t = 0; t <= duration; t += interval) {
      const x = (t / duration) * w;
      ctx.globalAlpha = 0.3;
      ctx.fillRect(x, h - 2, 1, 2);
      ctx.globalAlpha = 0.5;
      const m = Math.floor(t / 60);
      const s = Math.floor(t % 60);
      ctx.fillText(`${m}:${s.toString().padStart(2, "0")}`, x, h - 4);
    }
    ctx.globalAlpha = 1;
  }, [duration]);

  // Draw waveform + annotations + selection + playhead
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const canvasCtx = canvas.getContext("2d");
    if (!canvasCtx) return;

    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue("--accent").trim() || "#bd513a";
    const playhead = styles.getPropertyValue("--score-playback").trim() || "#5a89a8";
    const trace = styles.getPropertyValue("--muted").trim() || "#575a5e";
    const bg = styles.getPropertyValue("--panel").trim() || "#f4f1eb";
    const rhythmColor = styles.getPropertyValue("--color-rhythm").trim() || "#b8963e";
    const harmonyColor = styles.getPropertyValue("--color-harmony").trim() || "#4a7c59";
    const theoryColor = styles.getPropertyValue("--color-theory").trim() || "#8b5cf6";

    const w = canvas.width;
    const h = canvas.height;
    canvasCtx.fillStyle = bg;
    canvasCtx.fillRect(0, 0, w, h);

    if (annotations && annotations.length > 0 && duration > 0) {
      for (const ann of annotations) {
        const x1 = timeToX(ann.startSeconds);
        const x2 = timeToX(ann.endSeconds);
        const isFocused = ann.id === focusedAnnotationId;
        let color: string;
        switch (ann.category) {
          case "rhythm":
            color = rhythmColor;
            break;
          case "theory":
            color = theoryColor;
            break;
          default:
            color = harmonyColor;
        }
        canvasCtx.fillStyle = withAlpha(color, isFocused ? 0.18 : 0.06);
        canvasCtx.fillRect(x1, 0, Math.max(x2 - x1, 1), h);
        if (isFocused) {
          canvasCtx.strokeStyle = withAlpha(color, 0.4);
          canvasCtx.lineWidth = 1.5;
          canvasCtx.strokeRect(x1, 0, Math.max(x2 - x1, 1), h);
        }
      }
    }

    const peaks = peaksRef.current;
    if (peaks.length > 0) {
      const mid = h / 2;
      const barW = w / peaks.length;
      canvasCtx.fillStyle = trace;
      canvasCtx.globalAlpha = 0.35;
      peaks.forEach((peak, i) => {
        const x = i * barW;
        const topPeak = Math.max(1, (peak.max * h) / 2);
        const bottomPeak = Math.max(1, (peak.min * h) / 2);
        canvasCtx.fillRect(x, mid - topPeak, Math.max(barW - 1, 1), topPeak + bottomPeak);
      });
      canvasCtx.globalAlpha = 1;
    } else {
      // A center hairline is a neutral track frame, not fabricated waveform
      // evidence. It gives the saved recording a stable object while decoding.
      canvasCtx.strokeStyle = withAlpha(trace, status === "loading" ? 0.16 : 0.1);
      canvasCtx.lineWidth = 1;
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, h / 2 + 0.5);
      canvasCtx.lineTo(w, h / 2 + 0.5);
      canvasCtx.stroke();
    }

    const range = preview ?? selection?.timeRange ?? null;
    if (range && duration > 0) {
      const x1 = timeToX(range.start);
      const x2 = timeToX(range.end);
      canvasCtx.fillStyle = withAlpha(accent, emphasizeSelection ? 0.24 : 0.15);
      canvasCtx.fillRect(x1, 0, Math.max(x2 - x1, 1), h);
      canvasCtx.strokeStyle = withAlpha(accent, emphasizeSelection ? 0.9 : 0.6);
      canvasCtx.lineWidth = emphasizeSelection ? 1.8 : 1;
      canvasCtx.strokeRect(x1, 0, Math.max(x2 - x1, 1), h);
    }

    if (position > 0 && duration > 0) {
      const x = timeToX(position);
      canvasCtx.strokeStyle = playhead;
      canvasCtx.lineWidth = 2;
      canvasCtx.beginPath();
      canvasCtx.moveTo(x, 0);
      canvasCtx.lineTo(x, h);
      canvasCtx.stroke();
    }
  }, [position, selection, preview, status, duration, timeToX, annotations, focusedAnnotationId, emphasizeSelection]);

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
    } else {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const clickTime = (x / rect.width) * duration;
      if (onAnnotationClick && annotations) {
        for (const ann of annotations) {
          if (clickTime >= ann.startSeconds && clickTime <= ann.endSeconds) {
            onAnnotationClick(ann);
            return;
          }
        }
      }
      if (onSeek) {
        onSeek(clickTime);
      }
    }
  }

  return (
    <div className="waveform-wrap" data-testid="waveform">
      <canvas
        ref={rulerRef}
        className="waveform-ruler"
        width={900}
        height={16}
        style={{ width: "100%", height: 16 }}
      />
      <canvas
        ref={canvasRef}
        className="waveform"
        data-testid="waveform-canvas"
        data-waveform-state={status}
        data-waveform-segments={status === "ready" ? peaksRef.current.length : 0}
        data-selection-emphasized={emphasizeSelection ? "true" : undefined}
        width={900}
        height={220}
        style={{ height: 220 }}
        role="slider"
        aria-label="Waveform selection"
        aria-busy={status === "loading"}
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
          Decoding recording&hellip;
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
