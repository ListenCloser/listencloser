"use client";

import { useEffect, useRef, useState } from "react";
import { withAlpha } from "@/lib/color";
import type { AnalysisAnnotation } from "@/lib/analysis-annotations";
import type { MusicalSelection } from "@/lib/stores/workspace";
import { getSpectrogramData } from "@/lib/spectrogram-data";
import {
  frequencyToY,
  logarithmicFrequencyTicks,
  timeToX,
  xToTime,
  type SpectrogramData,
} from "@/lib/spectrogram";

type Range = { start: number; end: number };

function formatFrequency(value: number): string {
  return value >= 1000 ? `${value / 1000} kHz` : `${value} Hz`;
}

export default function Spectrogram({
  url,
  cacheIdentity,
  position,
  selection,
  annotations = [],
  focusedAnnotationId,
  onSeek,
  onSelect,
  onClearSelection,
}: {
  url: string;
  cacheIdentity?: string;
  position: number;
  selection?: MusicalSelection | null;
  annotations?: AnalysisAnnotation[];
  focusedAnnotationId?: string | null;
  onSeek?: (time: number) => void;
  onSelect?: (start: number, end: number) => void;
  onClearSelection?: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dataRef = useRef<SpectrogramData | null>(null);
  const draggingRef = useRef<{ startX: number; startTime: number; moved: boolean } | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [duration, setDuration] = useState(0);
  const [progress, setProgress] = useState(0);
  const [preview, setPreview] = useState<Range | null>(null);

  useEffect(() => {
    let cancelled = false;
    // A new source must never inherit pixels, duration, or drag state from the
    // prior recording. Keep a neutral canvas until this exact source resolves.
    dataRef.current = null;
    draggingRef.current = null;
    setDuration(0);
    setPreview(null);
    setStatus("loading");
    setProgress(0);

    const load = async () => {
      try {
        const result = await getSpectrogramData(url, {
          cacheIdentity,
          onProgress: (complete, total) => {
            if (!cancelled && complete % 12 === 0) setProgress(complete / total);
          },
        });
        if (cancelled) return;
        dataRef.current = result;
        setDuration(result.duration);
        setProgress(1);
        setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [cacheIdentity, url]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const styles = getComputedStyle(document.documentElement);
    const panel = styles.getPropertyValue("--panel").trim() || "#f4f1eb";
    const muted = styles.getPropertyValue("--muted").trim() || "#575a5e";
    const fontMono = styles.getPropertyValue("--font-mono").trim() || "monospace";
    const accent = styles.getPropertyValue("--accent").trim() || "#bd513a";
    const playhead = styles.getPropertyValue("--score-playback").trim() || "#5a89a8";
    const rhythm = styles.getPropertyValue("--color-rhythm").trim() || "#b8963e";
    const harmony = styles.getPropertyValue("--color-harmony").trim() || "#4a7c59";
    const theory = styles.getPropertyValue("--color-theory").trim() || "#8b5cf6";
    const width = canvas.width;
    const height = canvas.height;
    context.fillStyle = panel;
    context.fillRect(0, 0, width, height);

    const data = dataRef.current;
    if (!data) return;

    const image = context.createImageData(data.columns, data.bins);
    for (let column = 0; column < data.columns; column += 1) {
      for (let row = 0; row < data.bins; row += 1) {
        const strength = data.values[column * data.bins + row];
        const targetRow = data.bins - row - 1;
        const index = (targetRow * data.columns + column) * 4;
        // Warm restrained sequential map, deliberately avoiding rainbow hue jumps.
        image.data[index] = Math.round(42 + strength * 0.62);
        image.data[index + 1] = Math.round(38 + strength * 0.49);
        image.data[index + 2] = Math.round(33 + strength * 0.35);
        image.data[index + 3] = Math.round(strength * 0.94);
      }
    }
    const raster = document.createElement("canvas");
    raster.width = data.columns;
    raster.height = data.bins;
    const rasterContext = raster.getContext("2d");
    rasterContext?.putImageData(image, 0, 0);
    context.imageSmoothingEnabled = true;
    context.drawImage(raster, 0, 0, width, height);

    for (const annotation of annotations) {
      const x1 = timeToX(annotation.startSeconds, duration, width);
      const x2 = timeToX(annotation.endSeconds, duration, width);
      const color = annotation.category === "rhythm" ? rhythm : annotation.category === "theory" ? theory : harmony;
      const focused = annotation.id === focusedAnnotationId;
      context.fillStyle = withAlpha(color, focused ? 0.16 : 0.045);
      context.fillRect(x1, 0, Math.max(1, x2 - x1), height);
      if (focused) {
        context.strokeStyle = withAlpha(color, 0.45);
        context.strokeRect(x1, 0, Math.max(1, x2 - x1), height);
      }
    }

    const range = preview ?? selection?.timeRange;
    if (range) {
      const x1 = timeToX(range.start, duration, width);
      const x2 = timeToX(range.end, duration, width);
      context.fillStyle = withAlpha(accent, 0.16);
      context.fillRect(x1, 0, Math.max(1, x2 - x1), height);
      context.strokeStyle = withAlpha(accent, 0.62);
      context.strokeRect(x1, 0, Math.max(1, x2 - x1), height);
    }
    if (position >= 0 && duration > 0) {
      const x = timeToX(position, duration, width);
      context.strokeStyle = playhead;
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, height);
      context.stroke();
    }

    // Scientific/logarithmic ruler: conventional 1-2-5 ticks give the eye a
    // stable scale without changing or obscuring the measured raster itself.
    context.font = `10px ${fontMono}`;
    context.textAlign = "left";
    context.textBaseline = "middle";
    for (const frequency of logarithmicFrequencyTicks(data.minFrequency, data.maxFrequency)) {
      const y = frequencyToY(frequency, data.minFrequency, data.maxFrequency, height);
      const labelY = Math.min(height - 7, Math.max(7, y));
      context.fillStyle = withAlpha(muted, 0.1);
      context.fillRect(0, Math.round(y), width, 1);
      context.fillStyle = withAlpha(muted, 0.5);
      context.fillRect(0, Math.round(y), 7, 1);
      context.strokeStyle = withAlpha(panel, 0.9);
      context.lineWidth = 3;
      context.lineJoin = "round";
      context.strokeText(formatFrequency(frequency), 10, labelY);
      context.fillStyle = withAlpha(muted, 0.72);
      context.fillText(formatFrequency(frequency), 10, labelY);
    }
  }, [annotations, duration, focusedAnnotationId, position, preview, selection]);

  const eventTime = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return xToTime(event.clientX - rect.left, rect.width, duration);
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (duration <= 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const startTime = eventTime(event);
    draggingRef.current = { startX: event.clientX - rect.left, startTime, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = draggingRef.current;
    if (!drag) return;
    if (Math.abs(event.clientX - event.currentTarget.getBoundingClientRect().left - drag.startX) > 3) drag.moved = true;
    if (drag.moved) {
      const end = eventTime(event);
      setPreview({ start: Math.min(drag.startTime, end), end: Math.max(drag.startTime, end) });
    }
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = draggingRef.current;
    draggingRef.current = null;
    if (!drag) return;
    if (drag.moved) {
      const range = preview ?? { start: drag.startTime, end: eventTime(event) };
      if (range.end - range.start >= 0.05) onSelect?.(range.start, range.end);
      setPreview(null);
      return;
    }
    // Annotation overlays are deliberately non-interactive: a simple click
    // always preserves this view's primary transport affordance and leaves any
    // previously selected passage before moving the playhead.
    onClearSelection?.();
    onSeek?.(eventTime(event));
  };

  return (
    <div className="spectrogram-wrap" data-testid="spectrogram">
      <canvas
        ref={canvasRef}
        className="spectrogram-canvas"
        data-testid="spectrogram-canvas"
        data-spectrogram-state={status}
        width={900}
        height={420}
        role="slider"
        aria-label="Spectrogram selection"
        aria-busy={status === "loading"}
        aria-valuetext={duration > 0 ? `${duration.toFixed(1)} seconds` : "Loading spectrogram"}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={() => { if (draggingRef.current?.moved) setPreview(null); draggingRef.current = null; }}
      />
      {status === "loading" && <p className="muted spectrogram-status">Rendering spectrogram{progress > 0 ? ` ${Math.round(progress * 100)}%` : ""}&hellip;</p>}
      {status === "error" && <p className="muted spectrogram-status">Spectrogram unavailable.</p>}
    </div>
  );
}
