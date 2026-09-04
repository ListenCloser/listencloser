"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import { PITCH_CONTOUR_READY_EVENT } from "@/lib/pitch-contour-api";
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

function provenanceLabel(data: PitchContourData): string {
  const engine = `${data.engine.name} ${data.engine.version} · ${data.engine.method}`;
  const hopMs = Math.round(data.preprocessing.hop_seconds * 1000);
  return `${engine} · ${hopMs} ms frames · ${data.engine.license}`;
}

export default function PitchContour({ active }: { active: boolean }) {
  const { workspace } = useWorkspace();
  const { transport, seek, play } = useTransport();
  const [data, setData] = useState<PitchContourData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async (force = false) => {
    const workId = workspace.activeWorkId;
    if (!workId) {
      setData(null);
      return;
    }
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      if (force) clearWorkDataCache();
      const bundle = await getWorkBundle(workId);
      const matches = bundle.artifacts
        .filter((item) => item.latest_version && isPitchContourMetadata(item.latest_version.metadata))
        .sort((a, b) => String(b.latest_version?.created_at ?? "").localeCompare(String(a.latest_version?.created_at ?? "")));
      const item = matches[0];
      if (!item?.signed_url) {
        if (id === requestId.current) setData(null);
        return;
      }
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
    void load(false);
  }, [load]);

  useEffect(() => {
    const onReady = (event: Event) => {
      const detail = (event as CustomEvent<{ workId?: string }>).detail;
      if (!detail?.workId || detail.workId === workspace.activeWorkId) void load(true);
    };
    window.addEventListener(PITCH_CONTOUR_READY_EVENT, onReady);
    return () => window.removeEventListener(PITCH_CONTOUR_READY_EVENT, onReady);
  }, [load, workspace.activeWorkId]);

  const voicedFrames = useMemo(
    () => data?.frames.filter((frame) => frame.voiced && frame.pitch_cents !== null) ?? [],
    [data],
  );
  const plot = useMemo(() => {
    if (!data || voicedFrames.length === 0) return null;
    const width = 1000;
    const height = 280;
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

  if (loading && !data) {
    return <div className="representation-body"><p className="muted">Loading pitch contour…</p></div>;
  }
  if (error) {
    return <div className="representation-body"><p role="alert">{error}</p></div>;
  }
  if (!data || !plot) {
    return (
      <div className="representation-body">
        <div style={{ maxWidth: 560, display: "grid", gap: "var(--s-3)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <strong>Pitch contour</strong>
            <span style={{ border: "1px solid currentColor", borderRadius: 999, padding: "2px 7px", fontSize: "var(--fs-xs)" }}>Experimental</span>
          </div>
          <p className="muted" style={{ margin: 0 }}>
            Generate this opt-in view from Processing. It keeps continuous F0 in Hz/cents rather than converting expressive pitch into MIDI notes.
          </p>
        </div>
      </div>
    );
  }

  const playheadX = Math.max(0, Math.min(plot.width, (transport.position / plot.duration) * plot.width));
  const voicedShare = data.frames.length ? Math.round((voicedFrames.length / data.frames.length) * 100) : 0;

  return (
    <div className="representation-body">
      <div style={{ display: "grid", gap: "var(--s-3)", minHeight: 320 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--s-3)", alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ display: "grid", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <strong>Pitch contour</strong>
              <span style={{ border: "1px solid currentColor", borderRadius: 999, padding: "2px 7px", fontSize: "var(--fs-xs)" }}>Experimental</span>
            </div>
            <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>{provenanceLabel(data)}</span>
          </div>
          <button type="button" className="btn btn-sm" onClick={play} disabled={transport.isPlaying}>
            {transport.isPlaying ? "Playing" : "Hear"}
          </button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "42px minmax(0, 1fr)", gap: 8, alignItems: "stretch" }}>
          <div className="muted" aria-hidden="true" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", fontSize: "10px", textAlign: "right" }}>
            <span>{noteLabel(plot.maxCents)}</span>
            <span>{noteLabel(plot.minCents)}</span>
          </div>
          <svg
            viewBox={`0 0 ${plot.width} ${plot.height}`}
            preserveAspectRatio="none"
            role="img"
            aria-label="Continuous pitch over performance time. Click to seek."
            style={{ width: "100%", height: 280, border: "1px solid var(--border-subtle)", borderRadius: 8, cursor: "crosshair", overflow: "visible" }}
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1)));
              seek(ratio * plot.duration);
            }}
          >
            <path d={plot.path} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            {active && (
              <line x1={playheadX} x2={playheadX} y1="0" y2={plot.height} stroke="currentColor" strokeWidth="1" opacity="0.65" vectorEffect="non-scaling-stroke" />
            )}
          </svg>
        </div>

        <div className="muted" style={{ display: "flex", gap: "var(--s-3)", flexWrap: "wrap", fontSize: "var(--fs-xs)", lineHeight: 1.4 }}>
          <span>{voicedShare}% frames voiced</span>
          <span>Source Version {data.source_audio_version_id.slice(0, 8)}…</span>
          <span>{data.preprocessing.pitch_cents_reference}</span>
        </div>
        <p className="muted" style={{ margin: 0, fontSize: "var(--fs-xs)", lineHeight: 1.45 }}>
          Intended for voice and expressive monophonic material. Polyphony, noisy mixtures, and strong overtones can produce octave or subharmonic errors. Click the curve to seek; playback uses the shared original-audio transport.
        </p>
      </div>
    </div>
  );
}
