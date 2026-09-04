import { describe, expect, it } from "vitest";
import { projectMelodyReduction } from "@/lib/melody-reduction";
import type { Insight } from "@/lib/domain.types";
import type { RepresentationEntry } from "@/lib/stores/workspace";

function melodyInsight(versionId = "midi-v1", notes: unknown[] = [
  { pitch: 72, start_seconds: 1.0001, end_seconds: 1.5001, velocity: 80 },
  { pitch: 74, start_seconds: 1.5001, end_seconds: 2.0001, velocity: 82 },
]): Insight & { version_id: string } {
  return {
    id: "melody-1",
    version_id: versionId,
    kind: "melody",
    claim: "Range: MIDI 72–74",
    confidence: null,
    evidence: { notes },
    span: { start_seconds: null, end_seconds: null },
  } as unknown as Insight & { version_id: string };
}

function pianoRoll(versionId = "midi-v1", notes: RepresentationEntry["notes"] = [
  { id: "note-c5", pitch: 72, start: 1, end: 1.5, velocity: 80 },
  { id: "note-d5", pitch: 74, start: 1.5, end: 2, velocity: 82 },
]): RepresentationEntry {
  return {
    kind: "piano_roll",
    label: "Piano Roll",
    sourceUrl: "",
    sourceLabel: "Transcription MIDI",
    confidence: null,
    provenance: "basic_pitch",
    versionId,
    notes,
  };
}

describe("projectMelodyReduction", () => {
  it("maps rounded model tuples to exact persisted note entity IDs on the same Version", () => {
    const result = projectMelodyReduction(melodyInsight(), pianoRoll());

    expect(result.status).toBe("supported");
    if (result.status !== "supported") return;
    expect(result.sourceVersionId).toBe("midi-v1");
    expect(result.notes.map((note) => note.id)).toEqual(["note-c5", "note-d5"]);
    expect(result.notes.map((note) => [note.startSeconds, note.endSeconds])).toEqual([
      [1, 1.5],
      [1.5, 2],
    ]);
  });

  it("fails closed when the melody Insight belongs to a different Version", () => {
    expect(projectMelodyReduction(melodyInsight("midi-v2"), pianoRoll())).toEqual({
      status: "unavailable",
      reason: "melody evidence and Piano Roll do not share one exact Version",
    });
  });

  it("fails closed when a proposed tuple is ambiguous instead of guessing identity", () => {
    const roll = pianoRoll("midi-v1", [
      { id: "note-a", pitch: 72, start: 1, end: 1.5, velocity: 80 },
      { id: "note-b", pitch: 72, start: 1.002, end: 1.502, velocity: 80 },
    ]);
    const result = projectMelodyReduction(
      melodyInsight("midi-v1", [{ pitch: 72, start_seconds: 1.001, end_seconds: 1.501, velocity: 80 }]),
      roll,
    );

    expect(result).toEqual({
      status: "unavailable",
      reason: "a proposed melody note maps ambiguously to multiple source note entities",
    });
  });

  it("fails closed when even one proposed note cannot be identified", () => {
    const result = projectMelodyReduction(
      melodyInsight("midi-v1", [
        { pitch: 72, start_seconds: 1, end_seconds: 1.5, velocity: 80 },
        { pitch: 79, start_seconds: 2, end_seconds: 2.5, velocity: 80 },
      ]),
      pianoRoll(),
    );

    expect(result.status).toBe("unavailable");
  });
});
