"use client";

import { useEffect, useRef } from "react";

/**
 * #1143 experiment-only signal primitive.
 *
 * The original experiment borrowed the dependency-free animated-canvas idea
 * from Ruixen UI. v5 also adopts the polished bar-density, HiDPI resize, and
 * edge-fade conventions used by ElevenLabs UI's MIT waveform components.
 * This remains decorative landing geometry: it does not imply measured audio.
 */
export default function LiveSignalField({
  className = "",
  height = 120,
  barWidth = 2,
  barGap = 3,
}: {
  className?: string;
  height?: number;
  barWidth?: number;
  barGap?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    let frame = 0;
    let width = 0;
    let dpr = window.devicePixelRatio || 1;

    const resize = () => {
      width = Math.max(1, wrap.getBoundingClientRect().width);
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    };

    const draw = (now: number) => {
      const center = height / 2;
      const step = barWidth + barGap;
      const count = Math.ceil(width / step) + 1;
      const time = reduceMotion ? 2.15 : now / 1000;
      const color = getComputedStyle(canvas).color || "#d9ddd5";

      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);
      context.fillStyle = color;

      for (let index = 0; index < count; index += 1) {
        const x = index * step;
        const position = index / Math.max(count - 1, 1);
        const phrase = 0.38 + Math.sin(position * Math.PI * 3.4 - time * 0.68) * 0.17;
        const movement = Math.sin(position * Math.PI * 8.1 + time * 1.12) * 0.12;
        const detail = Math.sin(position * Math.PI * 18.4 - time * 1.72) * 0.055;
        const breath = Math.sin(position * Math.PI) * 0.12;
        const amplitude = Math.max(0.07, Math.min(0.82, phrase + movement + detail + breath));
        const barHeight = Math.max(5, amplitude * height * 0.84);
        const y = center - barHeight / 2;

        context.globalAlpha = 0.36 + amplitude * 0.58;
        context.beginPath();
        context.roundRect(x, y, barWidth, barHeight, Math.min(1, barWidth / 2));
        context.fill();
      }

      // Adopt the edge treatment used by mature open waveform components:
      // preserve the signal in the middle and let the geometry disappear at
      // the viewport boundary instead of ending on two hard vertical edges.
      const fadeWidth = Math.min(92, width * 0.14);
      if (fadeWidth > 0 && width > 0) {
        const gradient = context.createLinearGradient(0, 0, width, 0);
        const fade = fadeWidth / width;
        gradient.addColorStop(0, "rgba(255,255,255,1)");
        gradient.addColorStop(fade, "rgba(255,255,255,0)");
        gradient.addColorStop(1 - fade, "rgba(255,255,255,0)");
        gradient.addColorStop(1, "rgba(255,255,255,1)");
        context.globalCompositeOperation = "destination-out";
        context.globalAlpha = 1;
        context.fillStyle = gradient;
        context.fillRect(0, 0, width, height);
        context.globalCompositeOperation = "source-over";
      }

      context.globalAlpha = 1;
      if (!reduceMotion) frame = requestAnimationFrame(draw);
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(wrap);
    draw(performance.now());

    return () => {
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [barGap, barWidth, height]);

  return (
    <div ref={wrapRef} className={`live-signal-field ${className}`} aria-hidden="true">
      <canvas ref={canvasRef} />
    </div>
  );
}
