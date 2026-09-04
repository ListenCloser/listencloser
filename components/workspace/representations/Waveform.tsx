"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getDecodedAudio } from "@/lib/audio-buffer-cache";
import { canvasMeasurementFont } from "@/lib/canvas-typography";
import { withAlpha } from "@/lib/color";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";

const WAVEFORM_HEIGHT = 220;
const RULER_HEIGHT = 16;
const FALLBACK_WIDTH = 900;

/**
 * Waveform visualization — large horizontal canvas with sparse elapsed-time
 * ruler, shared playback signal, selection, and optional analysis overlays.
 *
 * The visible bars are derived only from measured min/max PCM peaks. Visual
 * craft must not invent samples, smoothing, musical structure, or timing data.
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
  onClearSelection,
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
  onClearSelection?: () => void;
  onAnnotationClick?: (annotation: AnalysisAnnotation) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rulerRef = useRef<HTMLCanvasElement>(null);
  const peaksRef = useRef<{ min: number; max: number }[]>([]);
  const durationRef = useRef(0);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const draggingRef = useRef<{ startX: number; startTime: number; moved: boolean } | null>(null);
  const [preview, setPreview] = useState<{ start: number; end: number } | null>(null);
  const [canvasWidth, setCanvasWidth] = useState(FALLBACK_WIDTH);
  const [devicePixelRatio, setDevicePixelRatio] = useState(1);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const measure = () => {
      const width = canvas.getBoundingClientRect().width;
      if (width > 0) setCanvasWidth(Math.round(width));
      setDevicePixelRatio(Math.max(1, window.devicePixelRatio || 1));
    };

    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }

    const observer = new ResizeObserver(measure);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!url) return;
    let cancelled = false;

    peaksRef.current = [];
    durationRef.current = 0;
    draggingRef.current = null;
    setPreview(null);
    setStatus("loading");

    getDecodedAudio(url)
      .then((decoded) => {
        if (cancelled) return;
        const channel = decoded.getChannelData(0);
        // Keep a substantially denser measured envelope than the eventual
        // display bars. The visible renderer may aggregate these extrema for
        // the current width, but it never has to re-infer missing transients.
        const targetSegments = Math.max(2048, Math.floor(decoded.duration * 64));
        const segments = Math.min(16384, targetSegments, channel.length);
        const per = Math.max(1, Math.ceil(channel.length / Math.max(1, segments)));
        const peaks: { min: number; max: number }[] = [];
        for (let i = 0; i < segments; i += 1) {
          const start = i * per;
          if (start >= channel.length) break;
          const end = Math.min(channel.length, start + per);
          let min = 0;
          let max = 0;
          for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
            const sample = channel[sampleIndex] ?? 0;
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
    (time: number) => (duration > 0 ? (time / duration) * canvasWidth : 0),
    [canvasWidth, duration],
  );

  useEffect(() => {
    const canvas = rulerRef.current;
    if (!canvas || duration <= 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvasWidth;
    const h = RULER_HEIGHT;
    ctx.resetTransform();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.scale(devicePixelRatio, devicePixelRatio);

    const styles = getComputedStyle(document.documentElement);
    const muted = styles.getPropertyValue("--muted").trim() || "#575a5e";

    ctx.fillStyle = muted;
    ctx.font = canvasMeasurementFont(styles);
    ctx.textAlign = "center";

    const targets = [0, 15, 30, 45, 60, 90, 120, 180, 240, 300, 600];
    let interval = 60;
    for (const t of targets) {
      if (t > 0 && duration / t <= 5) { interval = t; break; }
    }
    if (duration > 1200) interval = 300;

    for (let t = 0; t <= duration; t += interval) {
      const x = (t / duration) * w;
      ctx.globalAlpha = 0.18;
      ctx.fillRect(x, h - 2, 1, 2);
      ctx.globalAlpha = 0.54;
      const m = Math.floor(t / 60);
      const s = Math.floor(t % 60);
      ctx.fillText(`${m}:${s.toString().padStart(2, "0")}`, x, h - 4);
    }
    ctx.globalAlpha = 1;
  }, [canvasWidth, devicePixelRatio, duration]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const canvasCtx = canvas.getContext("2d");
    if (!canvasCtx) return;

    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue("--accent").trim() || "#dff45a";
    const playhead = styles.getPropertyValue("--score-playback").trim() || "#ff745d";
    const trace = styles.getPropertyValue("--waveform-trace").trim()
      || styles.getPropertyValue("--text").trim()
      || "#dce0d8";
    const axis = styles.getPropertyValue("--waveform-axis").trim()
      || styles.getPropertyValue("--border").trim()
      || "#cbc6bc";
    const bg = styles.getPropertyValue("--panel").trim() || "#0b0d0c";
    const rhythmColor = styles.getPropertyValue("--color-rhythm").trim() || "#929b96";
    const harmonyColor = styles.getPropertyValue("--color-harmony").trim() || "#819b9b";
    const theoryColor = styles.getPropertyValue("--color-theory").trim() || "#819b9b";

    const w = canvasWidth;
    const h = WAVEFORM_HEIGHT;
    const mid = h / 2;
    canvasCtx.resetTransform();
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    canvasCtx.scale(devicePixelRatio, devicePixelRatio);
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
        const rangeWidth = Math.max(x2 - x1, 1);
        canvasCtx.fillStyle = withAlpha(color, isFocused ? 0.075 : 0.018);
        canvasCtx.fillRect(x1, 0, rangeWidth, h);
        canvasCtx.fillStyle = withAlpha(color, isFocused ? 0.72 : 0.38);
        canvasCtx.fillRect(x1, 0, rangeWidth, isFocused ? 2 : 1);
        if (isFocused) {
          canvasCtx.strokeStyle = withAlpha(color, 0.34);
          canvasCtx.lineWidth = 1;
          canvasCtx.strokeRect(x1 + 0.5, 0.5, Math.max(rangeWidth - 1, 1), h - 1);
        }
      }
    }

    canvasCtx.save();
    canvasCtx.strokeStyle = axis;
    canvasCtx.globalAlpha = 0.48;
    canvasCtx.lineWidth = 1;
    canvasCtx.setLineDash([2, 5]);
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, mid + 0.5);
    canvasCtx.lineTo(w, mid + 0.5);
    canvasCtx.stroke();
    canvasCtx.restore();

    const peaks = peaksRef.current;
    if (peaks.length > 0) {
      // waveform-playlist and Field both treat bar width/gap as display-space
      // decisions over measured peaks. Use the actual CSS width here (rather
      // than the old fixed 900px backing store) so large canvases gain detail.
      const barWidth = 1.5;
      const gap = 1.75;
      const barCount = Math.max(1, Math.min(peaks.length, Math.floor(w / (barWidth + gap))));
      const usedWidth = (barCount - 1) * (barWidth + gap) + barWidth;
      const left = Math.max(0, (w - usedWidth) / 2);

      for (let index = 0; index < barCount; index += 1) {
        const start = Math.floor((index / barCount) * peaks.length);
        const end = Math.max(start + 1, Math.floor(((index + 1) / barCount) * peaks.length));
        let topPeak = 0;
        let bottomPeak = 0;
        for (let peakIndex = start; peakIndex < Math.min(end, peaks.length); peakIndex += 1) {
          topPeak = Math.max(topPeak, peaks[peakIndex].max);
          bottomPeak = Math.max(bottomPeak, peaks[peakIndex].min);
        }
        const top = mid - Math.max(1.1, topPeak * h * 0.45);
        const bottom = mid + Math.max(1.1, bottomPeak * h * 0.45);
        const x = left + index * (barWidth + gap);
        const value = Math.max(topPeak, bottomPeak);

        canvasCtx.fillStyle = trace;
        canvasCtx.globalAlpha = 0.3 + Math.min(1, value) * 0.58;
        canvasCtx.beginPath();
        canvasCtx.roundRect(x, top, barWidth, Math.max(2.2, bottom - top), barWidth / 2);
        canvasCtx.fill();
      }
      canvasCtx.globalAlpha = 1;
    }

    const range = preview ?? selection?.timeRange ?? null;
    if (range && duration > 0) {
      const x1 = timeToX(range.start);
      const x2 = timeToX(range.end);
      const rangeWidth = Math.max(x2 - x1, 1);
      canvasCtx.fillStyle = withAlpha(accent, emphasizeSelection ? 0.11 : 0.06);
      canvasCtx.fillRect(x1, 0, rangeWidth, h);
      canvasCtx.strokeStyle = withAlpha(accent, emphasizeSelection ? 0.72 : 0.42);
      canvasCtx.lineWidth = emphasizeSelection ? 1 : 0.75;
      canvasCtx.strokeRect(x1 + 0.5, 0.5, Math.max(rangeWidth - 1, 1), h - 1);
    }

    if (position > 0 && duration > 0) {
      const x = timeToX(position);
      canvasCtx.strokeStyle = withAlpha(playhead, 0.72);
      canvasCtx.lineWidth = 0.75;
      canvasCtx.beginPath();
      canvasCtx.moveTo(x, 0);
      canvasCtx.lineTo(x, h);
      canvasCtx.stroke();
      canvasCtx.fillStyle = withAlpha(playhead, 0.82);
      canvasCtx.fillRect(x - 1.5, 0, 3, 3);
    }
  }, [
    annotations,
    canvasWidth,
    devicePixelRatio,
    duration,
    emphasizeSelection,
    focusedAnnotationId,
    position,
    preview,
    selection,
    status,
    timeToX,
  ]);

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
      onClearSelection?.();
      onSeek?.(clickTime);
    }
  }

  return (
    <div className="waveform-wrap" data-testid="waveform">
      <canvas
        ref={rulerRef}
        className="waveform-ruler"
        width={Math.round(canvasWidth * devicePixelRatio)}
        height={Math.round(RULER_HEIGHT * devicePixelRatio)}
        style={{ width: "100%", height: RULER_HEIGHT }}
      />
      <canvas
        ref={canvasRef}
        className="waveform"
        data-testid="waveform-canvas"
        data-waveform-state={status}
        data-waveform-renderer="min-max-bars"
        data-waveform-segments={status === "ready" ? peaksRef.current.length : 0}
        data-selection-emphasized={emphasizeSelection ? "true" : undefined}
        width={Math.round(canvasWidth * devicePixelRatio)}
        height={Math.round(WAVEFORM_HEIGHT * devicePixelRatio)}
        style={{ height: WAVEFORM_HEIGHT }}
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
