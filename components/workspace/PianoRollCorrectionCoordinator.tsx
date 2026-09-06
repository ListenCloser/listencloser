"use client";

import { useEffect, useRef } from "react";
import { clearWorkDataCache, getWorkBundle } from "@/lib/api-client";
import { startCorrectWorkflow } from "@/lib/correction-client";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import { resolveMidiAuthority } from "@/lib/midi-authority";
import { useWorkspace } from "@/lib/stores/workspace";

export default function PianoRollCorrectionCoordinator() {
  const {
    clearSelection,
    selectPianoRollSource,
    setPianoRollCorrectionOperation,
    workspace,
  } = useWorkspace();
  const handledAction = useRef(0);

  useEffect(() => {
    const action = workspace.pianoRollCorrectionAction;
    const workId = workspace.activeWorkId;
    if (!action) {
      // Work changes clear the correction action. Reset the local de-duplication
      // guard too, because action ids intentionally restart from 1 in the new
      // Work's isolated correction state.
      handledAction.current = 0;
      return;
    }
    if (action.id === handledAction.current || !workId) return;
    handledAction.current = action.id;
    let cancelled = false;

    void (async () => {
      setPianoRollCorrectionOperation({
        state: "running",
        label: "Saving transcription correction",
        message: "Queued",
      });
      try {
        // Resolve the project from the exact active Work at mutation time. This
        // avoids ambient Library-project state and keeps passive representation
        // rendering free of a React Query dependency.
        const bundle = await getWorkBundle(workId);
        if (cancelled) return;
        const { jobId } = await startCorrectWorkflow(
          action.sourceVersionId,
          bundle.work.project_id,
          action.replacement,
        );
        const completed = await waitForJob(jobId, (current) => {
          if (cancelled) return;
          setPianoRollCorrectionOperation({
            state: "running",
            label: "Saving transcription correction",
            message: current.message || "Saving",
          });
        });
        if (cancelled) return;

        // Correction may also publish exact-parent synthesized playback. Never
        // infer which output is the performance interpretation by array order;
        // refresh durable state and resolve the one edited-performance MIDI
        // Version produced by this exact Job.
        clearWorkDataCache();
        const refreshed = await getWorkBundle(workId);
        if (cancelled) return;
        const outputIds = new Set(completed.output_version_ids);
        const correctedOutputs = resolveMidiAuthority(refreshed).representations.filter(
          (descriptor) => (
            descriptor.role === "edited_performance"
            && outputIds.has(descriptor.versionId)
            && descriptor.artifact.latest_version?.produced_by_job_id === jobId
          ),
        );
        if (correctedOutputs.length !== 1) {
          throw new Error("Correction did not produce one exact performance interpretation.");
        }

        clearSelection();
        selectPianoRollSource(correctedOutputs[0].versionId);
        setPianoRollCorrectionOperation({
          state: "success",
          label: "Correction saved",
          message: "Corrected transcription is now the active Piano Roll interpretation.",
        });
      } catch (cause) {
        if (cancelled) return;
        const disconnected = cause instanceof JobObservationError;
        setPianoRollCorrectionOperation({
          state: disconnected ? "disconnected" : "error",
          label: disconnected ? "Correction status interrupted" : "Couldn’t save correction",
          message: cause instanceof Error ? cause.message : "Please try again.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    clearSelection,
    selectPianoRollSource,
    setPianoRollCorrectionOperation,
    workspace.activeWorkId,
    workspace.pianoRollCorrectionAction,
  ]);

  return null;
}
