"use client";

import RepresentationLane from "./RepresentationLane";
import { useWorkspace } from "@/lib/stores/workspace";

const KIND_LABELS: Record<string, string> = {
  piano_roll: "Piano Roll",
  waveform: "Waveform",
  spectrogram: "Spectrogram",
  score: "Score",
  harmony: "Harmony",
  structure: "Structure",
  annotations: "Annotations",
};

type Note = { pitch: number; start: number; end: number; velocity: number };

export default function RepresentationStack({
  mode = "explore",
  correctedNotes,
  onCorrectedNotesChange,
}: {
  mode?: string;
  correctedNotes?: Note[] | null;
  onCorrectedNotesChange?: ((notes: Note[]) => void) | undefined;
}) {
  const {
    workspace,
    expandRepresentation,
    focusRepresentation,
    removeRepresentation,
  } = useWorkspace();

  const { representations, expandedRepresentation, focusRepresentation: focusedKind } = workspace;

  if (representations.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "var(--s-4)",
          flex: 1,
          padding: "var(--s-5)",
          color: "var(--muted)",
          fontSize: "var(--fs-sm)",
          textAlign: "center",
          border: "1px dashed var(--border)",
          borderRadius: "var(--r-md)",
          margin: "var(--s-2)",
        }}
      >
        <span style={{ fontSize: 32, lineHeight: 1 }}>🎵</span>
        <div>
          <div style={{ fontWeight: "var(--fw-medium)", color: "var(--text)", marginBottom: "var(--s-1)" }}>
            No representations yet
          </div>
          <div>Import audio to see representations</div>
        </div>
        <button className="btn btn-primary" style={{ marginTop: "var(--s-2)" }}>
          Import Audio
        </button>
      </div>
    );
  }

  const ordered = [...representations];
  if (expandedRepresentation) {
    const idx = ordered.findIndex((r) => r.kind === expandedRepresentation);
    if (idx > 0) {
      const [item] = ordered.splice(idx, 1);
      ordered.unshift(item);
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--s-2)",
        flex: 1,
        overflow: "hidden",
        padding: "var(--s-2)",
      }}
    >
      {ordered.map((rep) => (
        <RepresentationLane
          key={rep.kind}
          kind={rep.kind}
          label={KIND_LABELS[rep.kind] ?? rep.label}
          sourceLabel={rep.sourceLabel}
          confidence={rep.confidence}
          isExpanded={rep.kind === expandedRepresentation}
          isFocused={rep.kind === focusedKind}
          onExpand={() => expandRepresentation(rep.kind)}
          onFocus={() => focusRepresentation(rep.kind)}
          onRemove={() => removeRepresentation(rep.kind)}
          editable={mode === "correct" && rep.kind === "piano_roll"}
          correctedNotes={rep.kind === "piano_roll" ? correctedNotes : undefined}
          onNotesChange={rep.kind === "piano_roll" ? onCorrectedNotesChange : undefined}
        />
      ))}
    </div>
  );
}
