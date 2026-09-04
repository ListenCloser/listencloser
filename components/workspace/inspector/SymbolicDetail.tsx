"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import AddAnalysis from "@/components/workspace/AddAnalysis";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import { isInspectorExposed } from "@/lib/inspector/capabilities";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import { useWorkspace } from "@/lib/stores/workspace";
import {
  fetchSymbolicDetailReport,
  startSymbolicDetailWorkflow,
  type SymbolicDetailReport,
} from "@/lib/symbolic-detail-client";

const ACTIVE_JOB_STAGES = new Set(["queued", "claimed", "running"]);

function sourceAndReportState(
  bundle: Awaited<ReturnType<typeof getWorkBundle>>,
  preferredVersionId: string | null,
) {
  const midiArtifacts = bundle.artifacts.filter((item) => (
    (item.artifact.kind === "midi_performance" || item.artifact.kind === "midi_corrected")
    && item.latest_version
    && item.signed_url
  ));
  const source = midiArtifacts.find((item) => item.latest_version?.id === preferredVersionId)
    ?? midiArtifacts.find((item) => item.artifact.kind === "midi_corrected")
    ?? midiArtifacts.find((item) => item.artifact.kind === "midi_performance");
  const sourceVersionId = source?.latest_version?.id ?? null;
  const report = sourceVersionId
    ? bundle.artifacts.find((item) => (
        item.artifact.kind === "analysis_report"
        && item.latest_version?.metadata?.report_type === "symbolic_detail"
        && item.latest_version.metadata.source_version_id === sourceVersionId
        && item.signed_url
      ))
    : undefined;
  const job = sourceVersionId
    ? bundle.jobs.find((item) => (
        item.capability.name === "symbolic_detail"
        && item.input_version_ids.includes(sourceVersionId)
      ))
    : undefined;
  return { sourceVersionId, report, job };
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function signed(value: number): string {
  if (value > 0) return `+${value}`;
  return `${value}`;
}

export default function SymbolicDetail() {
  const { workspace } = useWorkspace();
  const exposed = isInspectorExposed("symbolic_detail");
  const preferredVersionId = workspace.representations.find(
    (representation) => representation.kind === "piano_roll" && representation.versionId,
  )?.versionId ?? null;
  const [report, setReport] = useState<SymbolicDetailReport | null>(null);
  const [sourceVersionId, setSourceVersionId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [chooserOpen, setChooserOpen] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "generating">("idle");
  const [error, setError] = useState<string | null>(null);
  const [observationLost, setObservationLost] = useState(false);
  const sequenceRef = useRef(0);

  const load = useCallback(async (
    workId: string,
    preferredSourceVersionId: string | null,
    fresh = false,
  ) => {
    const sequence = ++sequenceRef.current;
    setStatus("loading");
    setError(null);
    setObservationLost(false);
    try {
      if (fresh) clearWorkDataCache();
      const bundle = await getWorkBundle(workId);
      if (sequence !== sequenceRef.current) return;
      setProjectId(bundle.work.project_id);
      const resolved = sourceAndReportState(bundle, preferredSourceVersionId);
      setSourceVersionId(resolved.sourceVersionId);
      if (!resolved.report?.signed_url) {
        setReport(null);
        if (resolved.job && ACTIVE_JOB_STAGES.has(resolved.job.lifecycle.current)) {
          setActiveJobId(resolved.job.id);
          setChooserOpen(true);
          setStatus("generating");
          return;
        }
        setActiveJobId(null);
        setStatus("idle");
        if (
          resolved.job?.lifecycle.current === "failed"
          || resolved.job?.lifecycle.current === "cancelled"
        ) {
          setChooserOpen(true);
          setError(
            resolved.job.error
            || resolved.job.lifecycle.message
            || "Symbolic detail processing did not complete",
          );
        }
        return;
      }
      const nextReport = await fetchSymbolicDetailReport(resolved.report.signed_url);
      if (sequence !== sequenceRef.current) return;
      if (nextReport.source_version_id !== resolved.sourceVersionId) {
        throw new Error("Saved symbolic detail does not match the current MIDI Version");
      }
      setActiveJobId(null);
      setChooserOpen(false);
      setReport(nextReport);
      setStatus("idle");
    } catch (cause) {
      if (sequence !== sequenceRef.current) return;
      setActiveJobId(null);
      setReport(null);
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "Symbolic detail is unavailable");
    }
  }, []);

  useEffect(() => {
    const workId = workspace.activeWorkId;
    sequenceRef.current += 1;
    setActiveJobId(null);
    setChooserOpen(false);
    setReport(null);
    setSourceVersionId(null);
    setProjectId(null);
    setError(null);
    setObservationLost(false);
    if (exposed && workId) void load(workId, preferredVersionId);
  }, [exposed, load, preferredVersionId, workspace.activeWorkId]);

  useEffect(() => {
    const workId = workspace.activeWorkId;
    const jobId = activeJobId;
    if (!workId || !jobId) return;
    const controller = new AbortController();
    void waitForJob(jobId, () => undefined, { signal: controller.signal })
      .then(async () => {
        if (controller.signal.aborted) return;
        setActiveJobId(null);
        await load(workId, preferredVersionId, true);
      })
      .catch(async (cause) => {
        if (controller.signal.aborted) return;
        await load(workId, preferredVersionId, true);
        if (controller.signal.aborted) return;
        if (cause instanceof JobObservationError) {
          setActiveJobId(null);
          setStatus("idle");
          setChooserOpen(true);
          setObservationLost(true);
          setError(cause.message);
        }
      });
    return () => controller.abort();
  }, [activeJobId, load, preferredVersionId, workspace.activeWorkId]);

  const generate = useCallback(async () => {
    if (!sourceVersionId || !projectId || status !== "idle") return;
    setStatus("generating");
    setError(null);
    setObservationLost(false);
    setChooserOpen(true);
    try {
      const jobId = await startSymbolicDetailWorkflow(sourceVersionId, projectId);
      setActiveJobId(jobId);
    } catch (cause) {
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "Symbolic detail processing failed");
    }
  }, [projectId, sourceVersionId, status]);

  const checkStatus = useCallback(() => {
    if (!workspace.activeWorkId || status !== "idle") return;
    void load(workspace.activeWorkId, preferredVersionId, true);
  }, [load, preferredVersionId, status, workspace.activeWorkId]);

  if (!exposed || !workspace.activeWorkId || !sourceVersionId) return null;

  if (!report) {
    if (status === "loading" && !chooserOpen) return null;
    const busy = status === "loading" || status === "generating";
    return (
      <AddAnalysis
        open={chooserOpen}
        onOpenChange={setChooserOpen}
        options={[{
          id: "symbolic-detail",
          title: "Symbolic detail",
          description: "Measure register, contour, interval motion, density, and texture from this MIDI.",
          maturity: "Experimental",
          actionLabel: observationLost
            ? "Check status"
            : status === "generating"
              ? "Measuring…"
              : status === "loading"
                ? "Checking…"
                : error
                  ? "Retry"
                  : "Add",
          onAction: observationLost ? checkStatus : () => void generate(),
          busy,
        }]}
        notice={error}
        noticeRole={busy || observationLost ? "status" : "alert"}
      />
    );
  }

  const voiceMotion = report.voice_motion.status === "supported"
    ? `${percent(report.voice_motion.similar_direction_fraction ?? 0)} same-direction · ${percent(report.voice_motion.contrary_direction_fraction ?? 0)} contrary · ${percent(report.voice_motion.oblique_like_fraction ?? 0)} oblique-like`
    : "Not enough shared inferred-voice motion to compare";

  return (
    <section className="inspector-section" aria-label="Experimental symbolic detail">
      <div className="inspector-section-heading">
        <h3>Symbolic detail</h3>
        <span className="inspector-breakdown-time">Experimental</span>
      </div>
      <div className="inspector-breakdown-sparse">
        <p>Measured from the current MIDI Version. These summaries are method-qualified, not canonical melody, texture, or voice-leading theory.</p>
      </div>
      <div className="inspector-evidence-body">
        <p><strong>Register</strong> · {report.register.low_name}–{report.register.high_name} · {report.register.span_semitones} semitones</p>
        <p><strong>Contour</strong> · {signed(report.contour.net_change_semitones)} semitones net across onset pitch centroids</p>
        <p><strong>Interval motion</strong> · {percent(report.interval_motion.step_fraction)} stepwise · median {report.interval_motion.median_absolute_semitones} semitones</p>
        <p><strong>Density</strong> · {report.density.notes_per_quarter} notes / quarter · {report.density.note_count} notes measured</p>
        <p><strong>Texture</strong> · peak {report.texture.peak_simultaneous_notes} simultaneous notes · {percent(report.texture.polyphonic_time_fraction)} of symbolic time polyphonic</p>
        <p><strong>Voice motion</strong> · {voiceMotion}</p>
      </div>
      <details className="inspector-evidence-group">
        <summary>Method and provenance</summary>
        <div className="inspector-evidence-body">
          <p>{report.interpretation}</p>
          <p>Method: {report.method.label} · Partitura {report.method.partitura_version} · music21 {report.method.music21_version}</p>
          <p>Source: {report.source_artifact_kind} Version {report.source_version_id}</p>
          {report.voice_motion.reason && <p>{report.voice_motion.reason}</p>}
        </div>
      </details>
    </section>
  );
}
