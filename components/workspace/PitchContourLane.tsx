"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getWorkBundle } from "@/lib/api-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

type PitchFrame = {
  frame: number;
  time_seconds: number;
  pitch_hz: number | null;
  pitch_cents: number | null;
  voiced: boolean;
  voiced_probability: number | null;
};

type PitchContourData = {
  schema_version: number;
  representation_type: "pitch_contour";
  status: "experimental";
  source_audio_version_id: string;
  engine: {
    name: string;
    version: string;
    method: string;
    model: string | null;
    license: string;
  };
  preprocessing: {
    sample_rate_hz: number;
    hop_seconds: number;
    fmin_hz: number;
    fmax_hz: number;
    pitch_cents_reference: string;
  };
  frames: PitchFrame[];
};

function isPitchContourMetadata(metadata: Record<string, unknown> | null | undefined): boolean {
  return metadata?.representation_type === "pitch_contour";
}

function noteLabel(cents: number): string {
  const midi = Math.round(cents / 100);
  const names = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];
  const name = names[((midi % 12) + 12) % 12];
  const octave = Math.floor(midi / 12) - 1;
  return `${name}${octave}`;
}

export default function PitchContourLane({ onClose }: { onClose: () => void }) {
  const { workspace } = useWorkspace();
  const { transport, seek, play } = useTransport();
  const [data, setData] = useState<PitchContourData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const workId = workspace.activeWorkId;
    if (!workId) {
      setData(null);
      setLoading(false);
      return;
    }
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const bundle = await getWorkBundle(workId);
      const item = bundle.artifacts
        .filter((candidate) => candidate.latest_version && isPitchContourMetadata(candidate.latest_version.metadata))
        .sort((a, b) => String(b.latest_version?.created_at ?? "").localeCompare(String(a.latest_version?.created_at ?? "")))[0];
      if (!item?.signed_url) throw new Error("Pitch contour result is not ready.");
      const response = await fetch(item.signed_url);
      if (!response.ok) throw new Error(`Pitch contour data failed to load (${response.status})`);
      const payload = await response.json() as PitchContourData;
      if (payload.representation_type !== "pitch_contour" || !Array.isArray(payload.frames)) {
        throw new Error("Pitch contour artifact has an invalid schema");
      }
      if (id === requestId.current) setData(payload);
    } catch (cause) {
      if (id === requestId.current) {
        setData(null);
        setError(cause instanceof Error ? cause.message : "Pitch contour could not be loaded");
      }
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [workspace.activeWorkId]);

  useEffect(() => {
    void load();
  }, [load]);

  const voicedFrames = useMemo(
    () => data?.frames.filter((frame) => frame.voiced && frame.pitch_cents !== null) ?? [],
    [data],
  );
  const plot = useMemo(() => {
    if (!data || voicedFrames.length === 0) return null;
    const width = 1000;
    const height = 180;
    const values = voicedFrames.map((frame) => frame.pitch_cents as number);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const span = Math.max(200, rawMax - rawMin);
    const minCents = rawMin - span * 0.08;
    const maxCents = rawMax + span * 0.08;
    const duration = Math.max(
      transport.duration,
      data.frames[data.frames.length - 1]?.time_seconds ?? 0,
      0.001,
    );
    let path = "";
    let previousFrame = -2;
    for (const frame of data.frames) {
      if (!frame.voiced || frame.pitch_cents === null) {
        previousFrame = -2;
        continue;
      }
      const x = (frame.time_seconds / duration) * width;
      const y = height - ((frame.pitch_cents - minCents) / (maxCents - minCents)) * height;
      path += `${frame.frame === previousFrame + 1 ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)} `;
      previousFrame = frame.frame;
    }
    return { width, height, minCents, maxCents, duration, path };
  }, [data, transport.duration, voicedFrames]);

  const voicedShare = data?.frames.length
    ? Math.round((voicedFrames.length / data.frames.length) * 100)
    : 0;
  const playheadX = plot
    ? Math.max(0, Math.min(plot.width, (transport.position / plot.duration) * plot.width))
    : 0;

  return (
    <section
      data-testid="pitch-contour-lane"
      aria-label="Pitch contour"
      style={{
        borderBottom: "1px solid var(--border-subtle)",
        padding: "var(--s-3)",
        display: "grid",
        gap: "var(--s-3)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--s-3)", flexWrap: "wrap" }}>
        <div style={{ display: "grid", gap: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong>Pitch contour</strong>
            <span style={{ border: "1px solid currentColor", borderRadius: 999, padding: "2px 7px", fontSize: "var(--fs-xs)" }}>
              Experimental interpretation
            </span>
          </div>
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
            Continuous monophonic F0 aligned to the recording.
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="btn btn-sm" onClick={play} disabled={transport.isPlaying || loading || Boolean(error)}>
            {transport.isPlaying ? "Playing" : "Hear"}
          </button>
          <button type="button" className="btn btn-sm" onClick={onClose}>Hide</button>
        </div>
      </div>

      {loading && <p className="muted" role="status" style={{ margin: 0 }}>Loading pitch contour…</p>}
      {error && <p role="alert" style={{ margin: 0 }}>{error}</p>}
      {!loading && !error && data && !plot && (
        <p className="muted" style={{ margin: 0 }}>No voiced pitch frames were returned for this recording.</p>
      )}

      {data && plot && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "42px minmax(0, 1fr)", gap: 8, alignItems: "stretch" }}>
            <div className="muted" aria-hidden="true" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", fontSize: 10, textAlign: "right" }}>
              <span>{noteLabel(plot.maxCents)}</span>
              <span>{noteLabel(plot.minCents)}</span>
            </div>
            <svg
              data-testid="pitch-contour-plot"
              viewBox={`0 0 ${plot.width} ${plot.height}`}
              preserveAspectRatio="none"
              role="img"
              aria-label="Continuous pitch over performance time. Click to seek."
              style={{ width: "100%", height: plot.height, border: "1px solid var(--border-subtle)", borderRadius: 8, cursor: "crosshair", overflow: "visible" }}
              onClick={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1)));
                seek(ratio * plot.duration);
              }}
            >
              <path d={plot.path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
              <line x1={playheadX} x2={playheadX} y1="0" y2={plot.height} stroke="currentColor" strokeWidth="1" opacity="0.65" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>

          <div className="muted" style={{ display: "flex", gap: "var(--s-3)", flexWrap: "wrap", fontSize: "var(--fs-xs)" }}>
            <span>{voicedShare}% frames marked voiced by pYIN</span>
            <span>{data.preprocessing.pitch_cents_reference}</span>
          </div>

          <p className="muted" style={{ margin: 0, fontSize: "var(--fs-xs)", lineHeight: 1.45 }}>
            Intended for voice and expressive monophonic material. Polyphony, noisy mixtures, and strong overtones can produce octave or subharmonic errors.
          </p>

          <details>
            <summary style={{ cursor: "pointer", fontSize: "var(--fs-xs)" }}>Details</summary>
            <div className="muted" style={{ display: "grid", gap: 4, paddingTop: 6, fontSize: "var(--fs-xs)", lineHeight: 1.45 }}>
              <span>Method: {data.engine.name} {data.engine.version} · {data.engine.method}</span>
              <span>Model/checkpoint: {data.engine.model ?? "none"}</span>
              <span>License: {data.engine.license}</span>
              <span>Source Version: {data.source_audio_version_id}</span>
              <span>Preprocessing: {data.preprocessing.sample_rate_hz} Hz · {Math.round(data.preprocessing.hop_seconds * 1000)} ms hop · {data.preprocessing.fmin_hz}–{data.preprocessing.fmax_hz} Hz</span>
              <span>Voiced probability is pYIN-specific evidence, not generic correctness confidence.</span>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
