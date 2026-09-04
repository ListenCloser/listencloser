"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import AddAnalysis from "@/components/workspace/AddAnalysis";
import { useLayerAnalysis } from "@/components/workspace/useLayerAnalysis";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import { formatTime } from "@/lib/format";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";
import {
  fetchStructureMapReport,
  startStructureMapWorkflow,
  type StructureMapReport,
  type StructureMapSpan,
} from "@/lib/structure-map-client";
import styles from "./StructureMap.module.css";

const ACTIVE_JOB_STAGES = new Set(["queued", "claimed", "running"]);

function sourceAndMapState(bundle: Awaited<ReturnType<typeof getWorkBundle>>) {
  const source = bundle.artifacts.find(
    (item) => item.artifact.kind === "audio_original" && item.latest_version && item.signed_url,
  );
  const sourceVersionId = source?.latest_version?.id ?? null;
  const report = sourceVersionId
    ? bundle.artifacts.find((item) => (
        item.artifact.kind === "analysis_report"
        && item.latest_version?.metadata?.report_type === "structure_map"
        && item.latest_version.metadata.source_version_id === sourceVersionId
        && item.signed_url
      ))
    : undefined;
  const job = sourceVersionId
    ? bundle.jobs.find((item) => (
        item.capability.name === "structure_map"
        && item.input_version_ids.includes(sourceVersionId)
      ))
    : undefined;
  return { sourceVersionId, report, job };
}

export default function StructureMap({ canProcess = false }: { canProcess?: boolean }) {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek, play, setActiveSource, audioRef } = useTransport();
  const layerAnalysis = useLayerAnalysis(canProcess);
  const [report, setReport] = useState<StructureMapReport | null>(null);
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
      const resolved = sourceAndMapState(bundle);
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
            || "Structure Map processing did not complete",
          );
        }
        return;
      }
      const nextReport = await fetchStructureMapReport(resolved.report.signed_url);
      if (sequence !== sequenceRef.current) return;
      if (nextReport.source_version_id !== resolved.sourceVersionId) {
        throw new Error("Saved Structure Map does not match the current source Version");
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
      setError(cause instanceof Error ? cause.message : "Structure Map is unavailable");
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

  // A running/disconnected/failed Layers job must remain visible after reload,
  // but discovery still has one shared chooser rather than a second capability
  // button elsewhere in the workspace.
  useEffect(() => {
    if (layerAnalysis.option?.busy || layerAnalysis.notice) setChooserOpen(true);
  }, [layerAnalysis.notice, layerAnalysis.option?.busy]);

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

        // The Work bundle is durable authority for terminal state. In
        // particular, JobObservationError means only that this browser lost
        // contact or timed out; it must not fabricate a server-side failure or
        // restart the durable Job.
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
      const jobId = await startStructureMapWorkflow(sourceVersionId, projectId);
      setActiveJobId(jobId);
    } catch (cause) {
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "Structure Map processing failed");
    }
  }, [projectId, sourceVersionId, status, workspace.activeWorkId]);

  const checkStatus = useCallback(() => {
    if (!workspace.activeWorkId || status !== "idle") return;
    void load(workspace.activeWorkId, true);
  }, [load, status, workspace.activeWorkId]);

  const focusSpan = useCallback((span: StructureMapSpan, shouldPlay: boolean) => {
    const focus = () => {
      seek(span.start_seconds);
      if (shouldPlay) play();
    };
    const originalSource = transport.sources.find((source) => source.role === "original");
    const requiresOriginal = transport.activeSource?.role === "score";

    // Map spans use source-audio performance seconds. Score playback uses
    // notation time, so an exact audition must explicitly choose Original
    // before seeking rather than silently reinterpreting the coordinate.
    if (requiresOriginal && originalSource && audioRef.current) {
      const audio = audioRef.current;
      setActiveSource(originalSource);
      audio.addEventListener("loadedmetadata", focus, { once: true });
    } else if (!requiresOriginal) {
      focus();
    }

    setSelection({
      timeRange: {
        start: span.start_seconds,
        end: span.end_seconds,
        domain: "performance",
      },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
  }, [audioRef, play, seek, setActiveSource, setSelection, transport.activeSource?.role, transport.sources]);

  if (!workspace.activeWorkId || !sourceVersionId) return null;

  const mapBusy = status === "loading" || status === "generating";
  const mapOption = {
    id: "structure-map",
    title: "Structure Map",
    description: "Find rough candidate spans so you can jump through the recording's shape.",
    maturity: "Experimental" as const,
    actionLabel: observationLost
      ? "Check status"
      : status === "generating"
        ? "Finding shape…"
        : status === "loading"
          ? "Checking…"
          : error
            ? "Retry"
            : "Add",
    onAction: observationLost ? checkStatus : () => void generate(),
    busy: mapBusy,
  };
  const chooserNotice = error ?? layerAnalysis.notice;
  const chooserNoticeRole = error
    ? (mapBusy || observationLost ? "status" as const : "alert" as const)
    : layerAnalysis.noticeRole;

  if (!report) {
    if (status === "loading" && !chooserOpen && !layerAnalysis.option) return null;
    return (
      <AddAnalysis
        open={chooserOpen}
        onOpenChange={setChooserOpen}
        options={[mapOption, ...(layerAnalysis.option ? [layerAnalysis.option] : [])]}
        notice={chooserNotice}
        noticeRole={chooserNoticeRole}
      />
    );
  }

  const hearingRequiresOriginal = transport.activeSource?.role === "score";

  return (
    <>
      <section className={styles.map} aria-label="Experimental Structure Map">
        <header className={styles.header}>
          <div>
            <div className={styles.titleLine}>
              <h2>Map</h2>
              <span className={styles.experimental}>Experimental</span>
            </div>
            <p>Rough candidate spans for jumping through the recording.</p>
          </div>
        </header>

        <div className={styles.rows}>
          {report.candidate_spans.map((span, index) => {
            const active = transport.position >= span.start_seconds && transport.position < span.end_seconds;
            const hearLabel = hearingRequiresOriginal ? "Hear original" : "Hear";
            return (
              <div className={`${styles.row}${active ? ` ${styles.active}` : ""}`} key={`${span.start_seconds}-${index}`}>
                <button type="button" className={styles.jump} onClick={() => focusSpan(span, false)} aria-current={active ? "true" : undefined}>
                  <strong>{span.label}</strong>
                  <span>{formatTime(span.start_seconds)}–{formatTime(span.end_seconds)}</span>
                </button>
                <button
                  type="button"
                  className={styles.hear}
                  onClick={() => focusSpan(span, true)}
                  aria-label={`${hearLabel} ${span.label} from ${formatTime(span.start_seconds)}`}
                >
                  {hearLabel}
                </button>
              </div>
            );
          })}
        </div>
        <details className={styles.method}>
          <summary>How this map was made</summary>
          <p>{report.interpretation}</p>
          <p><strong>Method:</strong> {report.method.label}</p>
          <p><strong>Source Version:</strong> <span className={styles.versionId}>{report.source_version_id}</span></p>
        </details>
      </section>
      {layerAnalysis.option && (
        <AddAnalysis
          open={chooserOpen}
          onOpenChange={setChooserOpen}
          options={[layerAnalysis.option]}
          notice={layerAnalysis.notice}
          noticeRole={layerAnalysis.noticeRole}
        />
      )}
    </>
  );
}
