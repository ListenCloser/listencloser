"use client";

import { useEffect, useState } from "react";
import Spectrogram from "@/components/Spectrogram";
import { getDecodedAudio } from "@/lib/audio-buffer-cache";

type EvalParams = {
  mode: "baseline" | "candidate";
  run: string;
};

/**
 * Branch-only Spectrogram evaluation surface.
 *
 * Baseline renders the production Spectrogram unchanged. Candidate mode only
 * exposes ListenCloser's existing decoded PCM to the browser test; the pinned
 * WaveSurfer core + Spectrogram plugin are injected by CI, so no candidate
 * dependency enters production ownership before the decision is recorded.
 */
export default function WaveSurferSpectrogramEvaluationPage() {
  const [params, setParams] = useState<EvalParams | null>(null);

  useEffect(() => {
    const search = new URLSearchParams(window.location.search);
    const mode = search.get("mode") === "candidate" ? "candidate" : "baseline";
    const run = search.get("run") ?? "0";
    setParams({ mode, run });

    (window as any).__prepareWaveSurferSpectrogramPcm = async (
      url: string,
      cacheIdentity: string,
    ) => {
      const decoded = await getDecodedAudio(url, cacheIdentity);
      const channels = Array.from(
        { length: decoded.numberOfChannels },
        (_, index) => decoded.getChannelData(index),
      );
      return {
        channels,
        duration: decoded.duration,
        sampleRate: decoded.sampleRate,
      };
    };

    return () => {
      delete (window as any).__prepareWaveSurferSpectrogramPcm;
    };
  }, []);

  if (!params) return null;

  return (
    <main
      style={{
        minHeight: "100vh",
        padding: 24,
        background: "#161513",
        color: "#eee9df",
        display: "grid",
        gap: 16,
      }}
    >
      <h1 style={{ fontSize: 14, margin: 0 }}>
        {params.mode === "baseline" ? "Current Spectrogram" : "WaveSurfer Spectrogram candidate"}
      </h1>

      {params.mode === "baseline" ? (
        <Spectrogram
          url={`/__wavesurfer-eval/real-piano.m4a?specBaseline=${encodeURIComponent(params.run)}`}
          cacheIdentity={`wavesurfer-spec-baseline-${params.run}`}
          position={0}
        />
      ) : (
        <section data-testid="wavesurfer-spectrogram-candidate">
          <div
            id="wavesurfer-spectrogram-waveform-mount"
            aria-hidden="true"
            style={{ width: "100%", height: 1, overflow: "hidden", opacity: 0 }}
          />
          <div
            id="wavesurfer-spectrogram-mount"
            style={{ width: "100%", height: 420, background: "#1d1b18", position: "relative" }}
          />
        </section>
      )}
    </main>
  );
}
