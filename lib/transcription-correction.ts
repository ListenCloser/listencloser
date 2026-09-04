import { clearWorkDataCache, startScoreWorkflow } from "./api-client";
import { openapiClient, requireOpenApiData } from "./openapi-client";

export type CorrectionNote = {
  id?: string;
  pitch: number;
  start: number;
  end: number;
  velocity: number;
};

export type CorrectedNotePayload = {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
};

export type NoteCorrectionOperation =
  | { kind: "remove"; noteIds: string[] }
  | { kind: "pitch"; noteId: string; pitch: number }
  | { kind: "add"; pitch: number; start: number; end: number; velocity?: number };

export type CorrectionPayload = {
  selectionStart: number;
  selectionEnd: number;
  correctedNotes: CorrectedNotePayload[];
};

function assertMidiPitch(pitch: number): void {
  if (!Number.isInteger(pitch) || pitch < 0 || pitch > 127) {
    throw new Error("Pitch must be a MIDI note from 0 to 127.");
  }
}

function assertTimeRange(start: number, end: number): void {
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) {
    throw new Error("Choose a valid note or passage before saving a correction.");
  }
}

function payloadNote(note: CorrectionNote): CorrectedNotePayload {
  assertMidiPitch(note.pitch);
  assertTimeRange(note.start, note.end);
  return {
    pitch: note.pitch,
    start: note.start,
    end: note.end,
    velocity: Math.max(1, Math.min(127, Math.round(note.velocity || 64))),
  };
}

/**
 * Build the complete replacement note world for the selected span.
 *
 * The backend correction contract replaces every note fully contained by the
 * selected span, so unchanged notes inside that span must be sent back too.
 * Keeping that rule here prevents a one-note edit from deleting neighboring
 * notes in a chord or dense passage.
 */
export function buildCorrectionPayload(
  notes: CorrectionNote[],
  selection: { start: number; end: number },
  operation: NoteCorrectionOperation,
): CorrectionPayload {
  assertTimeRange(selection.start, selection.end);

  const inSelection = notes.filter(
    (note) => note.start >= selection.start && note.end <= selection.end,
  );
  let corrected = inSelection.map((note) => ({ ...note }));

  if (operation.kind === "remove") {
    if (operation.noteIds.length === 0) throw new Error("Select at least one note to remove.");
    const ids = new Set(operation.noteIds);
    const found = corrected.filter((note) => note.id && ids.has(note.id)).length;
    if (found !== ids.size) throw new Error("The selected note is outside this correction passage.");
    corrected = corrected.filter((note) => !note.id || !ids.has(note.id));
  } else if (operation.kind === "pitch") {
    assertMidiPitch(operation.pitch);
    const index = corrected.findIndex((note) => note.id === operation.noteId);
    if (index < 0) throw new Error("The selected note is outside this correction passage.");
    corrected[index] = { ...corrected[index], pitch: operation.pitch };
  } else {
    assertMidiPitch(operation.pitch);
    assertTimeRange(operation.start, operation.end);
    if (operation.start < selection.start || operation.end > selection.end) {
      throw new Error("The added note must stay inside the selected passage.");
    }
    corrected.push({
      pitch: operation.pitch,
      start: operation.start,
      end: operation.end,
      velocity: operation.velocity ?? 80,
    });
  }

  return {
    selectionStart: selection.start,
    selectionEnd: selection.end,
    correctedNotes: corrected.map(payloadNote),
  };
}

export async function startCorrectionWorkflow(
  versionId: string,
  projectId: string,
  payload: CorrectionPayload,
) {
  const result = await openapiClient.POST("/api/v1/workflows/correct", {
    body: {
      version_id: versionId,
      project_id: projectId,
      corrected_notes: payload.correctedNotes,
      selection_start: payload.selectionStart,
      selection_end: payload.selectionEnd,
    },
  });
  const data = requireOpenApiData(result);
  clearWorkDataCache();
  return data;
}

export async function startAnalysisFromCorrected(versionId: string, projectId: string) {
  const result = await openapiClient.POST("/api/v1/workflows/analyze", {
    body: { version_id: versionId, project_id: projectId },
  });
  const data = requireOpenApiData(result);
  clearWorkDataCache();
  return data;
}

export async function regenerateFromCorrected(
  versionId: string,
  projectId: string,
  scoreEngine: "musescore" | "pm2s",
) {
  const [score, analysis] = await Promise.all([
    startScoreWorkflow(versionId, projectId, scoreEngine),
    startAnalysisFromCorrected(versionId, projectId),
  ]);
  return { score, analysis };
}
