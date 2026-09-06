"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AddAnalysisOption } from "@/components/workspace/AddAnalysis";
import { clearWorkDataCache, getWorkBundle, retryJob } from "@/lib/api-client";
import { JobObservationError, sanitizeJobError, waitForJob } from "@/lib/job-tracking";
import {
  invalidateLayerWork,
  originalPlaybackSource,
  selectLayerSources,
  separationJobForSource,
  startLayerSeparation,
} from "@/lib/layers";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

const ACTIVE_JOB_STAGES = new Set(["queued", "claimed", "running"]);

type LayerStatus = "idle" | "loading" | "separating" | "ready";

export type LayerAnalysisState = {
  option: AddAnalysisOption | null;
  notice: string | null;
  noticeRole: "alert" | "status";
};

export function useLayerAnalysis(canProcess: boolean): LayerAnalysisState {
  const { workspace } = useWorkspace();
  const { transport, replaceSources } = useTransport();
  const [bundle, setBundle] = useState<Awaited<ReturnType<typeof getWorkBundle>> | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<LayerStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [observationLost, setObservationLost] = useState(false);
  const sequenceRef = useRef(0);
  const hydratedLayerIdsRef = useRef<Set<string>>(new Set());

  const load = useCallback(async (workId: string, fresh = false) => {
    const sequence = ++sequenceRef.current;
    setStatus("loading");
    setError(null);
    setObservationLost(false);
    try {
      if (fresh) clearWorkDataCache();
      const nextBundle = await getWorkBundle(workId);
      if (sequence !== sequenceRef.current) return;
      setBundle(nextBundle);
      const original = originalPlaybackSource(nextBundle);
      if (!original) {
        setActiveJobId(null);
        setStatus("idle");
        return;
      }

      const layers = selectLayerSources(nextBundle, original.id);
      if (layers.length === 4) {
        setActiveJobId(null);
        setStatus("ready");
        return;
      }

      const job = separationJobForSource(nextBundle, original.id);
      if (job && ACTIVE_JOB_STAGES.has(job.lifecycle.current)) {
        setActiveJobId(job.id);
        setStatus("separating");
        return;
      }

      setActiveJobId(null);
      setStatus("idle");
      if (job?.lifecycle.current === "failed" || job?.lifecycle.current === "cancelled") {
        setError(
          sanitizeJobError(job.error || job.lifecycle.message)
          || "Layer separation could not be completed.",
        );
      } else if (job?.lifecycle.current === "succeeded") {
        // A succeeded Job without all four structurally coherent stems is not a
        // usable result. Keep the failure local and never manufacture sources.
        setError("Layer separation finished without a complete four-layer result.");
      }
    } catch (cause) {
      if (sequence !== sequenceRef.current) return;
      setBundle(null);
      setActiveJobId(null);
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "Layer status is unavailable.");
    }
  }, []);

  useEffect(() => {
    sequenceRef.current += 1;
    setBundle(null);
    setActiveJobId(null);
    setStatus("idle");
    setError(null);
    setObservationLost(false);
    const workId = workspace.activeWorkId;
    if (workId) void load(workId);
  }, [load, workspace.activeWorkId]);

  const original = useMemo(() => (bundle ? originalPlaybackSource(bundle) : null), [bundle]);
  const layerSources = useMemo(
    () => (bundle && original ? selectLayerSources(bundle, original.id) : []),
    [bundle, original],
  );

  // Stems are durable playback sources, not a separate result panel. Reconcile
  // them into the existing transport selector after the Work session has loaded
  // its ordinary sources, and remove only the stem IDs previously owned here.
  useEffect(() => {
    const previousLayerIds = hydratedLayerIdsRef.current;
    const withoutPreviousLayers = transport.sources.filter((source) => !previousLayerIds.has(source.id));

    if (layerSources.length !== 4) {
      if (previousLayerIds.size === 0) return;
      hydratedLayerIdsRef.current = new Set();
      const activeWasLayer = Boolean(transport.activeSource && previousLayerIds.has(transport.activeSource.id));
      replaceSources(
        withoutPreviousLayers,
        activeWasLayer ? original?.id ?? undefined : transport.activeSource?.id,
        true,
      );
      return;
    }

    // WorkspaceSession owns the base playback list. Waiting until it is present
    // avoids a race where optional analysis could temporarily replace the normal
    // Original/Transcription/Score choices during cold open.
    if (transport.sources.length === 0) return;

    const nextSources = [
      ...withoutPreviousLayers,
      ...layerSources.filter((layer) => !withoutPreviousLayers.some((source) => source.id === layer.id)),
    ];
    const currentIds = transport.sources.map((source) => source.id).join("|");
    const nextIds = nextSources.map((source) => source.id).join("|");
    hydratedLayerIdsRef.current = new Set(layerSources.map((source) => source.id));
    if (currentIds === nextIds) return;

    replaceSources(nextSources, transport.activeSource?.id ?? original?.id ?? undefined, true);
  }, [layerSources, original?.id, replaceSources, transport.activeSource, transport.sources]);

  useEffect(() => {
    const workId = workspace.activeWorkId;
    const jobId = activeJobId;
    if (!workId || !jobId) return;
    const controller = new AbortController();

    void waitForJob(jobId, () => undefined, { signal: controller.signal })
      .then(async () => {
        if (controller.signal.aborted) return;
        setActiveJobId(null);
        invalidateLayerWork();
        await load(workId, true);
      })
      .catch(async (cause) => {
        if (controller.signal.aborted) return;
        // Durable Work truth wins over the browser observer. Reconcile first;
        // only an unresolved observation failure becomes "Check status".
        await load(workId, true);
        if (controller.signal.aborted) return;
        if (cause instanceof JobObservationError) {
          setActiveJobId(null);
          setStatus("idle");
          setObservationLost(true);
          setError(cause.message);
        }
      });

    return () => controller.abort();
  }, [activeJobId, load, workspace.activeWorkId]);

  const separate = useCallback(async () => {
    const workId = workspace.activeWorkId;
    if (!workId || !bundle || !original || !canProcess || status === "separating") return;
    setStatus("separating");
    setError(null);
    setObservationLost(false);
    try {
      const result = await startLayerSeparation(original.id, bundle.work.project_id);
      const dispatchedJobId = result.job.id;
      const dispatchedStage = result.job.lifecycle?.current;
      if (!dispatchedJobId || !dispatchedStage) {
        throw new Error("Layer separation returned an incomplete Job response.");
      }

      let jobId = dispatchedJobId;
      if (dispatchedStage === "failed" || dispatchedStage === "cancelled") {
        const retried = await retryJob(jobId);
        jobId = retried.id;
        if (retried.stage === "succeeded") {
          invalidateLayerWork();
          await load(workId, true);
          return;
        }
      } else if (dispatchedStage === "succeeded") {
        invalidateLayerWork();
        await load(workId, true);
        return;
      }
      setActiveJobId(jobId);
    } catch (cause) {
      setStatus("idle");
      setError(
        sanitizeJobError(cause instanceof Error ? cause.message : null)
        || "Layer separation could not be started.",
      );
    }
  }, [bundle, canProcess, load, original, status, workspace.activeWorkId]);

  const checkStatus = useCallback(() => {
    const workId = workspace.activeWorkId;
    if (!workId || status !== "idle") return;
    void load(workId, true);
  }, [load, status, workspace.activeWorkId]);

  if (!workspace.activeWorkId || !original || status === "ready") {
    return { option: null, notice: null, noticeRole: "status" };
  }

  const busy = status === "loading" || status === "separating";
  return {
    option: {
      id: "layers",
      title: "Separate layers",
      description: "Separate vocals, drums, bass, and other so you can hear each part.",
      maturity: "Experimental",
      actionLabel: observationLost
        ? "Check status"
        : status === "separating"
          ? "Separating…"
          : status === "loading"
            ? "Checking…"
            : error
              ? "Retry"
              : "Add",
      onAction: observationLost ? checkStatus : () => void separate(),
      busy,
      disabled: !canProcess,
    },
    notice: error ? `${error} Original remains available.` : null,
    noticeRole: observationLost || busy ? "status" : "alert",
  };
}
