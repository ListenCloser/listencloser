"use client";

import { useEffect, useState } from "react";
import Waveform from "@/components/Waveform";
import { getDecodedAudio } from "@/lib/audio-buffer-cache";

/**
 * Branch-only WaveSurfer evaluation surface.
 *
 * This intentionally renders the production Waveform unchanged beside an
 * empty candidate mount point. The evaluation Playwright job injects the
 * pinned WaveSurfer browser bundles at runtime, so no candidate dependency or
 * implementation leaks into production package ownership before a decision.
 */
export default function WaveSurferEvaluationPage() {
  const [audioUrl, setAudioUrl] = useState("");

  useEffect(() => {
    const run = new URLSearchParams(window.location.search).get("run") ?? "0";
    setAudioUrl(`/__wavesurfer-eval/real-piano.m4a?baseline=${encodeURIComponent(run)}`);

    // Second characterization mode: keep ListenCloser's existing shared
    // fetch/decode cache as the source owner and hand WaveSurfer a compact peak
    // array. The optional identity lets the harness distinguish a true cold
    // decode from ordinary same-Version cache reuse.
    (window as any).__prepareWaveSurferPeaks = async (url: string, cacheIdentity?: string) => {
      const decoded = await getDecodedAudio(url, cacheIdentity);
      const channel = decoded.getChannelData(0);
      const pointCount = Math.max(1024, Math.min(4096, Math.floor(decoded.duration * 48)));
      const per = Math.max(1, Math.floor(channel.length / pointCount));
      const peaks = new Float32Array(pointCount);

      for (let index = 0; index < pointCount; index += 1) {
        let strongest = 0;
        let strongestAbs = 0;
        const start = index * per;
        const end = Math.min(channel.length, start + per);
        for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
          const sample = channel[sampleIndex] ?? 0;
          const absolute = Math.abs(sample);
          if (absolute > strongestAbs) {
            strongest = sample;
            strongestAbs = absolute;
          }
        }
        peaks[index] = strongest;
      }

      return {
        duration: decoded.duration,
        peaks: [peaks],
        peakPoints: pointCount,
      };
    };

    return () => {
      delete (window as any).__prepareWaveSurferPeaks;
    };
  }, []);

  return (
    <main
      style={{
        minHeight: "100vh",
        padding: 24,
        background: "#161513",
        color: "#eee9df",
        display: "grid",
        gap: 28,
      }}
    >
      <section data-testid="wavesurfer-eval-baseline">
        <h1 style={{ fontSize: 14, margin: "0 0 10px" }}>Current Waveform</h1>
        {audioUrl ? <Waveform url={audioUrl} position={0} /> : null}
      </section>

      <section data-testid="wavesurfer-eval-candidate">
        <h2 style={{ fontSize: 14, margin: "0 0 10px" }}>WaveSurfer candidate</h2>
        <div
          id="wavesurfer-eval-candidate-mount"
          style={{ width: "100%", height: 220, background: "#1d1b18" }}
        />
      </section>
    </main>
  );
}
