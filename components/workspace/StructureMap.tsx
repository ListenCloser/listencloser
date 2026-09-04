"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clearWorkDataCache, getJob, getWorkBundle } from "@/lib/api-client";
import { formatTime } from "@/lib/format";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";
import {
  fetchStructureMapReport,
  startStructureMapWorkflow,
  type StructureMapReport,
  type StructureMapSpan,
} from "@/lib/structure-map-client";
import styles from "./StructureMap.module.css";

const POLL_MS = 1000;
const MAX_POLLS = 180;
const ACTIVE_JOB_STAGES = new Set(["queued", "claimed", "running"]);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
  return { sourceVersionId, report, job };
}

export default function StructureMap() {
  const { workspace, setSelection } = useWorkspace();
  const { transport, seek, play, setActiveSource, audioRef } = useTransport();
  const [report, setReport] = useState<StructureMapReport | null>(null);
  const [sourceVersionId, setSourceVersionId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [chooserOpen, setChooserOpen] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "generating">("idle");
  const [error, setError] = useState<string | null>(null);
  const sequenceRef = useRef(0);

  const load = useCallback(async (workId: string, fresh = false) => {
    const sequence = ++sequenceRef.current;
    setStatus("loading");
    setError(null);
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
        if (resolved.job?.lifecycle.current === "failed") {
          setChooserOpen(true);
          setError(resolved.job.error || resolved.job.lifecycle.message || "Structure Map processing failed");
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
    if (workId) void load(workId);
  }, [load, workspace.activeWorkId]);

  useEffect(() => {
    const workId = workspace.activeWorkId;
    const jobId = activeJobId;
    if (!workId || !jobId) return;
    let cancelled = false;

    void (async () => {
      try {
        for (let poll = 0; poll < MAX_POLLS; poll += 1) {
          await sleep(POLL_MS);
          if (cancelled) return;
          const job = await getJob(jobId);
          if (job.stage === "succeeded") {
            setActiveJobId(null);
            await load(workId, true);
            return;
          }
          if (job.stage === "failed" || job.stage === "cancelled") {
            setActiveJobId(null);
            setStatus("idle");
            setChooserOpen(true);
            setError(job.error ?? "Structure Map processing did not complete");
            return;
          }
        }
        if (!cancelled) {
          setActiveJobId(null);
          setStatus("idle");
          setChooserOpen(true);
          setError("Structure Map processing is taking longer than expected");
        }
      } catch (cause) {
        if (cancelled) return;
        setActiveJobId(null);
        setStatus("idle");
        setChooserOpen(true);
        setError(cause instanceof Error ? cause.message : "Structure Map processing failed");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeJobId, load, workspace.activeWorkId]);

  const generate = useCallback(async () => {
    if (!workspace.activeWorkId || !sourceVersionId || !projectId || status === "generating") return;
    setStatus("generating");
    setError(null);
    setChooserOpen(true);
    try {
      const jobId = await startStructureMapWorkflow(sourceVersionId, projectId);
      setActiveJobId(jobId);
    } catch (cause) {
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "Structure Map processing failed");
    }
  }, [projectId, sourceVersionId, status, workspace.activeWorkId]);

  const focusSpan = useCallback((span: StructureMapSpan, shouldPlay: boolean) => {
    const focus = () => {
      seek(span.start_seconds);
      if (shouldPlay) play();
    };
    const originalSource = transport.sources.find((source) => source.role === "original");

    // Structure Map spans are exact performance-time locators for the source
    // audio Version. Score playback uses notation time, so a map jump must not
    // reinterpret these seconds against the score timeline. Switch back to the
    // exact source audio before seeking; the transport's own loadedmetadata
    // handler runs first, then this handler applies the requested locator.
    if (transport.activeSource?.role === "score" && originalSource && audioRef.current) {
      const audio = audioRef.current;
      setActiveSource(originalSource);
      audio.addEventListener("loadedmetadata", focus, { once: true });
    } else if (transport.activeSource?.role !== "score") {
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

  if (!report) {
    return (
      <section className={styles.discovery} aria-label="Add analysis">
        {!chooserOpen && status !== "loading" ? (
          <button type="button" className={styles.addAnalysis} onClick={() => setChooserOpen(true)}>
            + Add analysis
          </button>
        ) : chooserOpen ? (
          <div className={styles.chooser}>
            <div className={styles.chooserHeader}>
              <strong>Add analysis</strong>
              {status !== "generating" && (
                <button type="button" className={styles.closeChooser} onClick={() => setChooserOpen(false)} aria-label="Close analysis chooser">×</button>
              )}
            </div>
            <div className={styles.choice}>
              <div>
                <div className={styles.titleLine}>
                  <strong>Structure Map</strong>
                  <span className={styles.experimental}>Experimental</span>
                </div>
                <p>Find rough candidate spans so you can jump through the recording&apos;s shape.</p>
              </div>
              <button type="button" className={styles.generate} onClick={() => void generate()} disabled={status === "generating"}>
                {status === "generating" ? "Finding shape…" : error ? "Retry" : "Add"}
              </button>
            </div>
            {error && <p className={styles.error} role="alert">{error}</p>}
          </div>
        ) : null}
      </section>
    );
  }

  return (
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
          return (
            <div className={`${styles.row}${active ? ` ${styles.active}` : ""}`} key={`${span.start_seconds}-${index}`}>
              <button type="button" className={styles.jump} onClick={() => focusSpan(span, false)} aria-current={active ? "true" : undefined}>
                <strong>{span.label}</strong>
                <span>{formatTime(span.start_seconds)}–{formatTime(span.end_seconds)}</span>
              </button>
              <button type="button" className={styles.hear} onClick={() => focusSpan(span, true)} aria-label={`Hear ${span.label} from ${formatTime(span.start_seconds)}`}>
                Hear
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
  );
}
