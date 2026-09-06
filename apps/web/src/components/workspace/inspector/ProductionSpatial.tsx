"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import AddAnalysis from "@/components/workspace/AddAnalysis";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import { formatTime } from "@/lib/format";
import { isInspectorExposed } from "@/lib/inspector/capabilities";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import {
  fetchProductionSpatialReport,
  startProductionSpatialWorkflow,
  type ProductionSpatialRelation,
  type ProductionSpatialReport,
} from "@/lib/production-spatial-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

const ACTIVE_JOB_STAGES = new Set(["queued", "claimed", "running"]);

function sourceAndLensState(bundle: Awaited<ReturnType<typeof getWorkBundle>>) {
  const source = bundle.artifacts.find(
    (item) => item.artifact.kind === "audio_original" && item.latest_version && item.signed_url,
  );
  const sourceVersionId = source?.latest_version?.id ?? null;
  const report = sourceVersionId
    ? bundle.artifacts.find((item) => (
        item.artifact.kind === "analysis_report"
        && item.latest_version?.metadata?.report_type === "production_spatial"
        && item.latest_version.metadata.source_version_id === sourceVersionId
        && item.signed_url
      ))
    : undefined;
  const job = sourceVersionId
    ? bundle.jobs.find((item) => (
        item.capability.name === "production_spatial"
        && item.input_version_ids.includes(sourceVersionId)
      ))
    : undefined;
  return { sourceVersionId, report, job };
}

function signedDelta(relation: ProductionSpatialRelation): string {
  const sign = relation.delta > 0 ? "+" : "";
  return `${sign}${relation.delta} ${relation.unit}`;
}

export default function ProductionSpatial() {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek, play, setActiveSource, audioRef } = useTransport();
  const [report, setReport] = useState<ProductionSpatialReport | null>(null);
  const [sourceVersionId, setSourceVersionId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [chooserOpen, setChooserOpen] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "generating">("idle");
  const [error, setError] = useState<string | null>(null);
  const [observationLost, setObservationLost] = useState(false);
  const sequenceRef = useRef(0);

  const load = useCallback(async (workId: string, fresh = false) => {
    const sequence = ++sequenceRef.current;
    setStatus("loading");
    setError(null);
    setObservationLost(false);
    try {
      if (fresh) clearWorkDataCache();
      const bundle = await getWorkBundle(workId);
      if (sequence !== sequenceRef.current) return;
      setProjectId(bundle.work.project_id);
      const resolved = sourceAndLensState(bundle);
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
            || "Production / Space processing did not complete",
          );
        }
        return;
      }
      const nextReport = await fetchProductionSpatialReport(resolved.report.signed_url);
      if (sequence !== sequenceRef.current) return;
      if (nextReport.source_version_id !== resolved.sourceVersionId) {
        throw new Error("Saved Production / Space report does not match the current source Version");
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
      setError(cause instanceof Error ? cause.message : "Production / Space is unavailable");
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
    if (workId) void load(workId);
  }, [load, workspace.activeWorkId]);

  useEffect(() => {
    const workId = workspace.activeWorkId;
    const jobId = activeJobId;
    if (!workId || !jobId) return;
    const controller = new AbortController();

    void waitForJob(jobId, () => undefined, { signal: controller.signal })
      .then(async () => {
        if (controller.signal.aborted) return;
        setActiveJobId(null);
        await load(workId, true);
      })
      .catch(async (cause) => {
        if (controller.signal.aborted) return;
        await load(workId, true);
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
  }, [activeJobId, load, workspace.activeWorkId]);

  const generate = useCallback(async () => {
    if (
      !workspace.activeWorkId
      || !sourceVersionId
      || !projectId
      || status === "generating"
      || status === "loading"
    ) return;
    setStatus("generating");
    setError(null);
    setObservationLost(false);
    setChooserOpen(true);
    try {
      const jobId = await startProductionSpatialWorkflow(sourceVersionId, projectId);
      setActiveJobId(jobId);
    } catch (cause) {
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "Production / Space processing failed");
    }
  }, [projectId, sourceVersionId, status, workspace.activeWorkId]);

  const checkStatus = useCallback(() => {
    if (!workspace.activeWorkId || status !== "idle") return;
    void load(workspace.activeWorkId, true);
  }, [load, status, workspace.activeWorkId]);

  const focusRelation = useCallback((relation: ProductionSpatialRelation, shouldPlay: boolean) => {
    const focus = () => {
      seek(relation.start_seconds);
      if (shouldPlay) play();
    };
    const originalSource = transport.sources.find((source) => source.role === "original");
    const requiresOriginal = transport.activeSource?.role === "score";
    if (requiresOriginal && originalSource && audioRef.current) {
      const audio = audioRef.current;
      setActiveSource(originalSource);
      audio.addEventListener("loadedmetadata", focus, { once: true });
    } else if (!requiresOriginal) {
      focus();
    }

    setSelection({
      timeRange: {
        start: relation.start_seconds,
        end: relation.end_seconds,
        domain: "performance",
      },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    requestWorkspaceOrientation();
  }, [audioRef, play, seek, setActiveSource, setSelection, transport.activeSource?.role, transport.sources]);

  if (!isInspectorExposed("production_spatial") || !workspace.activeWorkId || !sourceVersionId) {
    return null;
  }

  if (!report) {
    if (status === "loading" && !chooserOpen) return null;
    const busy = status === "loading" || status === "generating";
    return (
      <section className="inspector-section" aria-label="Production and spatial analysis">
        <AddAnalysis
          open={chooserOpen}
          onOpenChange={setChooserOpen}
          options={[{
            id: "production-spatial",
            title: "Production / Space",
            description: "Compare literal loudness, stereo mid/side, spectral, and transient changes.",
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
      </section>
    );
  }

  const hearingRequiresOriginal = transport.activeSource?.role === "score";

  return (
    <section className="inspector-section" aria-label="Production and spatial analysis">
      <div className="inspector-section-heading">
        <h3>Production / Space</h3>
        <span className="inspector-breakdown-time">Experimental</span>
      </div>

      <div className="inspector-breakdown-sparse">
        <p>{report.interpretation}</p>
        {report.channel_count !== 2 && (
          <p>Mid/side evidence is unavailable for this {report.channel_count}-channel source.</p>
        )}
      </div>

      <div aria-live="polite">
        {report.relations.map((relation) => (
          <article
            className="inspector-breakdown-finding"
            key={`${relation.kind}:${relation.start_seconds}:${relation.end_seconds}`}
          >
            <div className="inspector-breakdown-focus">
              <span className="inspector-breakdown-time">
                {formatTime(relation.start_seconds)}–{formatTime(relation.end_seconds)}
              </span>
              <span className="inspector-breakdown-headline">{relation.label}</span>
              <span className="inspector-breakdown-support">{signedDelta(relation)}</span>
            </div>

            <details className="inspector-evidence-group">
              <summary>Method</summary>
              <div className="inspector-evidence-body">
                <p>{relation.method}</p>
                <p>
                  Compared {formatTime(relation.from_start_seconds)}–{formatTime(relation.from_end_seconds)}
                  {" → "}
                  {formatTime(relation.to_start_seconds)}–{formatTime(relation.to_end_seconds)}.
                </p>
                <p>Source Version: {report.source_version_id}</p>
              </div>
            </details>

            <div className="inspector-breakdown-actions" aria-label={`${relation.label} actions`}>
              <button
                type="button"
                className="inspector-breakdown-action"
                onClick={() => focusRelation(relation, true)}
              >
                {hearingRequiresOriginal ? "Hear original" : "Hear"}
              </button>
              <button
                type="button"
                className="inspector-breakdown-action"
                onClick={() => focusRelation(relation, false)}
              >
                Inspect
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
