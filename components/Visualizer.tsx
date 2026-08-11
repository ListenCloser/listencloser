"use client";

import { useEffect, useRef } from "react";

type Props = {
  audioRef: React.RefObject<HTMLAudioElement | null>;
};

type AudioGraph = { ctx: AudioContext; source: MediaElementAudioSourceNode };
const graphCache = new WeakMap<HTMLAudioElement, AudioGraph>();

export default function Visualizer({ audioRef }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const audio = audioRef.current;
    if (!canvas || !audio) return;
    const canvasCtx = canvas.getContext("2d");
    if (!canvasCtx) return;

    let cancelled = false;

    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue("--accent").trim() || "#bd513a";
    const bg = "#292825";

    // Browsers create the AudioContext suspended until a user gesture.
    // If it stays suspended, cross-origin audio routed through Web Audio is
    // silenced. Resume it on play so gallery/saved playback actually sounds.
    const resume = () => {
      if (ctxRef.current?.state === "suspended") ctxRef.current.resume().catch(() => {});
    };

    async function setup() {
      const audioEl = audio;
      if (!audioEl) return;
      const AudioCtx =
        window.AudioContext ||
        (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      // createMediaElementSource throws if called twice for the same element,
      // so reuse the AudioContext + source node once an element has been routed.
      let graph = graphCache.get(audioEl);
      if (!graph) {
        const ctx: AudioContext = new AudioCtx();
        const source = ctx.createMediaElementSource(audioEl);
        graph = { ctx, source };
        graphCache.set(audioEl, graph);
      }
      const { ctx, source } = graph;
      ctxRef.current = ctx;
      sourceRef.current = source;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      analyser.connect(ctx.destination);

      audioEl.addEventListener("play", resume);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const draw = () => {
        if (cancelled) return;
        rafRef.current = requestAnimationFrame(draw);
        analyser.getByteTimeDomainData(dataArray);

        const w = canvas!.width;
        const h = canvas!.height;
        canvasCtx!.fillStyle = bg;
        canvasCtx!.fillRect(0, 0, w, h);

        // One calm, high-contrast listening trace. Frequency bars made this
        // representation compete with the score rather than support playback.
        canvasCtx!.lineWidth = 1.5;
        canvasCtx!.strokeStyle = "rgba(255,253,249,.9)";
        canvasCtx!.beginPath();
        const sliceWidth = w / bufferLength;
        let x = 0;
        for (let i = 0; i < bufferLength; i++) {
          const v = dataArray[i] / 128.0;
          const y = (v * h) / 2;
          if (i === 0) canvasCtx!.moveTo(x, y);
          else canvasCtx!.lineTo(x, y);
          x += sliceWidth;
        }
        canvasCtx!.stroke();
        canvasCtx!.fillStyle = accent;
        canvasCtx!.fillRect(0, h / 2 - 1, w, 2);
      };
      draw();
    }

    setup();

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
      // The AudioContext + source are cached and reused per element, so tear
      // down only this effect's connections; don't close the shared context.
      sourceRef.current?.disconnect();
      audio.removeEventListener("play", resume);
    };
  }, [audioRef]);

  return <canvas ref={canvasRef} className="visualizer" width={760} height={180} />;
}
