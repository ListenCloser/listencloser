"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "@/components/AuthProvider";
import { clearWorkDataCache } from "@/lib/api-client";
import { startCorrectWorkflow } from "@/lib/correction-client";
import { JobObservationError, waitForJob } from "@/lib/job-tracking";
import { useLibraryProject } from "@/lib/server-state";
import { useWorkspace } from "@/lib/stores/workspace";

export default function PianoRollCorrectionCoordinator() {
  const { user } = useAuth();
  const projectQuery = useLibraryProject(user?.id ?? "");
  const projectId = projectQuery.data?.id ?? "";
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
    if (action.id === handledAction.current || !projectId || !workId) return;
    handledAction.current = action.id;
    let cancelled = false;

    void (async () => {
      setPianoRollCorrectionOperation({
        state: "running",
        label: "Saving transcription correction",
        message: "Queued",
      });
      try {
        const { jobId } = await startCorrectWorkflow(
          action.sourceVersionId,
          projectId,
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
        if (completed.output_version_ids.length !== 1) {
          throw new Error("Correction did not produce exactly one performance interpretation.");
        }

        const correctedVersionId = completed.output_version_ids[0];
        clearWorkDataCache();
        clearSelection();
        selectPianoRollSource(correctedVersionId);
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
    projectId,
    selectPianoRollSource,
    setPianoRollCorrectionOperation,
    workspace.activeWorkId,
    workspace.pianoRollCorrectionAction,
  ]);

  return null;
}
