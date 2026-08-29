"use client";

import { useEffect, useRef, useState } from "react";
import { formatTime } from "@/lib/format";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import {
  comparePerceptualSpans,
  type PerceptualSpanComparisonResponse,
} from "@/lib/relation-api-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace, type MusicalSelection } from "@/lib/stores/workspace";

type PassageRange = { start: number; end: number };
type RequestState = "idle" | "loading" | "error";

function performanceRange(selection: MusicalSelection | null): PassageRange | null {
  const range = selection?.timeRange;
  if (!range || range.domain !== "performance" || selection?.provenance.timeExact !== true) return null;
  if (!Number.isFinite(range.start) || !Number.isFinite(range.end)) return null;
  if (range.start < 0 || range.end <= range.start) return null;
  return { start: range.start, end: range.end };
}

function sameRange(left: PassageRange, right: PassageRange): boolean {
  return Math.abs(left.start - right.start) < 1e-6 && Math.abs(left.end - right.end) < 1e-6;
}

function passageLabel(range: PassageRange): string {
  return `${formatTime(range.start)}–${formatTime(range.end)}`;
}

function unavailableCopy(status: PerceptualSpanComparisonResponse["status"]): string | null {
  switch (status) {
    case "unavailable":
      return "Measured perceptual evidence is not available for this recording yet.";
    case "withheld":
      return "These passages do not have enough validated evidence for a grounded comparison.";
    case "failed":
      return "The saved evidence could not be validated for this comparison.";
    default:
      return null;
  }
}

export default function PassageCompare() {
  const { workspace, setSelection } = useWorkspace();
  const { seek } = useTransport();
  const workId = workspace.activeWorkId;
  const sourceVersionId = workspace.representations.find(
    (representation) => representation.kind === "waveform" && representation.versionId,
  )?.versionId ?? null;
  const selectedRange = performanceRange(workspace.selection);
  const contextKey = `${workId ?? ""}:${sourceVersionId ?? ""}`;
  const latestContextKey = useRef(contextKey);
  const [referenceRange, setReferenceRange] = useState<PassageRange | null>(null);
  const [result, setResult] = useState<PerceptualSpanComparisonResponse | null>(null);
  const [requestState, setRequestState] = useState<RequestState>("idle");

  useEffect(() => {
    latestContextKey.current = contextKey;
    setReferenceRange(null);
    setResult(null);
    setRequestState("idle");
  }, [contextKey]);

  if (!workId || !sourceVersionId || (!referenceRange && !selectedRange)) return null;

  const comparisonRange = referenceRange && selectedRange && !sameRange(referenceRange, selectedRange)
    ? selectedRange
    : null;
  const groundedFinding = result?.status === "supported" ? result.finding : null;
  const unavailableMessage = result ? unavailableCopy(result.status) : null;

  const captureReference = () => {
    if (!selectedRange) return;
    setReferenceRange(selectedRange);
    setResult(null);
    setRequestState("idle");
  };

  const resetComparison = () => {
    setReferenceRange(null);
    setResult(null);
    setRequestState("idle");
  };

  const runComparison = async () => {
    if (!referenceRange || !comparisonRange) return;
    const requestContextKey = contextKey;
    setRequestState("loading");
    setResult(null);
    try {
      const response = await comparePerceptualSpans(workId, {
        source_version_id: sourceVersionId,
        subject_start_seconds: referenceRange.start,
        subject_end_seconds: referenceRange.end,
        comparison_start_seconds: comparisonRange.start,
        comparison_end_seconds: comparisonRange.end,
      });
      if (latestContextKey.current !== requestContextKey) return;
      setResult(response);
      setRequestState("idle");
    } catch {
      if (latestContextKey.current !== requestContextKey) return;
      setRequestState("error");
    }
  };

  const focusRange = (range: PassageRange) => {
    seek(range.start);
    setSelection({
      timeRange: { start: range.start, end: range.end, domain: "performance" },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    requestWorkspaceOrientation();
  };

  return (
    <section className="inspector-section" aria-label="Compare passages">
      <div className="inspector-section-heading">
        <h3>Compare passages</h3>
      </div>

      {!referenceRange ? (
        <div className="inspector-breakdown-sparse">
          <strong>Use this selection as a reference passage</strong>
          <p>Then select a second passage. The comparison only runs after you explicitly choose both spans.</p>
          <div className="inspector-breakdown-actions">
            <button type="button" className="inspector-breakdown-action" onClick={captureReference}>
              Use selection as reference
            </button>
          </div>
        </div>
      ) : groundedFinding ? (
        <article className="inspector-breakdown-finding" aria-live="polite">
          <div className="inspector-breakdown-focus">
            <span className="inspector-breakdown-time">
              {passageLabel({
                start: groundedFinding.subject_locator.start_seconds,
                end: groundedFinding.subject_locator.end_seconds,
              })}
              {" ↔ "}
              {passageLabel({
                start: groundedFinding.comparison_locator.start_seconds,
                end: groundedFinding.comparison_locator.end_seconds,
              })}
            </span>
            <span className="inspector-breakdown-headline">{groundedFinding.headline}</span>
            <span className="inspector-breakdown-support">{groundedFinding.evidence_summary}</span>
          </div>

          {groundedFinding.available_actions.includes("evidence") && groundedFinding.measurements.length > 0 && (
            <details className="inspector-evidence-group">
              <summary>
                <span>Evidence</span>
                <span className="inspector-evidence-count">{groundedFinding.support_refs.length}</span>
              </summary>
              <div className="inspector-evidence-body">
                {groundedFinding.measurements.map((measurement) => (
                  <p key={`${measurement.support_ref.id}:${measurement.feature}`}>{measurement.summary}</p>
                ))}
              </div>
            </details>
          )}

          <div className="inspector-breakdown-actions" aria-label="Comparison actions">
            <button
              type="button"
              className="inspector-breakdown-action"
              onClick={() => focusRange({
                start: groundedFinding.subject_locator.start_seconds,
                end: groundedFinding.subject_locator.end_seconds,
              })}
            >
              Focus A
            </button>
            <button
              type="button"
              className="inspector-breakdown-action"
              onClick={() => focusRange({
                start: groundedFinding.comparison_locator.start_seconds,
                end: groundedFinding.comparison_locator.end_seconds,
              })}
            >
              Focus B
            </button>
            <button type="button" className="inspector-breakdown-action" onClick={resetComparison}>
              New comparison
            </button>
          </div>
        </article>
      ) : (
        <div className="inspector-breakdown-sparse" aria-live="polite">
          <strong>Reference {passageLabel(referenceRange)}</strong>
          <p>
            {comparisonRange
              ? `Selected passage B: ${passageLabel(comparisonRange)}.`
              : "Select a different exact passage in the Waveform or Piano Roll to use as passage B."}
          </p>
          {unavailableMessage && <p>{unavailableMessage}</p>}
          {requestState === "error" && <p>The comparison request could not be completed.</p>}
          <div className="inspector-breakdown-actions">
            {comparisonRange && (
              <button
                type="button"
                className="inspector-breakdown-action"
                disabled={requestState === "loading"}
                onClick={runComparison}
              >
                {requestState === "loading" ? "Checking evidence…" : "Check against selected passage"}
              </button>
            )}
            {selectedRange && (
              <button type="button" className="inspector-breakdown-action" onClick={captureReference}>
                Replace reference
              </button>
            )}
            <button type="button" className="inspector-breakdown-action" onClick={resetComparison}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
