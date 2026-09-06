"use client";

import { useQuery } from "@tanstack/react-query";

import { formatTime } from "@/lib/format";
import { isInspectorExposed } from "@/lib/inspector/capabilities";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import {
  getMeasuredChanges,
  type MeasuredChangeCandidate,
} from "@/lib/relation-api-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace } from "@/lib/stores/workspace";

type MeasuredChangesResultsProps = {
  workId: string;
  sourceVersionId: string;
};

function MeasuredChangesResults({ workId, sourceVersionId }: MeasuredChangesResultsProps) {
  const { setSelection } = useWorkspace();
  const { play, seek } = useTransport();
  const query = useQuery({
    queryKey: ["measured-changes", workId, sourceVersionId],
    queryFn: () => getMeasuredChanges(workId, sourceVersionId),
    staleTime: 60_000,
  });

  const result = query.data;
  const candidates = result?.candidates ?? [];
  if (
    query.isPending
    || query.isError
    || result?.status !== "supported"
    || candidates.length === 0
  ) {
    return null;
  }

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
    seek(Math.max(0, candidate.boundary_seconds - 1.5));
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

      <div aria-live="polite">
        {candidates.map((candidate) => (
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
    </section>
  );
}

export default function MeasuredChanges() {
  const { workspace } = useWorkspace();
  const exposed = isInspectorExposed("measured_change");
  const workId = workspace.activeWorkId;
  const sourceVersionId = workspace.representations.find(
    (representation) => representation.kind === "waveform" && representation.versionId,
  )?.versionId ?? null;

  if (!exposed || !workId || !sourceVersionId) return null;

  return <MeasuredChangesResults workId={workId} sourceVersionId={sourceVersionId} />;
}
