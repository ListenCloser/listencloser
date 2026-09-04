"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getWorkBundle, retryJob } from "@/lib/api-client";
import { JobObservationError, sanitizeJobError, waitForJob } from "@/lib/job-tracking";
import {
  invalidateLayerWork,
  originalPlaybackSource,
  selectLayerSources,
  startLayerSeparation,
} from "@/lib/layers";
import { useTransport, type PlaybackSource } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

type LayerState = "idle" | "loading" | "separating" | "ready" | "error";

export default function LayersControl({
  projectId,
  canProcess,
}: {
  projectId: string;
  canProcess: boolean;
}) {
  const { workspace } = useWorkspace();
  const { transport, setActiveSource } = useTransport();
  const [bundle, setBundle] = useState<Awaited<ReturnType<typeof getWorkBundle>> | null>(null);
  const [state, setState] = useState<LayerState>("idle");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const trackingAbortRef = useRef<AbortController | null>(null);
  const activeWorkId = workspace.activeWorkId;

  const refresh = useCallback(async (workId: string) => {
    const nextBundle = await getWorkBundle(workId);
    setBundle(nextBundle);
    const original = originalPlaybackSource(nextBundle);
    const layers = original ? selectLayerSources(nextBundle, original.id) : [];
    setState(layers.length === 4 ? "ready" : "idle");
    return nextBundle;
  }, []);

  useEffect(() => {
    trackingAbortRef.current?.abort();
    trackingAbortRef.current = null;
    setBundle(null);
    setError(null);
    setMessage("");

    if (!activeWorkId) {
      setState("idle");
      return;
    }

    let cancelled = false;
    setState("loading");
    void getWorkBundle(activeWorkId)
      .then((nextBundle) => {
        if (cancelled) return;
        setBundle(nextBundle);
        const original = originalPlaybackSource(nextBundle);
        const layers = original ? selectLayerSources(nextBundle, original.id) : [];
        setState(layers.length === 4 ? "ready" : "idle");
      })
      .catch(() => {
        if (!cancelled) setState("idle");
      });

    return () => {
      cancelled = true;
      trackingAbortRef.current?.abort();
    };
  }, [activeWorkId]);

  const original = useMemo(() => (bundle ? originalPlaybackSource(bundle) : null), [bundle]);
  const layers = useMemo(
    () => (bundle && original ? selectLayerSources(bundle, original.id) : []),
    [bundle, original],
  );
  const ready = layers.length === 4;

  const hear = useCallback((source: PlaybackSource) => {
    setActiveSource(source);
  }, [setActiveSource]);

  const separate = useCallback(async () => {
    if (!activeWorkId || !projectId || !original || !canProcess) return;

    trackingAbortRef.current?.abort();
    const controller = new AbortController();
    trackingAbortRef.current = controller;
    setState("separating");
    setError(null);
    setMessage("Starting layer separation…");

    try {
      const result = await startLayerSeparation(original.id, projectId);
      const initialJobId = result.job.id;
      if (!initialJobId) throw new Error("Layer separation did not return a durable job.");

      const initialStage = result.job.lifecycle?.current;
      let jobId = initialJobId;
      let alreadySucceeded = initialStage === "succeeded";

      if (initialStage === "failed" || initialStage === "cancelled") {
        const retried = await retryJob(initialJobId);
        jobId = retried.id;
        alreadySucceeded = retried.stage === "succeeded";
      }

      if (!alreadySucceeded) {
        await waitForJob(
          jobId,
          (job) => {
            setMessage(job.message || "Separating layers…");
          },
          { signal: controller.signal },
        );
      }

      invalidateLayerWork();
      const refreshed = await refresh(activeWorkId);
      const refreshedOriginal = originalPlaybackSource(refreshed);
      const refreshedLayers = refreshedOriginal
        ? selectLayerSources(refreshed, refreshedOriginal.id)
        : [];
      if (refreshedLayers.length !== 4) {
        throw new Error("Layer separation finished without a complete four-layer result.");
      }
      setMessage("Layers ready");
      setState("ready");
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      const detail = cause instanceof Error ? cause.message : null;
      setError(
        cause instanceof JobObservationError
          ? cause.message
          : sanitizeJobError(detail) || "Layer separation could not be completed.",
      );
      setMessage("");
      setState("error");
    } finally {
      if (trackingAbortRef.current === controller) trackingAbortRef.current = null;
    }
  }, [activeWorkId, canProcess, original, projectId, refresh]);

  if (!activeWorkId || state === "loading" || !original) return null;

  const rowSources: PlaybackSource[] = ready ? [...layers, original] : [original];
  const separating = state === "separating";

  return (
    <div
      data-testid="experimental-layers"
      style={{
        display: "grid",
        gap: "7px",
        paddingTop: "var(--s-1)",
        borderTop: "1px solid var(--border)",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "8px" }}>
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Layers</span>
        <span
          className="muted"
          style={{ fontSize: "9px", letterSpacing: "0.04em", textTransform: "uppercase" }}
        >
          Experimental
        </span>
      </div>

      {!ready && (
        <button
          type="button"
          className="btn btn-sm"
          disabled={separating || !canProcess || !projectId}
          onClick={() => void separate()}
        >
          {separating ? "Separating layers…" : state === "error" ? "Retry separate layers" : "Separate layers"}
        </button>
      )}

      {(separating || state === "error" || ready) && (
        <div style={{ display: "grid", gap: "5px" }} aria-label="Layer playback sources">
          {rowSources.map((source) => {
            const active = transport.activeSource?.id === source.id;
            return (
              <div
                key={source.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "10px",
                  minHeight: "26px",
                }}
              >
                <span style={{ fontSize: "var(--fs-xs)" }}>{source.label}</span>
                <button
                  type="button"
                  className="btn btn-sm"
                  aria-pressed={active}
                  onClick={() => hear(source)}
                >
                  {active ? "Hearing" : "Hear"}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {message && <span className="muted" role="status" style={{ fontSize: "var(--fs-xs)", lineHeight: 1.35 }}>{message}</span>}
      {error && <span role="alert" style={{ fontSize: "var(--fs-xs)", lineHeight: 1.35 }}>{error} Original remains available.</span>}

      <details>
        <summary className="muted" style={{ cursor: "pointer", fontSize: "10px" }}>Method</summary>
        <span className="muted" style={{ display: "block", paddingTop: "4px", fontSize: "10px", lineHeight: 1.35 }}>
          HTDemucs 955717e8 · CPU · shifts 0. Roles are model-emitted isolation targets, not instrumentation or arrangement claims.
        </span>
      </details>
    </div>
  );
}
