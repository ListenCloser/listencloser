"use client";

import { useRef, useState } from "react";

import { formatTime } from "@/lib/format";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import {
  getSimilarMoments,
  type SimilarMomentMatch,
  type SimilarMomentsResponse,
} from "@/lib/relation-api-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace, type MusicalSelection } from "@/lib/stores/workspace";

type PassageRange = { start: number; end: number };
type RequestState = "idle" | "loading" | "error";

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

function unavailableCopy(status: SimilarMomentsResponse["status"]): string | null {
  switch (status) {
    case "unavailable":
      return "Measured perceptual evidence is not available for this recording yet.";
    case "withheld":
      return "This selection does not have enough compatible measured evidence for this method.";
    case "failed":
      return "The saved measured evidence could not be validated for Similar moments.";
    default:
      return null;
  }
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

  if (!workId || !sourceVersionId || (!selectedRange && !queryRange)) return null;

  const activeQuery = queryRange ?? selectedRange;
  if (!activeQuery) return null;

  const runSearch = async () => {
    if (!selectedRange) return;
    const captured = selectedRange;
    const requestGeneration = generation.current + 1;
    generation.current = requestGeneration;
    setQueryRange(captured);
    setResult(null);
    setRequestState("loading");
    try {
      const response = await getSimilarMoments(workId, {
        source_version_id: sourceVersionId,
        query_start_seconds: captured.start,
        query_end_seconds: captured.end,
        max_matches: 3,
      });
      if (generation.current !== requestGeneration) return;
      setResult(response);
      setRequestState("idle");
    } catch {
      if (generation.current !== requestGeneration) return;
      setRequestState("error");
    }
  };

  const resetToCurrentSelection = () => {
    generation.current += 1;
    setQueryRange(null);
    setResult(null);
    setRequestState("idle");
  };

  const hear = (startSeconds: number) => {
    const original = transport.sources.find((source) => source.role === "original");
    if (transport.activeSource?.role === "score" && original) {
      setActiveSource(original);
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

  return (
    <section className="inspector-section" aria-label="Similar moments">
      <div className="inspector-section-heading">
        <h3>Similar moments</h3>
        <span className="inspector-breakdown-time">Experimental</span>
      </div>

      <div className="inspector-breakdown-sparse">
        <strong>Selected {passageLabel(activeQuery)}</strong>
        <p>
          Find passages with a similar measured descriptor shape in this recording. Results are
          listening proposals under one method, not motif, chorus, melody, or section labels.
        </p>
        <div className="inspector-breakdown-actions">
          <button
            type="button"
            className="inspector-breakdown-action"
            disabled={!selectedRange || requestState === "loading"}
            onClick={runSearch}
          >
            {requestState === "loading" ? "Finding similar moments…" : "Find similar moments"}
          </button>
          {queryRange && (
            <button
              type="button"
              className="inspector-breakdown-action"
              onClick={() => hear(queryRange.start)}
            >
              Hear selected
            </button>
          )}
          {queryRange && selectedRange && (
            <button
              type="button"
              className="inspector-breakdown-action"
              onClick={resetToCurrentSelection}
            >
              Use current selection
            </button>
          )}
        </div>
        {requestState === "error" && (
          <p aria-live="polite">Similar moments could not be loaded.</p>
        )}
        {statusCopy && <p aria-live="polite">{statusCopy}</p>}
      </div>

      {observation?.matches.length === 0 ? (
        <div className="inspector-breakdown-sparse" aria-live="polite">
          <p>No valid non-overlapping candidate window fits this selection.</p>
          <p>This experimental method does not yet use a semantic no-match threshold.</p>
        </div>
      ) : observation ? (
        <div aria-live="polite">
          {observation.matches.map((match, index) => (
            <article
              className="inspector-breakdown-finding"
              key={`${observation.evidence_report_version_id}:${match.start_seconds}`}
            >
              <div className="inspector-breakdown-focus">
                <span className="inspector-breakdown-time">
                  {passageLabel({ start: match.start_seconds, end: match.end_seconds })}
                </span>
                <span className="inspector-breakdown-headline">
                  Similar proposal {index + 1}
                </span>
                <span className="inspector-breakdown-support">
                  Similar under the declared descriptor-shape method; lower distance means closer
                  only under this method.
                </span>
              </div>

              <details className="inspector-evidence-group">
                <summary>
                  <span>Method & evidence</span>
                  <span className="inspector-evidence-count">{observation.method.dimensions.length}</span>
                </summary>
                <div className="inspector-evidence-body">
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
              </details>

              <div className="inspector-breakdown-actions" aria-label={`Similar proposal ${index + 1} actions`}>
                <button
                  type="button"
                  className="inspector-breakdown-action"
                  onClick={() => hear(match.start_seconds)}
                >
                  Hear
                </button>
                <button
                  type="button"
                  className="inspector-breakdown-action"
                  onClick={() => focus(match)}
                >
                  Focus
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
