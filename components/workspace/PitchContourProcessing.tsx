"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  clearWorkDataCache,
  getJob,
  getWorkBundle,
  retryJob,
  startPitchContourWorkflow,
} from "@/lib/api-client";
import { PITCH_CONTOUR_OPEN_EVENT, type PitchContourOpenDetail } from "@/lib/pitch-contour";
import { useWorkspace } from "@/lib/stores/workspace";

type PitchExecution = "checking" | "add" | "processing" | "ready" | "failed" | "unavailable";

const ACTIVE_STAGES = new Set(["queued", "claimed", "running"]);
const POLL_MS = 750;

function openPitchContour(workId: string) {
  window.dispatchEvent(new CustomEvent<PitchContourOpenDetail>(PITCH_CONTOUR_OPEN_EVENT, {
    detail: { workId },
  }));
}

export default function PitchContourProcessing() {
  const { workspace } = useWorkspace();
  const workId = workspace.activeWorkId;
  const sourceVersionId = workspace.representations.find((item) => item.kind === "waveform")?.versionId ?? null;
  const [execution, setExecution] = useState<PitchExecution>("checking");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const openWhenReadyRef = useRef(false);

  const syncFromServer = useCallback(async () => {
    if (!workId) {
      setExecution("unavailable");
      setProjectId(null);
      setJobId(null);
      return;
    }
    setExecution("checking");
    const bundle = await getWorkBundle(workId);
    setProjectId(bundle.work.project_id);

    const ready = bundle.artifacts.some((item) => (
      item.artifact.kind === "analysis_report"
      && item.latest_version?.metadata?.representation_type === "pitch_contour"
    ));
    if (ready) {
      setExecution("ready");
      setJobId(null);
      setError(null);
      return;
    }

    const latestJob = bundle.jobs
      .filter((job) => job.capability.name === "pitch_contour")
      .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
    if (latestJob && ACTIVE_STAGES.has(latestJob.lifecycle.current)) {
      setExecution("processing");
      setJobId(latestJob.id);
      setError(null);
      return;
    }
    if (latestJob?.lifecycle.current === "failed" || latestJob?.lifecycle.current === "cancelled") {
      setExecution("failed");
      setJobId(latestJob.id);
      setError(latestJob.error ?? "Pitch contour did not complete.");
      return;
    }

    setExecution(sourceVersionId ? "add" : "unavailable");
    setJobId(null);
    setError(null);
  }, [sourceVersionId, workId]);

  useEffect(() => {
    let cancelled = false;
    void syncFromServer().catch((cause) => {
      if (cancelled) return;
      setExecution(sourceVersionId ? "add" : "unavailable");
      setError(cause instanceof Error ? cause.message : "Pitch contour status could not be loaded.");
    });
    return () => { cancelled = true; };
  }, [syncFromServer, sourceVersionId]);

  useEffect(() => {
    if (execution !== "processing" || !jobId || !workId) return;
    let cancelled = false;
    let timer: number | null = null;

    const poll = async () => {
      try {
        const state = await getJob(jobId);
        if (cancelled) return;
        if (ACTIVE_STAGES.has(state.stage)) {
          timer = window.setTimeout(() => void poll(), POLL_MS);
          return;
        }
        if (state.stage === "succeeded") {
          clearWorkDataCache();
          setExecution("ready");
          setJobId(null);
          setError(null);
          if (openWhenReadyRef.current) openPitchContour(workId);
          openWhenReadyRef.current = false;
          return;
        }
        setExecution("failed");
        setError(state.error ?? "Pitch contour did not complete.");
        openWhenReadyRef.current = false;
      } catch (cause) {
        if (cancelled) return;
        setExecution("failed");
        setError(cause instanceof Error ? cause.message : "Pitch contour status could not be loaded.");
        openWhenReadyRef.current = false;
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [execution, jobId, workId]);

  async function handleAction() {
    if (!workId) return;
    if (execution === "ready") {
      openPitchContour(workId);
      return;
    }
    if (!sourceVersionId || !projectId || execution === "processing" || execution === "checking") return;

    setError(null);
    openWhenReadyRef.current = true;
    try {
      if (execution === "failed" && jobId) {
        const retried = await retryJob(jobId);
        setJobId(retried.id);
      } else {
        const { job } = await startPitchContourWorkflow(sourceVersionId, projectId);
        setJobId(job.id);
      }
      setExecution("processing");
    } catch (cause) {
      setExecution("failed");
      setError(cause instanceof Error ? cause.message : "Pitch contour could not be started.");
      openWhenReadyRef.current = false;
    }
  }

  const status = execution === "checking"
    ? "Checking…"
    : execution === "processing"
      ? "Processing…"
      : execution === "ready"
        ? "Ready"
        : execution === "failed"
          ? "Failed"
          : execution === "unavailable"
            ? "Unavailable"
            : "Not added";
  const action = execution === "ready"
    ? "Open"
    : execution === "failed"
      ? "Retry"
      : "Add";

  return (
    <div
      data-testid="pitch-contour-processing"
      style={{ display: "grid", gap: 6, paddingTop: "var(--s-1)", borderTop: "1px solid var(--border-subtle)" }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 7, fontSize: "var(--fs-xs)" }}>
          <span>Pitch contour</span>
          <span style={{ border: "1px solid currentColor", borderRadius: 999, padding: "1px 6px", fontSize: 10 }}>Experimental</span>
        </span>
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>{status}</span>
      </div>
      <span className="muted" style={{ fontSize: "var(--fs-xs)", lineHeight: 1.35 }}>
        Follow continuous pitch movement in voice and expressive monophonic material.
      </span>
      <button
        type="button"
        className="btn btn-sm"
        disabled={execution === "checking" || execution === "processing" || execution === "unavailable"}
        onClick={() => void handleAction()}
      >
        {execution === "processing" ? "Processing pitch contour…" : action}
      </button>
      {error && execution === "failed" && <span role="alert" style={{ fontSize: "var(--fs-xs)" }}>{error}</span>}
    </div>
  );
}
