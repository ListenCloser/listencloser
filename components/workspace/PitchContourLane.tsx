"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import {
  startPitchContourWorkflow,
  type PitchContourEngine,
} from "@/lib/pitch-contour-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

type PitchFrame = {
  frame: number;
  time_seconds: number;
  pitch_hz: number | null;
  pitch_cents: number | null;
  voiced: boolean;
  voiced_probability: number | null;
  method_score?: number | null;
  method_score_kind?: "periodicity" | "voicing_confidence" | null;
};

type PitchContourData = {
  schema_version: number;
  representation_type: "pitch_contour";
  status: "experimental";
  source_audio_version_id: string;
  requested_engine?: PitchContourEngine;
  engine: {
    name: string;
    version: string;
    method: string;
    model: string | null;
    model_sha256?: string | null;
    license: string;
  };
  preprocessing: {
    sample_rate_hz: number;
    hop_seconds: number;
    fmin_hz: number;
    fmax_hz: number;
    pitch_cents_reference: string;
    voicing_rule?: string;
  };
  frames: PitchFrame[];
};

type PitchCandidate = {
  engine: PitchContourEngine;
  signedUrl: string;
  createdAt: string;
};

const ENGINE_ORDER: PitchContourEngine[] = ["pyin", "pesto", "torchcrepe"];

function isPitchContourMetadata(metadata: Record<string, unknown> | null | undefined): boolean {
  return metadata?.representation_type === "pitch_contour";
}

function normalizeEngine(value: unknown): PitchContourEngine | null {
  return value === "pyin" || value === "pesto" || value === "torchcrepe" ? value : null;
}

function engineFromMetadata(
  metadata: Record<string, unknown> | null | undefined,
): PitchContourEngine {
  const requested = normalizeEngine(metadata?.requested_engine);
  if (requested) return requested;
  const engine = metadata?.engine;
  if (engine && typeof engine === "object" && "name" in engine) {
    const name = normalizeEngine((engine as { name?: unknown }).name);
    if (name) return name;
  }
  return "pyin";
}

function engineLabel(engine: PitchContourEngine): string {
  if (engine === "pyin") return "pYIN";
  if (engine === "pesto") return "PESTO";
  return "torchcrepe";
}

function noteLabel(cents: number): string {
  const midi = Math.round(cents / 100);
  const names = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];
  const name = names[((midi % 12) + 12) % 12];
  const octave = Math.floor(midi / 12) - 1;
  return `${name}${octave}`;
}

function scoreSemantics(data: PitchContourData): string {
  if (data.requested_engine === "torchcrepe" || data.engine.name === "torchcrepe") {
    return "Periodicity is CREPE-specific voicing evidence, not generic correctness confidence.";
  }
  if (data.requested_engine === "pesto" || data.engine.name === "pesto") {
    return "Voicing confidence is PESTO-specific evidence, not generic correctness confidence.";
  }
  return "Voiced probability is pYIN-specific evidence, not generic correctness confidence.";
}

export default function PitchContourLane({ onClose }: { onClose: () => void }) {
  const { workspace } = useWorkspace();
  const { transport, seek, play } = useTransport();
  const [data, setData] = useState<PitchContourData | null>(null);
  const [candidates, setCandidates] = useState<PitchCandidate[]>([]);
  const [selectedEngine, setSelectedEngine] = useState<PitchContourEngine>("pyin");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [sourceVersionId, setSourceVersionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatingEngine, setGeneratingEngine] = useState<PitchContourEngine | null>(null);
  const requestId = useRef(0);
  const selectedEngineRef = useRef<PitchContourEngine>("pyin");

  const fetchCandidate = useCallback(async (candidate: PitchCandidate, sourceId: string) => {
    const response = await fetch(candidate.signedUrl);
    if (!response.ok) throw new Error(`Pitch contour data failed to load (${response.status})`);
    const payload = await response.json() as PitchContourData;
    if (payload.representation_type !== "pitch_contour" || !Array.isArray(payload.frames)) {
      throw new Error("Pitch contour artifact has an invalid schema");
    }
    if (payload.status !== "experimental" || payload.source_audio_version_id !== sourceId) {
      throw new Error("Pitch contour artifact does not match the active source Version");
    }
    selectedEngineRef.current = candidate.engine;
    setSelectedEngine(candidate.engine);
    setData(payload);
  }, []);

  const load = useCallback(async (
    preferredEngine?: PitchContourEngine,
    requirePreferred = false,
  ): Promise<boolean> => {
    const workId = workspace.activeWorkId;
    if (!workId) {
      setData(null);
      setLoading(false);
      return false;
    }
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const bundle = await getWorkBundle(workId);
      if (id !== requestId.current) return false;
      setProjectId(bundle.work.project_id);
      const source = bundle.artifacts.find(
        (candidate) => candidate.artifact.kind === "audio_original" && candidate.latest_version,
      );
      const sourceId = source?.latest_version?.id ?? null;
      setSourceVersionId(sourceId);
      if (!sourceId) throw new Error("Pitch contour source audio is unavailable.");

      const matching = bundle.artifacts
        .filter((candidate) => (
          candidate.latest_version
          && candidate.signed_url
          && isPitchContourMetadata(candidate.latest_version.metadata)
          && candidate.latest_version.metadata?.source_audio_version_id === sourceId
        ))
        .map((candidate): PitchCandidate => ({
          engine: engineFromMetadata(candidate.latest_version?.metadata),
          signedUrl: candidate.signed_url as string,
          createdAt: String(candidate.latest_version?.created_at ?? ""),
        }))
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

      const unique = matching.filter(
        (candidate, index) => matching.findIndex((item) => item.engine === candidate.engine) === index,
      );
      setCandidates(unique);
      if (unique.length === 0) throw new Error("Pitch contour result is not ready.");

      const desiredEngine = preferredEngine ?? selectedEngineRef.current;
      const desired = unique.find((candidate) => candidate.engine === desiredEngine);
      if (requirePreferred && preferredEngine && !desired) return false;
      const candidate = desired ?? unique[0];
      await fetchCandidate(candidate, sourceId);
      return candidate.engine === preferredEngine || preferredEngine === undefined;
    } catch (cause) {
      if (id === requestId.current) {
        setData(null);
        setError(cause instanceof Error ? cause.message : "Pitch contour could not be loaded");
      }
      return false;
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [fetchCandidate, workspace.activeWorkId]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectInterpretation = useCallback(async (engine: PitchContourEngine) => {
    const existing = candidates.find((candidate) => candidate.engine === engine);
    if (!existing || !sourceVersionId) return;
    setLoading(true);
    setError(null);
    try {
      await fetchCandidate(existing, sourceVersionId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Pitch contour could not be loaded");
    } finally {
      setLoading(false);
    }
  }, [candidates, fetchCandidate, sourceVersionId]);

  const generateInterpretation = useCallback(async (engine: PitchContourEngine) => {
    if (!sourceVersionId || !projectId || generatingEngine) return;
    const existing = candidates.find((candidate) => candidate.engine === engine);
    if (existing) {
      await selectInterpretation(engine);
      return;
    }

    setGeneratingEngine(engine);
    setError(null);
    try {
      const jobId = await startPitchContourWorkflow(sourceVersionId, projectId, engine);
      await waitForJob(jobId, () => undefined);
      clearWorkDataCache();
      const loaded = await load(engine, true);
      if (!loaded) throw new Error(`${engineLabel(engine)} result was not published by the completed job.`);
    } catch (cause) {
      if (cause instanceof JobObservationError) {
        clearWorkDataCache();
        const loaded = await load(engine, true);
        if (!loaded) setError(cause.message);
      } else {
        setError(cause instanceof Error ? cause.message : `${engineLabel(engine)} processing failed`);
      }
    } finally {
      setGeneratingEngine(null);
    }
  }, [
    candidates,
    generatingEngine,
    load,
    projectId,
    selectInterpretation,
    sourceVersionId,
  ]);

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
              Experimental
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
            <span>{voicedShare}% frames marked voiced</span>
            <span>{data.preprocessing.pitch_cents_reference}</span>
          </div>

          <p className="muted" style={{ margin: 0, fontSize: "var(--fs-xs)", lineHeight: 1.45 }}>
            Intended for voice and expressive monophonic material. Polyphony, noisy mixtures, and strong overtones can produce octave or subharmonic errors.
          </p>

          <details>
            <summary style={{ cursor: "pointer", fontSize: "var(--fs-xs)" }}>Details</summary>
            <div className="muted" style={{ display: "grid", gap: 6, paddingTop: 6, fontSize: "var(--fs-xs)", lineHeight: 1.45 }}>
              <span>Interpretation: {engineLabel(selectedEngine)}</span>
              <span>Method: {data.engine.name} {data.engine.version} · {data.engine.method}</span>
              <span>Model/checkpoint: {data.engine.model ?? "none"}</span>
              {data.engine.model_sha256 && <span>Model SHA-256: {data.engine.model_sha256}</span>}
              <span>License: {data.engine.license}</span>
              <span>Source Version: {data.source_audio_version_id}</span>
              <span>Preprocessing: {data.preprocessing.sample_rate_hz} Hz · {Math.round(data.preprocessing.hop_seconds * 1000)} ms hop · {data.preprocessing.fmin_hz}–{data.preprocessing.fmax_hz} Hz</span>
              <span>{scoreSemantics(data)}</span>
              <div style={{ display: "grid", gap: 4, paddingTop: 4 }}>
                <strong style={{ fontWeight: 600 }}>Try another interpretation</strong>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {ENGINE_ORDER.map((engine) => {
                    const available = candidates.some((candidate) => candidate.engine === engine);
                    const active = selectedEngine === engine;
                    const generating = generatingEngine === engine;
                    return (
                      <button
                        key={engine}
                        type="button"
                        className="btn btn-sm"
                        disabled={active || generatingEngine !== null || loading}
                        aria-pressed={active}
                        onClick={() => void generateInterpretation(engine)}
                      >
                        {active
                          ? `${engineLabel(engine)} · Shown`
                          : generating
                            ? `Generating ${engineLabel(engine)}…`
                            : available
                              ? `Show ${engineLabel(engine)}`
                              : `Generate ${engineLabel(engine)}`}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
