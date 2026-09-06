"use client";

import { useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Disclosure from "@/components/ui/Disclosure";
import { getWorkBundle } from "@/lib/api-client";
import { formatTime } from "@/lib/format";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import { waitForJob } from "@/lib/job-tracking";
import { startPerceptualSeriesWorkflow } from "@/lib/perceptual-series-client";
import {
  getSimilarMoments,
  type SimilarMomentMatch,
  type SimilarMomentsResponse,
} from "@/lib/relation-api-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace, type MusicalSelection } from "@/lib/stores/workspace";
import styles from "./InspectorFinding.module.css";

type PassageRange = { start: number; end: number };
type RequestState = "idle" | "searching" | "preparing" | "error";

const RANGE_EQUALITY_EPSILON_SECONDS = 0.05;

function performanceRange(selection: MusicalSelection | null): PassageRange | null {
  const range = selection?.timeRange;
  if (!range || range.domain !== "performance" || selection?.provenance.timeExact !== true) {
    return null;
  }
  if (!Number.isFinite(range.start) || !Number.isFinite(range.end)) return null;
  if (range.start < 0 || range.end <= range.start) return null;
  return { start: range.start, end: range.end };
}

function passageLabel(range: PassageRange): string {
  return `${formatTime(range.start)}–${formatTime(range.end)}`;
}

function rangesMatch(a: PassageRange, b: PassageRange): boolean {
  return (
    Math.abs(a.start - b.start) <= RANGE_EQUALITY_EPSILON_SECONDS
    && Math.abs(a.end - b.end) <= RANGE_EQUALITY_EPSILON_SECONDS
  );
}

function unavailableCopy(status: SimilarMomentsResponse["status"]): string | null {
  switch (status) {
    case "unavailable":
      return "Similarity analysis is not available for this recording yet.";
    case "withheld":
      return "This selection does not have enough compatible measured evidence for this method.";
    case "failed":
      return "The saved measured evidence could not be validated for Similar moments.";
    default:
      return null;
  }
}

function searchButtonLabel(state: RequestState): string {
  if (state === "preparing") return "Preparing similarity analysis…";
  if (state === "searching") return "Finding similar moments…";
  return "Find similar moments";
}

export default function SimilarMoments() {
  const { workspace, setSelection } = useWorkspace();
  const { transport, audioRef, play, seek, setActiveSource } = useTransport();
  const generation = useRef(0);
  const selectedRange = performanceRange(workspace.selection);
  const workId = workspace.activeWorkId;
  const sourceVersionId = workspace.representations.find(
    (representation) => representation.kind === "waveform" && representation.versionId,
  )?.versionId ?? null;
  const [queryRange, setQueryRange] = useState<PassageRange | null>(null);
  const [result, setResult] = useState<SimilarMomentsResponse | null>(null);
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!workId || !sourceVersionId || (!selectedRange && !queryRange)) return null;

  const activeQuery = queryRange ?? selectedRange;
  if (!activeQuery) return null;

  const originalSource = transport.sources.find((source) => source.role === "original");
  const hearingRequiresOriginal = transport.activeSource?.role === "score";
  const canHear = !hearingRequiresOriginal || Boolean(originalSource);
  const busy = requestState === "searching" || requestState === "preparing";

  const querySimilarMoments = (captured: PassageRange) => getSimilarMoments(workId, {
    source_version_id: sourceVersionId,
    query_start_seconds: captured.start,
    query_end_seconds: captured.end,
    max_matches: 3,
  });

  const runSearch = async () => {
    const captured = queryRange ?? selectedRange;
    if (!captured) return;
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    const isCurrentRequest = () => generation.current === requestGeneration;
    let preparingDependency = false;
    setQueryRange(captured);
    setResult(null);
    setErrorMessage(null);
    setRequestState("searching");

    try {
      let response = await querySimilarMoments(captured);
      if (!isCurrentRequest()) return;

      if (response.status === "unavailable") {
        preparingDependency = true;
        setRequestState("preparing");
        const bundle = await getWorkBundle(workId);
        if (!isCurrentRequest()) return;
        const jobId = await startPerceptualSeriesWorkflow(
          sourceVersionId,
          bundle.work.project_id,
        );
        if (!isCurrentRequest()) return;
        await waitForJob(jobId, () => undefined);
        if (!isCurrentRequest()) return;
        setRequestState("searching");
        response = await querySimilarMoments(captured);
        if (!isCurrentRequest()) return;
      }

      setResult(response);
      setRequestState("idle");
    } catch {
      if (!isCurrentRequest()) return;
      setRequestState("error");
      setErrorMessage(
        preparingDependency
          ? "Similarity analysis could not be prepared. Try again."
          : "Similar moments could not be loaded. Try again.",
      );
    }
  };

  const resetToCurrentSelection = () => {
    generation.current += 1;
    setQueryRange(null);
    setResult(null);
    setErrorMessage(null);
    setRequestState("idle");
  };

  const hear = (startSeconds: number) => {
    if (hearingRequiresOriginal) {
      if (!originalSource) return;
      setActiveSource(originalSource);
      const audio = audioRef.current;
      if (audio) {
        audio.addEventListener(
          "loadedmetadata",
          () => {
            seek(startSeconds);
            play();
          },
          { once: true },
        );
        return;
      }
    }
    seek(startSeconds);
    play();
  };

  const focus = (match: SimilarMomentMatch) => {
    if (transport.activeSource?.role !== "score") seek(match.start_seconds);
    setSelection({
      timeRange: {
        start: match.start_seconds,
        end: match.end_seconds,
        domain: "performance",
      },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    requestWorkspaceOrientation();
  };

  const observation = result?.status === "supported" ? result.observation : null;
  const statusCopy = result ? unavailableCopy(result.status) : null;
  const currentSelectionDiffers = Boolean(
    queryRange && selectedRange && !rangesMatch(queryRange, selectedRange),
  );

  return (
    <section className={styles.section} aria-label="Similar moments">
      <div className={styles.heading}>
        <h3>Similar moments</h3>
        <span className={styles.experimental}>Experimental</span>
      </div>

      <div className={styles.sparse}>
        <strong>Selected {passageLabel(activeQuery)}</strong>
        <p>Find other passages with a similar measured shape. These are listening proposals, not motif or section labels.</p>
        <div className={styles.actions}>
          <Button size="compact" variant="ghost" disabled={busy} onClick={runSearch}>
            {searchButtonLabel(requestState)}
          </Button>
          <Button
            size="compact"
            variant="ghost"
            disabled={!canHear}
            onClick={() => hear(activeQuery.start)}
          >
            {hearingRequiresOriginal ? "Hear selected · Original" : "Hear selected"}
          </Button>
          {currentSelectionDiffers && (
            <Button size="compact" variant="ghost" onClick={resetToCurrentSelection}>
              Use current selection
            </Button>
          )}
        </div>
        {requestState === "preparing" && (
          <p aria-live="polite">Preparing the recording for similarity search…</p>
        )}
        {errorMessage && <p aria-live="polite">{errorMessage}</p>}
        {statusCopy && <p aria-live="polite">{statusCopy}</p>}
      </div>

      {observation?.matches.length === 0 ? (
        <div className={styles.sparse} aria-live="polite">
          <p>No valid non-overlapping candidate window fits this selection.</p>
          <p>This experimental method does not yet use a semantic no-match threshold.</p>
        </div>
      ) : observation ? (
        <div aria-live="polite">
          {observation.matches.map((match, index) => (
            <article
              className={styles.finding}
              key={`${observation.evidence_report_version_id}:${match.start_seconds}`}
            >
              <div className={styles.focus}>
                <span className={styles.time}>
                  {passageLabel({ start: match.start_seconds, end: match.end_seconds })}
                </span>
                <span className={styles.headline}>
                  Similar proposal {index + 1}
                </span>
                <span className={styles.support}>
                  Similar under the declared descriptor-shape method; lower distance means closer
                  only under this method.
                </span>
              </div>

              <Disclosure
                className={styles.evidence}
                label={(
                  <>
                    <span>Method & evidence</span>
                    <span className={styles.count}>{observation.method.dimensions.length}</span>
                  </>
                )}
              >
                <div className={styles.evidenceBody}>
                  <p>
                    Aggregate distance: {match.distance.toFixed(3)}. This value is not confidence.
                  </p>
                  {Object.entries(match.component_distances).map(([dimension, distance]) => (
                    <p key={dimension}>{dimension}: {distance.toFixed(3)}</p>
                  ))}
                  <p>
                    Method: {observation.method.id} v{observation.method.version}; candidate windows
                    use the same evidence-frame count as the selected passage and exclude overlap.
                  </p>
                  <p>Evidence Version: {observation.evidence_report_version_id}</p>
                  <p>Source Version: {observation.source_version_id}</p>
                </div>
              </Disclosure>

              <div className={styles.actions} aria-label={`Similar proposal ${index + 1} actions`}>
                <Button
                  size="compact"
                  variant="ghost"
                  disabled={!canHear}
                  onClick={() => hear(match.start_seconds)}
                >
                  {hearingRequiresOriginal ? "Hear original" : "Hear"}
                </Button>
                <Button size="compact" variant="ghost" onClick={() => focus(match)}>
                  Focus
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
