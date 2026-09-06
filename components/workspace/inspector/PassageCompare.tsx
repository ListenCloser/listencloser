"use client";

import { useEffect, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import Disclosure from "@/components/ui/Disclosure";
import { formatTime } from "@/lib/format";
import { isInspectorExposed } from "@/lib/inspector/capabilities";
import { requestWorkspaceOrientation } from "@/lib/inspector/orientation";
import {
  comparePerceptualSpans,
  type PerceptualSpanComparisonResponse,
} from "@/lib/relation-api-client";
import { useTransport } from "@/lib/stores/transport";
import { useWorkspace, type MusicalSelection } from "@/lib/stores/workspace";
import styles from "./InspectorFinding.module.css";

type PassageRange = { start: number; end: number };
type RequestState = "idle" | "loading" | "error";
type SetSelection = (selection: MusicalSelection | null) => void;

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
      return "Measured perceptual evidence is not available for this recording.";
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
  if (!isInspectorExposed("perceptual_series")) return null;

  const workId = workspace.activeWorkId;
  const sourceVersionId = workspace.representations.find(
    (representation) => representation.kind === "waveform" && representation.versionId,
  )?.versionId ?? null;

  if (!workId || !sourceVersionId) return null;

  return (
    <PassageCompareForSource
      key={`${workId}:${sourceVersionId}`}
      workId={workId}
      sourceVersionId={sourceVersionId}
      selectedRange={performanceRange(workspace.selection)}
      setSelection={setSelection}
    />
  );
}

function PassageCompareForSource({
  workId,
  sourceVersionId,
  selectedRange,
  setSelection,
}: {
  workId: string;
  sourceVersionId: string;
  selectedRange: PassageRange | null;
  setSelection: SetSelection;
}) {
  const { seek, transport } = useTransport();
  const requestGeneration = useRef(0);
  const selectedRangeRef = useRef(selectedRange);
  const [referenceRange, setReferenceRange] = useState<PassageRange | null>(null);
  const [result, setResult] = useState<PerceptualSpanComparisonResponse | null>(null);
  const [resultComparisonRange, setResultComparisonRange] = useState<PassageRange | null>(null);
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [requestComparisonRange, setRequestComparisonRange] = useState<PassageRange | null>(null);

  useEffect(() => {
    selectedRangeRef.current = selectedRange;
  }, [selectedRange]);

  if (!referenceRange && !selectedRange) return null;

  const comparisonRange = referenceRange && selectedRange && !sameRange(referenceRange, selectedRange)
    ? selectedRange
    : null;
  const resultMatchesComparison = resultComparisonRange !== null
    && comparisonRange !== null
    && sameRange(resultComparisonRange, comparisonRange);
  const resultAppliesToSelection = resultComparisonRange !== null
    && selectedRange !== null
    && referenceRange !== null
    && (
      sameRange(selectedRange, referenceRange)
      || sameRange(selectedRange, resultComparisonRange)
    );
  const resultForCurrentComparison = resultMatchesComparison ? result : null;
  const resultForCurrentSelection = resultAppliesToSelection ? result : null;
  const groundedFinding = resultForCurrentSelection?.status === "supported"
    ? resultForCurrentSelection.finding
    : null;
  const unavailableMessage = resultForCurrentComparison
    ? unavailableCopy(resultForCurrentComparison.status)
    : null;
  const protocolError = resultForCurrentComparison?.status === "supported"
    && !resultForCurrentComparison.finding
    ? "The comparison response was incomplete and could not be shown."
    : null;
  const requestMatchesComparison = requestComparisonRange !== null
    && comparisonRange !== null
    && sameRange(requestComparisonRange, comparisonRange);
  const requestIsLoading = requestState === "loading" && requestMatchesComparison;
  const requestError = requestState === "error" && requestMatchesComparison
    ? "The comparison request could not be completed."
    : null;

  const invalidatePendingRequest = () => {
    requestGeneration.current += 1;
  };

  const captureReference = () => {
    if (!selectedRange) return;
    invalidatePendingRequest();
    setReferenceRange(selectedRange);
    setResult(null);
    setResultComparisonRange(null);
    setRequestState("idle");
    setRequestComparisonRange(null);
  };

  const resetComparison = () => {
    invalidatePendingRequest();
    setReferenceRange(null);
    setResult(null);
    setResultComparisonRange(null);
    setRequestState("idle");
    setRequestComparisonRange(null);
  };

  const runComparison = async () => {
    if (!referenceRange || !comparisonRange) return;
    const requestedComparisonRange = comparisonRange;
    const generation = requestGeneration.current + 1;
    requestGeneration.current = generation;
    setRequestState("loading");
    setRequestComparisonRange(requestedComparisonRange);
    setResult(null);
    setResultComparisonRange(null);
    try {
      const response = await comparePerceptualSpans(workId, {
        source_version_id: sourceVersionId,
        subject_start_seconds: referenceRange.start,
        subject_end_seconds: referenceRange.end,
        comparison_start_seconds: requestedComparisonRange.start,
        comparison_end_seconds: requestedComparisonRange.end,
      });
      if (requestGeneration.current !== generation) return;

      const liveSelection = selectedRangeRef.current;
      const resultStillApplies = liveSelection !== null && (
        sameRange(liveSelection, referenceRange)
        || sameRange(liveSelection, requestedComparisonRange)
      );
      if (!resultStillApplies) {
        setRequestState("idle");
        setRequestComparisonRange(null);
        return;
      }

      setResult(response);
      setResultComparisonRange(requestedComparisonRange);
      setRequestState("idle");
      setRequestComparisonRange(null);
    } catch {
      if (requestGeneration.current !== generation) return;

      const liveSelection = selectedRangeRef.current;
      if (!liveSelection || !sameRange(liveSelection, requestedComparisonRange)) {
        setRequestState("idle");
        setRequestComparisonRange(null);
        return;
      }

      setRequestState("error");
    }
  };

  const focusRange = (range: PassageRange) => {
    if (transport.activeSource?.role !== "score") {
      seek(range.start);
    }
    setSelection({
      timeRange: { start: range.start, end: range.end, domain: "performance" },
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    requestWorkspaceOrientation();
  };

  return (
    <section className={styles.section} aria-label="Compare passages">
      <div className={styles.heading}>
        <h3>Compare passages</h3>
      </div>

      {!referenceRange ? (
        <div className={styles.sparse}>
          <strong>Use this selection as a reference passage</strong>
          <p>Then select a second passage. The comparison only runs after you explicitly choose both spans.</p>
          <div className={styles.actions}>
            <Button size="compact" variant="ghost" onClick={captureReference}>
              Use selection as reference
            </Button>
          </div>
        </div>
      ) : groundedFinding ? (
        <article className={styles.finding} aria-live="polite">
          <div className={styles.focus}>
            <span className={styles.time}>
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
            <span className={styles.headline}>{groundedFinding.headline}</span>
            <span className={styles.support}>{groundedFinding.evidence_summary}</span>
          </div>

          {groundedFinding.available_actions.includes("evidence") && groundedFinding.measurements.length > 0 && (
            <Disclosure
              className={styles.evidence}
              label={(
                <>
                  <span>Evidence</span>
                  <span className={styles.count}>{groundedFinding.support_refs.length}</span>
                </>
              )}
            >
              <div className={styles.evidenceBody}>
                {groundedFinding.measurements.map((measurement) => (
                  <p key={`${measurement.support_ref.id}:${measurement.feature}`}>{measurement.summary}</p>
                ))}
              </div>
            </Disclosure>
          )}

          <div className={styles.actions} aria-label="Comparison actions">
            <Button
              size="compact"
              variant="ghost"
              onClick={() => focusRange({
                start: groundedFinding.subject_locator.start_seconds,
                end: groundedFinding.subject_locator.end_seconds,
              })}
            >
              Focus A
            </Button>
            <Button
              size="compact"
              variant="ghost"
              onClick={() => focusRange({
                start: groundedFinding.comparison_locator.start_seconds,
                end: groundedFinding.comparison_locator.end_seconds,
              })}
            >
              Focus B
            </Button>
            <Button size="compact" variant="ghost" onClick={resetComparison}>
              New comparison
            </Button>
          </div>
        </article>
      ) : (
        <div className={styles.sparse} aria-live="polite">
          <strong>Reference {passageLabel(referenceRange)}</strong>
          <p>
            {comparisonRange
              ? `Selected passage B: ${passageLabel(comparisonRange)}.`
              : "Select a different exact passage in the Waveform or Piano Roll to use as passage B."}
          </p>
          {unavailableMessage && <p>{unavailableMessage}</p>}
          {protocolError && <p>{protocolError}</p>}
          {requestError && <p>{requestError}</p>}
          <div className={styles.actions}>
            {comparisonRange && (
              <Button
                size="compact"
                variant="ghost"
                disabled={requestIsLoading}
                onClick={runComparison}
              >
                {requestIsLoading ? "Checking evidence…" : "Check against selected passage"}
              </Button>
            )}
            {selectedRange && (
              <Button size="compact" variant="ghost" onClick={captureReference}>
                Replace reference
              </Button>
            )}
            <Button size="compact" variant="ghost" onClick={resetComparison}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
