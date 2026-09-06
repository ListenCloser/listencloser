"use client";

import { useMemo, useState } from "react";
import { pitchToName } from "@/lib/notes";
import {
  addDraftNote,
  buildCorrectionReplacement,
  removeDraftNotes,
  transposeDraftNotes,
  type EditablePianoRollNote,
} from "@/lib/piano-roll-correction";
import { useWorkspace } from "@/lib/stores/workspace";

type TimeRange = { start: number; end: number };

export default function PianoRollCorrectionPanel({
  sourceNotes,
  sourceVersionId,
  draftNotes,
  selectedNoteIds,
  selectionTimeRange,
  onDraftChange,
  onCancel,
  onSelectNote,
}: {
  sourceNotes: EditablePianoRollNote[];
  sourceVersionId: string | null;
  draftNotes: EditablePianoRollNote[] | null;
  selectedNoteIds: string[];
  selectionTimeRange: TimeRange | null;
  onDraftChange: (notes: EditablePianoRollNote[]) => void;
  onCancel: () => void;
  onSelectNote: (id: string) => void;
}) {
  const { requestPianoRollCorrection, setPianoRollCorrectionOperation, workspace } = useWorkspace();
  const [addPitch, setAddPitch] = useState(60);
  const operation = workspace.pianoRollCorrectionOperation ?? { state: "idle" as const, label: "", message: "" };
  const editing = draftNotes !== null;
  const busy = operation.state === "running";
  const selected = useMemo(() => {
    if (!draftNotes) return [];
    const ids = new Set(selectedNoteIds);
    return draftNotes.filter((note) => note.id && ids.has(note.id));
  }, [draftNotes, selectedNoteIds]);

  if (!sourceVersionId) return null;
  if (!editing) {
    return (
      <div className="piano-roll-correction" style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <button
          type="button"
          className="btn"
          onClick={() => {
            setPianoRollCorrectionOperation({ state: "idle", label: "" });
            onDraftChange(sourceNotes.map((note) => ({ ...note })));
          }}
        >
          Edit transcription
        </button>
        {operation.state === "success" && operation.message && <span className="muted">{operation.message}</span>}
        {(operation.state === "error" || operation.state === "disconnected") && operation.message && (
          <span role="alert" className="muted">{operation.message}</span>
        )}
      </div>
    );
  }

  const replacement = buildCorrectionReplacement(sourceNotes, draftNotes);
  const canAdd = Boolean(selectionTimeRange && selectionTimeRange.end > selectionTimeRange.start);

  return (
    <div
      className="piano-roll-correction"
      aria-label="Edit transcription"
      style={{ display: "grid", gap: 8, marginBottom: 10, padding: 10, border: "1px solid var(--border)", borderRadius: 6 }}
    >
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <strong style={{ fontSize: "var(--fs-sm)" }}>Edit transcription</strong>
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
          Select a short passage, then repair its notes. Score stays unchanged.
        </span>
      </div>

      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn"
          disabled={!selected.length || busy}
          onClick={() => onDraftChange(transposeDraftNotes(draftNotes, selectedNoteIds, -1))}
        >
          Pitch −1
        </button>
        <button
          type="button"
          className="btn"
          disabled={!selected.length || busy}
          onClick={() => onDraftChange(transposeDraftNotes(draftNotes, selectedNoteIds, 1))}
        >
          Pitch +1
        </button>
        <button
          type="button"
          className="btn"
          disabled={!selected.length || busy}
          onClick={() => onDraftChange(removeDraftNotes(draftNotes, selectedNoteIds))}
        >
          Remove
        </button>
        <label className="muted" style={{ display: "inline-flex", gap: 4, alignItems: "center", fontSize: "var(--fs-xs)" }}>
          Add MIDI pitch
          <input
            aria-label="MIDI pitch for missing note"
            type="number"
            min={0}
            max={127}
            value={addPitch}
            disabled={!canAdd || busy}
            onChange={(event) => setAddPitch(Math.max(0, Math.min(127, Number(event.target.value))))}
            style={{ width: 58 }}
          />
        </label>
        <button
          type="button"
          className="btn"
          disabled={!canAdd || busy}
          onClick={() => {
            if (!selectionTimeRange) return;
            const id = `draft:add:${Date.now()}:${draftNotes.length}`;
            onDraftChange(addDraftNote(draftNotes, {
              id,
              pitch: addPitch,
              start: selectionTimeRange.start,
              end: selectionTimeRange.end,
              velocity: 96,
            }));
            onSelectNote(id);
          }}
        >
          Add note
        </button>
      </div>

      {selected.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} aria-label="Selected transcription notes">
          {selected.map((note) => (
            <button key={note.id} type="button" className="btn" onClick={() => note.id && onSelectNote(note.id)} disabled={busy}>
              {pitchToName(note.pitch)} · {note.start.toFixed(2)}–{note.end.toFixed(2)}s
            </button>
          ))}
        </div>
      )}

      {!selected.length && !selectionTimeRange && (
        <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>Drag over a short passage to choose notes or an add-note duration.</span>
      )}

      <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={!replacement || busy}
          onClick={() => {
            if (replacement) requestPianoRollCorrection(sourceVersionId, replacement);
          }}
        >
          {busy ? "Saving…" : "Save correction"}
        </button>
        <button type="button" className="btn" disabled={busy} onClick={onCancel}>Cancel</button>
        {replacement && (
          <span className="muted" style={{ fontSize: "var(--fs-xs)" }}>
            {replacement.pitchChanged ? `${replacement.pitchChanged} pitch` : ""}
            {replacement.pitchChanged && (replacement.added || replacement.removed) ? " · " : ""}
            {replacement.added ? `${replacement.added} added` : ""}
            {replacement.added && replacement.removed ? " · " : ""}
            {replacement.removed ? `${replacement.removed} removed` : ""}
          </span>
        )}
        {(operation.state === "error" || operation.state === "disconnected") && operation.message && (
          <span role="alert" className="muted">{operation.message}</span>
        )}
      </div>
    </div>
  );
}
