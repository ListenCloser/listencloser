"use client";

import { useQuery } from "@tanstack/react-query";

import { formatTime } from "@/lib/format";
import { isInspectorExposed } from "@/lib/inspector/capabilities";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import {
  getMeasuredChanges,
  type MeasuredChangeCandidate,
  type MeasuredChangeQueryResponse,
} from "@/lib/relation-api-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

function unavailableCopy(status: MeasuredChangeQueryResponse["status"]): string | null {
  switch (status) {
    case "unavailable":
      return "Measured perceptual evidence is not available for this recording yet.";
    case "withheld":
      return "This recording does not have enough compatible measured evidence for change candidates.";
    case "failed":
      return "The saved measured evidence could not be validated for change navigation.";
    default:
      return null;
  }
}

export default function MeasuredChanges() {
  const { workspace, setSelection } = useWorkspace();
  const { transport, audioRef, play, seek, setActiveSource } = useTransport();

  if (!isInspectorExposed("measured_change")) return null;

  const workId = workspace.activeWorkId;
  const sourceVersionId = workspace.representations.find(
    (representation) => representation.kind === "waveform" && representation.versionId,
  )?.versionId ?? null;

  const query = useQuery({
    queryKey: ["measured-changes", workId, sourceVersionId],
    queryFn: () => getMeasuredChanges(workId!, sourceVersionId!),
    enabled: Boolean(workId && sourceVersionId),
    staleTime: 60_000,
  });

  if (!workId || !sourceVersionId) return null;

  const result = query.data;
  const statusCopy = result ? unavailableCopy(result.status) : null;

  const inspect = (candidate: MeasuredChangeCandidate) => {
    setSelection({
      timeRange: {
        start: candidate.before_span_seconds[0],
        end: candidate.after_span_seconds[1],
        domain: "performance",
      },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    requestWorkspaceOrientation();
  };

  const hear = (candidate: MeasuredChangeCandidate) => {
    const target = Math.max(0, candidate.boundary_seconds - 1.5);
    const original = transport.sources.find((source) => source.role === "original");

    if (transport.activeSource?.role === "score" && original) {
      setActiveSource(original);
      const audio = audioRef.current;
      if (audio) {
        audio.addEventListener(
          "loadedmetadata",
          () => {
            seek(target);
            play();
          },
          { once: true },
        );
        return;
      }
    }

    seek(target);
    play();
  };

  return (
    <section className="inspector-section" aria-label="Measured changes">
      <div className="inspector-section-heading">
        <h3>Changes</h3>
        <span className="inspector-breakdown-time">Experimental</span>
      </div>

      <div className="inspector-breakdown-sparse">
        <p>
          Multiple measured features changed around these times. These are listening candidates,
          not section boundaries or claims about musical importance.
        </p>
      </div>

      {query.isPending ? (
        <div className="inspector-breakdown-sparse" aria-live="polite">
          <p>Finding measured changes…</p>
        </div>
      ) : query.isError ? (
        <div className="inspector-breakdown-sparse" aria-live="polite">
          <p>Measured changes could not be loaded.</p>
        </div>
      ) : statusCopy ? (
        <div className="inspector-breakdown-sparse" aria-live="polite">
          <p>{statusCopy}</p>
        </div>
      ) : result?.status === "supported" && result.candidates.length === 0 ? (
        <div className="inspector-breakdown-sparse" aria-live="polite">
          <p>No bounded measured-change candidates were found for this recording.</p>
        </div>
      ) : result?.status === "supported" ? (
        <div aria-live="polite">
          {result.candidates.map((candidate) => (
            <article
              key={`${sourceVersionId}:${candidate.boundary_seconds}`}
              className="inspector-breakdown-finding"
            >
              <div className="inspector-breakdown-focus">
                <span className="inspector-breakdown-time">
                  {formatTime(candidate.boundary_seconds)}
                </span>
                <span className="inspector-breakdown-headline">Measured change</span>
                <span className="inspector-breakdown-support">
                  {candidate.changed_feature_count} measured feature groups changed under this method.
                </span>
              </div>

              {candidate.finding.measurements.length > 0 && (
                <details className="inspector-evidence-group">
                  <summary>
                    <span>Evidence</span>
                    <span className="inspector-evidence-count">
                      {candidate.finding.support_refs.length}
                    </span>
                  </summary>
                  <div className="inspector-evidence-body">
                    {candidate.finding.measurements.map((measurement) => (
                      <p key={`${measurement.support_ref.id}:${measurement.feature}`}>
                        {measurement.summary}
                      </p>
                    ))}
                    <p>
                      Method: {result.method ?? "measured change"}. Ranking is only within this
                      recording and is not confidence or importance.
                    </p>
                  </div>
                </details>
              )}

              <div className="inspector-breakdown-actions" aria-label="Measured change actions">
                <button
                  type="button"
                  className="inspector-breakdown-action"
                  onClick={() => hear(candidate)}
                >
                  Hear
                </button>
                <button
                  type="button"
                  className="inspector-breakdown-action"
                  onClick={() => inspect(candidate)}
                >
                  Inspect
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
