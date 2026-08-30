"use client";

import { useEffect, useState } from "react";
import Waveform from "@/components/Waveform";

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
