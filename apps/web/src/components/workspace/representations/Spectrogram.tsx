"use client";

import { useEffect, useRef, useState } from "react";
import { canvasMeasurementFont } from "@/lib/canvas-typography";
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
type Rgb = readonly [number, number, number];
type ColorStop = readonly [number, Rgb];

const SPECTROGRAM_HEIGHT = 420;
const FALLBACK_WIDTH = 900;

const SPECTROGRAM_STOPS: readonly ColorStop[] = [
  [0, [7, 9, 9]],
  [0.28, [19, 24, 25]],
  [0.56, [49, 59, 61]],
  [0.8, [112, 122, 121]],
  [1, [225, 224, 213]],
] as const;

function interpolateColor(value: number): Rgb {
  const normalized = Math.max(0, Math.min(1, value));
  let upperIndex = 1;
  while (upperIndex < SPECTROGRAM_STOPS.length - 1 && normalized > SPECTROGRAM_STOPS[upperIndex][0]) {
    upperIndex += 1;
  }
  const [startAt, start] = SPECTROGRAM_STOPS[upperIndex - 1];
  const [endAt, end] = SPECTROGRAM_STOPS[upperIndex];
  const mix = endAt > startAt ? (normalized - startAt) / (endAt - startAt) : 0;
  return [
    Math.round(start[0] + (end[0] - start[0]) * mix),
    Math.round(start[1] + (end[1] - start[1]) * mix),
    Math.round(start[2] + (end[2] - start[2]) * mix),
  ];
}

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
    let cancelled = false;
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
    const panel = styles.getPropertyValue("--panel").trim() || "#0b0d0c";
    const muted = styles.getPropertyValue("--muted").trim() || "#737a72";
    const accent = styles.getPropertyValue("--accent").trim() || "#dff45a";
    const playhead = styles.getPropertyValue("--score-playback").trim() || "#ff745d";
    const rhythm = styles.getPropertyValue("--color-rhythm").trim() || "#929b96";
    const harmony = styles.getPropertyValue("--color-harmony").trim() || "#819b9b";
    const theory = styles.getPropertyValue("--color-theory").trim() || "#819b9b";
    const width = canvasWidth;
    const height = SPECTROGRAM_HEIGHT;

    // Field UI and waveform-playlist both keep CSS geometry separate from the
    // backing store. Draw in CSS pixels after scaling the canvas for the actual
    // device pixel ratio so FFT content and measurement labels stay sharp.
    context.resetTransform();
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.scale(devicePixelRatio, devicePixelRatio);
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
        const normalized = Math.max(0, Math.min(1, strength / 255));
        const lifted = Math.pow(normalized, 0.68);
        const [red, green, blue] = interpolateColor(lifted);
        image.data[index] = red;
        image.data[index + 1] = green;
        image.data[index + 2] = blue;
        image.data[index + 3] = 255;
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
      const rangeWidth = Math.max(1, x2 - x1);
      context.fillStyle = withAlpha(color, focused ? 0.075 : 0.018);
      context.fillRect(x1, 0, rangeWidth, height);
      context.fillStyle = withAlpha(color, focused ? 0.72 : 0.38);
      context.fillRect(x1, 0, rangeWidth, focused ? 2 : 1);
      if (focused) {
        context.strokeStyle = withAlpha(color, 0.34);
        context.lineWidth = 1;
        context.strokeRect(x1 + 0.5, 0.5, Math.max(1, rangeWidth - 1), height - 1);
      }
    }

    const range = preview ?? selection?.timeRange;
    if (range) {
      const x1 = timeToX(range.start, duration, width);
      const x2 = timeToX(range.end, duration, width);
      const rangeWidth = Math.max(1, x2 - x1);
      context.fillStyle = withAlpha(accent, 0.065);
      context.fillRect(x1, 0, rangeWidth, height);
      context.strokeStyle = withAlpha(accent, 0.46);
      context.lineWidth = 0.75;
      context.strokeRect(x1 + 0.5, 0.5, Math.max(1, rangeWidth - 1), height - 1);
    }
    if (position >= 0 && duration > 0) {
      const x = timeToX(position, duration, width);
      context.strokeStyle = withAlpha(playhead, 0.72);
      context.lineWidth = 0.75;
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, height);
      context.stroke();
      context.fillStyle = withAlpha(playhead, 0.82);
      context.fillRect(x - 1.5, 0, 3, 3);
    }

    context.font = canvasMeasurementFont(styles);
    context.textAlign = "left";
    context.textBaseline = "middle";
    for (const frequency of logarithmicFrequencyTicks(data.minFrequency, data.maxFrequency)) {
      const y = frequencyToY(frequency, data.minFrequency, data.maxFrequency, height);
      const labelY = Math.min(height - 8, Math.max(8, y));
      const label = formatFrequency(frequency);
      const labelWidth = context.measureText(label).width;
      context.fillStyle = "rgba(7, 9, 9, 0.74)";
      context.fillRect(5, labelY - 7, labelWidth + 9, 14);
      context.fillStyle = withAlpha(muted, 0.12);
      context.fillRect(0, Math.round(y), width, 1);
      context.fillStyle = withAlpha(muted, 0.62);
      context.fillRect(0, Math.round(y), 5, 1);
      context.fillStyle = "rgba(222, 224, 216, 0.72)";
      context.fillText(label, 9, labelY);
    }
  }, [
    annotations,
    canvasWidth,
    devicePixelRatio,
    duration,
    focusedAnnotationId,
    position,
    preview,
    selection,
  ]);

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
        width={Math.round(canvasWidth * devicePixelRatio)}
        height={Math.round(SPECTROGRAM_HEIGHT * devicePixelRatio)}
        style={{ width: "100%", height: SPECTROGRAM_HEIGHT }}
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
