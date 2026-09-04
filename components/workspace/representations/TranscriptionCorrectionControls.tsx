"use client";

import { useEffect, useMemo, useState } from "react";

import { getWorkBundle } from "@/lib/api-client";
import { waitForJob } from "@/lib/job-tracking";
import { selectScoreArtifacts } from "@/lib/score-artifacts";
import { useWorkspace } from "@/lib/stores/workspace";
import {
  buildCorrectionPayload,
  regenerateFromCorrected,
  startCorrectionWorkflow,
  type CorrectionNote,
  type NoteCorrectionOperation,
} from "@/lib/transcription-correction";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The transcription edit could not be saved.";
}

export default function TranscriptionCorrectionControls({ notes }: { notes: CorrectionNote[] }) {
  const { workspace, clearSelection } = useWorkspace();
  const [editing, setEditing] = useState(false);
  const [operation, setOperation] = useState<"remove" | "pitch" | "add">("pitch");
  const [pitch, setPitch] = useState(60);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editedSource, setEditedSource] = useState(false);
  const [hasCurrentScore, setHasCurrentScore] = useState(false);
  const [sourceParentId, setSourceParentId] = useState<string | null>(null);

  const pianoRoll = workspace.representations.find((item) => item.kind === "piano_roll");
  const sourceVersionId = pianoRoll?.versionId ?? null;
  const selection = workspace.selection;
  const performanceRange = selection?.timeRange?.domain === "performance" ? selection.timeRange : null;
  const selectedIds = selection?.noteIds ?? [];
  const selectedNotes = useMemo(
    () => notes.filter((note) => note.id && selectedIds.includes(note.id)),
    [notes, selectedIds],
  );
  const selectedNote = selectedNotes.length === 1 ? selectedNotes[0] : null;

  useEffect(() => {
    if (selectedNote) setPitch(selectedNote.pitch);
  }, [selectedNote]);

  useEffect(() => {
    let cancelled = false;
    const workId = workspace.activeWorkId;
    if (!workId || !sourceVersionId) {
      setEditedSource(false);
      setHasCurrentScore(false);
      setSourceParentId(null);
      return;
    }
    void getWorkBundle(workId).then((bundle) => {
      if (cancelled) return;
      const source = bundle.artifacts
        .flatMap((item) => item.versions)
        .find((version) => version.id === sourceVersionId)
        ?? bundle.artifacts.find((item) => item.latest_version?.id === sourceVersionId)?.latest_version;
      const role = source?.metadata?.representation_role;
      const isEdited = role === "edited_performance";
      setEditedSource(isEdited);
      setSourceParentId(isEdited ? source?.parent_version_id ?? null : null);
      setHasCurrentScore(
        isEdited
          ? selectScoreArtifacts(bundle, sourceVersionId, workspace.scoreEngine).matchesPerformanceMidi
          : false,
      );
    }).catch(() => {
      if (!cancelled) {
        setEditedSource(false);
        setHasCurrentScore(false);
        setSourceParentId(null);
      }
    });
    return () => { cancelled = true; };
  }, [sourceVersionId, workspace.activeWorkId, workspace.scoreEngine]);

  if (!sourceVersionId || !workspace.activeWorkId) return null;

  const canEdit = Boolean(performanceRange && performanceRange.end > performanceRange.start);
  const canPitch = selectedNotes.length === 1;
  const canRemove = selectedNotes.length > 0;

  function beginEditing() {
    if (!canEdit) return;
    setError(null);
    setOperation(canPitch ? "pitch" : canRemove ? "remove" : "add");
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setError(null);
  }

  function makeOperation(): NoteCorrectionOperation {
    if (!performanceRange) throw new Error("Select a note or passage before editing the transcription.");
    if (operation === "remove") {
      return { kind: "remove", noteIds: selectedIds };
    }
    if (operation === "pitch") {
      if (!selectedNote?.id) throw new Error("Select one note to change its pitch.");
      return { kind: "pitch", noteId: selectedNote.id, pitch };
    }
    return {
      kind: "add",
      pitch,
      start: performanceRange.start,
      end: performanceRange.end,
      velocity: 80,
    };
  }

  async function saveCorrection() {
    if (!performanceRange) return;
    setSaving(true);
    setError(null);
    try {
      const bundle = await getWorkBundle(workspace.activeWorkId!);
      const projectId = bundle.work.project_id;
      const payload = buildCorrectionPayload(notes, performanceRange, makeOperation());
      const result = await startCorrectionWorkflow(sourceVersionId!, projectId, payload);
      await waitForJob(result.job.id, () => undefined);
      clearSelection();
      window.location.reload();
    } catch (caught) {
      setError(errorMessage(caught));
      setSaving(false);
    }
  }

  async function regenerate() {
    setRegenerating(true);
    setError(null);
    try {
      const bundle = await getWorkBundle(workspace.activeWorkId!);
      const projectId = bundle.work.project_id;
      const jobs = await regenerateFromCorrected(sourceVersionId!, projectId, workspace.scoreEngine);
      await Promise.all([
        waitForJob(jobs.score.job.id, () => undefined),
        waitForJob(jobs.analysis.job.id, () => undefined),
      ]);
      window.location.reload();
    } catch (caught) {
      setError(errorMessage(caught));
      setRegenerating(false);
    }
  }

  return (
    <div
      data-testid="transcription-correction-controls"
      style={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "var(--s-2)",
        padding: "var(--s-2) 0",
        borderTop: "1px solid var(--border)",
      }}
    >
      {editedSource && (
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          Corrected transcription{sourceParentId ? " · machine transcription preserved" : ""}
        </span>
      )}

      {!editing && canEdit && (
        <button className="btn btn-sm" type="button" onClick={beginEditing}>
          Edit transcription
        </button>
      )}

      {editing && (
        <>
          {canPitch && (
            <button
              className={`btn btn-sm${operation === "pitch" ? " btn-primary" : ""}`}
              type="button"
              onClick={() => setOperation("pitch")}
            >
              Change pitch
            </button>
          )}
          {canRemove && (
            <button
              className={`btn btn-sm${operation === "remove" ? " btn-primary" : ""}`}
              type="button"
              onClick={() => setOperation("remove")}
            >
              Remove {selectedNotes.length > 1 ? "notes" : "note"}
            </button>
          )}
          <button
            className={`btn btn-sm${operation === "add" ? " btn-primary" : ""}`}
            type="button"
            onClick={() => setOperation("add")}
          >
            Add missing note
          </button>

          {(operation === "pitch" || operation === "add") && (
            <label style={{ display: "inline-flex", alignItems: "center", gap: "var(--s-1)", fontSize: "var(--fs-xs)" }}>
              MIDI pitch
              <input
                aria-label="MIDI pitch"
                type="number"
                min={0}
                max={127}
                step={1}
                value={pitch}
                onChange={(event) => setPitch(Number(event.target.value))}
                style={{ width: 64, padding: "4px 6px" }}
              />
            </label>
          )}

          <button className="btn btn-sm btn-primary" type="button" disabled={saving} onClick={() => void saveCorrection()}>
            {saving ? "Saving…" : "Save correction"}
          </button>
          <button className="btn btn-sm btn-ghost" type="button" disabled={saving} onClick={cancelEditing}>
            Cancel
          </button>
        </>
      )}

      {editedSource && !hasCurrentScore && (
        <button className="btn btn-sm" type="button" disabled={regenerating} onClick={() => void regenerate()}>
          {regenerating ? "Regenerating…" : "Regenerate from corrected transcription"}
        </button>
      )}

      {error && <span role="alert" className="status">{error}</span>}
    </div>
  );
}
