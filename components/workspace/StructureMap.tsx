"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import AddAnalysis, { type AddAnalysisOption } from "@/components/workspace/AddAnalysis";
import { useLayerAnalysis } from "@/components/workspace/useLayerAnalysis";
import PitchContourLane from "@/components/workspace/PitchContourLane";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import { formatTime } from "@/lib/format";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import { startPitchContourWorkflow } from "@/lib/pitch-contour-client";
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

type AnalysisJob = Awaited<ReturnType<typeof getWorkBundle>>["jobs"][number];

function terminalJobError(job: AnalysisJob | undefined, fallback: string): string | null {
  if (job?.lifecycle.current !== "failed" && job?.lifecycle.current !== "cancelled") return null;
  return job.error || job.lifecycle.message || fallback;
}

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
  const pitchReport = sourceVersionId
    ? bundle.artifacts.find((item) => (
        item.artifact.kind === "analysis_report"
        && item.latest_version?.metadata?.representation_type === "pitch_contour"
        && item.latest_version.metadata.source_audio_version_id === sourceVersionId
        && item.latest_version.metadata.status === "experimental"
        && item.signed_url
      ))
    : undefined;
  const pitchJob = sourceVersionId
    ? bundle.jobs.find((item) => (
        item.capability.name === "pitch_contour"
        && item.input_version_ids.includes(sourceVersionId)
      ))
    : undefined;
  return { sourceVersionId, report, job, pitchReport, pitchJob };
}

export default function StructureMap({ canProcess = false }: { canProcess?: boolean }) {
  const { workspace, setSelection, setInspectorMode, toggleInspector } = useWorkspace();
  const { transport, seek, play, setActiveSource, audioRef } = useTransport();
  const layerAnalysis = useLayerAnalysis(canProcess);
  const [report, setReport] = useState<StructureMapReport | null>(null);
  const [mapOpen, setMapOpen] = useState(false);
  const [pitchReady, setPitchReady] = useState(false);
  const [pitchOpen, setPitchOpen] = useState(false);
  const [sourceVersionId, setSourceVersionId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activePitchJobId, setActivePitchJobId] = useState<string | null>(null);
  const [chooserOpen, setChooserOpen] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "generating">("idle");
  const [pitchStatus, setPitchStatus] = useState<"idle" | "loading" | "generating">("idle");
  const [error, setError] = useState<string | null>(null);
  const [pitchError, setPitchError] = useState<string | null>(null);
  const [observationLost, setObservationLost] = useState(false);
  const [pitchObservationLost, setPitchObservationLost] = useState(false);
  const sequenceRef = useRef(0);

  const load = useCallback(async (workId: string, fresh = false): Promise<boolean> => {
    const sequence = ++sequenceRef.current;
    setStatus("loading");
    setPitchStatus("loading");
    setError(null);
    setPitchError(null);
    setObservationLost(false);
    setPitchObservationLost(false);
    try {
      if (fresh) clearWorkDataCache();
      const bundle = await getWorkBundle(workId);
      if (sequence !== sequenceRef.current) return false;
      setProjectId(bundle.work.project_id);
      const resolved = sourceAndMapState(bundle);
      setSourceVersionId(resolved.sourceVersionId);

      const pitchActive = Boolean(
        resolved.pitchJob && ACTIVE_JOB_STAGES.has(resolved.pitchJob.lifecycle.current),
      );
      const nextPitchError = terminalJobError(
        resolved.pitchJob,
        "Pitch contour processing did not complete",
      );
      const pitchAvailable = Boolean(resolved.pitchReport?.signed_url);
      setActivePitchJobId(pitchActive ? resolved.pitchJob?.id ?? null : null);
      setPitchReady(pitchAvailable);
      setPitchStatus(pitchActive ? "generating" : "idle");
      setPitchError(nextPitchError);
      if (pitchActive || nextPitchError) setChooserOpen(true);

      if (!resolved.report?.signed_url) {
        setReport(null);
        setMapOpen(false);
        if (resolved.job && ACTIVE_JOB_STAGES.has(resolved.job.lifecycle.current)) {
          setActiveJobId(resolved.job.id);
          setChooserOpen(true);
          setStatus("generating");
          return pitchAvailable;
        }
        setActiveJobId(null);
        setStatus("idle");
        const nextError = terminalJobError(
          resolved.job,
          "Structure Map processing did not complete",
        );
        if (nextError) {
          setChooserOpen(true);
          setError(nextError);
        }
        return pitchAvailable;
      }
      const nextReport = await fetchStructureMapReport(resolved.report.signed_url);
      if (sequence !== sequenceRef.current) return false;
      if (nextReport.source_version_id !== resolved.sourceVersionId) {
        throw new Error("Saved Structure Map does not match the current source Version");
      }
      setActiveJobId(null);
      if (!pitchActive && !nextPitchError) setChooserOpen(false);
      setReport(nextReport);
      setMapOpen(true);
      setStatus("idle");
      return pitchAvailable;
    } catch (cause) {
      if (sequence !== sequenceRef.current) return false;
      setActiveJobId(null);
      setActivePitchJobId(null);
      setReport(null);
      setMapOpen(false);
      setPitchReady(false);
      setStatus("idle");
      setPitchStatus("idle");
      setError(cause instanceof Error ? cause.message : "Experimental analyses are unavailable");
      return false;
    }
  }, []);

  useEffect(() => {
    const workId = workspace.activeWorkId;
    sequenceRef.current += 1;
    setActiveJobId(null);
    setActivePitchJobId(null);
    setChooserOpen(false);
    setReport(null);
    setMapOpen(false);
    setPitchReady(false);
    setPitchOpen(false);
    setSourceVersionId(null);
    setProjectId(null);
    setError(null);
    setPitchError(null);
    setObservationLost(false);
    setPitchObservationLost(false);
    if (workId) void load(workId);
  }, [load, workspace.activeWorkId]);

  // Layers owns its durable job state but discovery remains in the shared chooser.
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

  useEffect(() => {
    const workId = workspace.activeWorkId;
    const jobId = activePitchJobId;
    if (!workId || !jobId) return;
    const controller = new AbortController();

    void waitForJob(jobId, () => undefined, { signal: controller.signal })
      .then(async () => {
        if (controller.signal.aborted) return;
        // `load` is the durable authority and clears a terminal job id itself.
        // Do not clear this effect dependency before the refresh: doing so runs
        // this effect's cleanup, aborts the controller, and prevents the newly
        // persisted lane from opening after a successful Add action.
        const pitchAvailable = await load(workId, true);
        if (pitchAvailable) {
          setPitchOpen(true);
          setChooserOpen(false);
        }
      })
      .catch(async (cause) => {
        if (controller.signal.aborted) return;
        const pitchAvailable = await load(workId, true);
        if (pitchAvailable) {
          setPitchOpen(true);
          setChooserOpen(false);
          return;
        }
        if (controller.signal.aborted) return;
        if (cause instanceof JobObservationError) {
          setActivePitchJobId(null);
          setPitchStatus("idle");
          setChooserOpen(true);
          setPitchObservationLost(true);
          setPitchError(cause.message);
        }
      });

    return () => controller.abort();
  }, [activePitchJobId, load, workspace.activeWorkId]);

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

  const generatePitch = useCallback(async () => {
    if (
      !workspace.activeWorkId
      || !sourceVersionId
      || !projectId
      || pitchStatus === "generating"
      || pitchStatus === "loading"
    ) return;
    setPitchStatus("generating");
    setPitchError(null);
    setPitchObservationLost(false);
    setChooserOpen(true);
    try {
      const jobId = await startPitchContourWorkflow(sourceVersionId, projectId);
      setActivePitchJobId(jobId);
    } catch (cause) {
      setPitchStatus("idle");
      setPitchError(cause instanceof Error ? cause.message : "Pitch contour processing failed");
    }
  }, [pitchStatus, projectId, sourceVersionId, workspace.activeWorkId]);

  const checkStatus = useCallback(() => {
    if (!workspace.activeWorkId || status !== "idle") return;
    void load(workspace.activeWorkId, true);
  }, [load, status, workspace.activeWorkId]);

  const checkPitchStatus = useCallback(() => {
    if (!workspace.activeWorkId || pitchStatus !== "idle") return;
    void load(workspace.activeWorkId, true);
  }, [load, pitchStatus, workspace.activeWorkId]);

  const openAnalysisInspector = useCallback(() => {
    setInspectorMode("analysis");
    if (workspace.inspectorCollapsed) toggleInspector();
    setChooserOpen(false);
  }, [setInspectorMode, toggleInspector, workspace.inspectorCollapsed]);

  const openMap = useCallback(() => {
    setMapOpen(true);
    setChooserOpen(false);
  }, []);

  const openPitch = useCallback(() => {
    setPitchOpen(true);
    setChooserOpen(false);
  }, []);

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

  const busy = status === "loading" || status === "generating";
  const pitchBusy = pitchStatus === "loading" || pitchStatus === "generating";
  const selectedPassage = workspace.selection?.timeRange;
  const hasExactSelectedPassage = Boolean(
    selectedPassage
    && selectedPassage.domain === "performance"
    && workspace.selection?.provenance.timeExact === true
    && Number.isFinite(selectedPassage.start)
    && Number.isFinite(selectedPassage.end)
    && selectedPassage.start >= 0
    && selectedPassage.end > selectedPassage.start,
  );
  const analysisOptions: AddAnalysisOption[] = [];
  if (!report) {
    analysisOptions.push({
      id: "structure-map",
      title: "Structure Map",
      description: "Find rough candidate spans so you can jump through the recording's shape.",
      maturity: "Experimental",
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
      busy,
    });
  } else {
    analysisOptions.push({
      id: "structure-map",
      title: "Structure Map",
      description: "Rough candidate spans are ready for navigation.",
      maturity: "Experimental",
      actionLabel: mapOpen ? "Shown" : "Open",
      onAction: openMap,
      disabled: mapOpen,
    });
  }
  analysisOptions.push({
    id: "pitch-contour",
    title: "Pitch Contour",
    description: "Trace continuous monophonic pitch against the recording and seek through it.",
    maturity: "Experimental",
    actionLabel: pitchReady
      ? pitchOpen ? "Shown" : "Open"
      : pitchObservationLost
        ? "Check status"
        : pitchStatus === "generating"
          ? "Finding pitch…"
          : pitchStatus === "loading"
            ? "Checking…"
            : pitchError
              ? "Retry"
              : "Add",
    onAction: pitchReady
      ? openPitch
      : pitchObservationLost
        ? checkPitchStatus
        : () => void generatePitch(),
    disabled: pitchReady && pitchOpen,
    busy: pitchBusy,
  });
  if (layerAnalysis.option) {
    analysisOptions.push(layerAnalysis.option);
  }
  if (hasExactSelectedPassage) {
    analysisOptions.push({
      id: "similar-moments",
      title: "Similar moments",
      description: "Find method-qualified candidate passages like this exact selection.",
      maturity: "Experimental",
      actionLabel: "Open",
      onAction: openAnalysisInspector,
    });
  }
  if (workspace.analysisState !== "idle") {
    analysisOptions.push({
      id: "measured-changes",
      title: "Changes",
      description: "Open measured change moments in Breakdown without starting another job.",
      maturity: "Experimental",
      actionLabel: "Open",
      onAction: openAnalysisInspector,
    });
  }

  const notice = [error, pitchError, layerAnalysis.notice].filter(Boolean).join(" · ") || null;
  const noticeRole = (
    busy
    || pitchBusy
    || observationLost
    || pitchObservationLost
    || (Boolean(layerAnalysis.notice) && layerAnalysis.noticeRole === "status")
  ) ? "status" : "alert";
  const discovery = (
    <AddAnalysis
      open={chooserOpen}
      onOpenChange={setChooserOpen}
      options={analysisOptions}
      notice={notice}
      noticeRole={noticeRole}
    />
  );

  if (!report) {
    if (status === "loading" && pitchStatus === "loading" && !chooserOpen && !pitchReady && !layerAnalysis.option) return null;
    return (
      <>
        {discovery}
        {pitchReady && pitchOpen && <PitchContourLane onClose={() => setPitchOpen(false)} />}
      </>
    );
  }

  const hearingRequiresOriginal = transport.activeSource?.role === "score";

  return (
    <>
      {discovery}
      {pitchReady && pitchOpen && <PitchContourLane onClose={() => setPitchOpen(false)} />}
      {mapOpen && (
        <section className={styles.map} aria-label="Experimental Structure Map">
          <header className={styles.header}>
            <div>
              <div className={styles.titleLine}>
                <h2>Map</h2>
                <span className={styles.experimental}>Experimental</span>
              </div>
              <p>Rough candidate spans for jumping through the recording.</p>
            </div>
            <button type="button" className={styles.hide} onClick={() => setMapOpen(false)}>
              Hide
            </button>
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
      )}
    </>
  );
}
