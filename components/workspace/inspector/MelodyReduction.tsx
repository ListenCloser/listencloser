"use client";

import { useId, useState } from "react";
import type { Insight } from "@/lib/domain.types";
import {
  projectMelodyReduction,
  type MelodyReductionProjection,
} from "@/lib/melody-reduction";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport, type PlaybackSource } from "@/lib/stores/transport";
import styles from "./MelodyReduction.module.css";

const NOTE_NAMES = ["C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B"] as const;

type SupportedMelodyReduction = Extract<MelodyReductionProjection, { status: "supported" }>;
type MelodyReductionNote = SupportedMelodyReduction["notes"][number];

function pitchName(pitch: number): string {
  return `${NOTE_NAMES[((pitch % 12) + 12) % 12]}${Math.floor(pitch / 12) - 1}`;
}

function formatClock(seconds: number): string {
  const value = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(value / 60);
  const remainder = value % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? value as Record<string, unknown> : null;
}

function stringField(record: Record<string, unknown> | null, key: string): string | null {
  const value = record?.[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function playbackActionLabel(role: PlaybackSource["role"] | null): string {
  switch (role) {
    case "original": return "Hear recording";
    case "transcription": return "Hear transcription";
    case "score": return "Hear score";
    case "derived": return "Hear playback";
    default: return "Hear";
  }
}

function provenanceLabels(insight: Insight): { engine: string; method: string; model: string | null } {
  const provenance = asRecord(insight.provenance);
  const engine = asRecord(provenance?.engine);
  const evidence = asRecord(insight.evidence);
  return {
    engine: stringField(engine, "engine") ?? stringField(engine, "name") ?? "LStoM",
    method: stringField(provenance, "method") ?? stringField(evidence, "heuristic") ?? "method-specific melody interpretation",
    model: stringField(evidence, "model_version") ?? stringField(engine, "model_version"),
  };
}

export function MelodyReductionObject({
  insight,
  projection,
  pieceEndSeconds,
  playbackRole,
  canHear,
  selectedNoteId,
  onFocus,
  onHear,
  onSelectNote,
}: {
  insight: Insight;
  projection: SupportedMelodyReduction;
  pieceEndSeconds: number;
  playbackRole: PlaybackSource["role"] | null;
  canHear: boolean;
  selectedNoteId?: string | null;
  onFocus: () => void;
  onHear: () => void;
  onSelectNote: (note: MelodyReductionNote) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const bodyId = useId();
  const { engine, method, model } = provenanceLabels(insight);
  const pitches = projection.notes.map((note) => note.pitch);
  const minPitch = Math.min(...pitches);
  const maxPitch = Math.max(...pitches);
  const pitchSpan = Math.max(1, maxPitch - minPitch);
  const timelineEnd = Math.max(pieceEndSeconds, projection.endSeconds, 0.001);
  const x = (seconds: number) => 10 + (Math.max(0, seconds) / timelineEnd) * 460;
  const y = (pitch: number) => 91 - ((pitch - minPitch) / pitchSpan) * 66;

  return (
    <section className={styles.reduction} aria-label="Experimental melody reduction">
      <div className={styles.header}>
        <div className={styles.heading}>
          <strong>Melody</strong>
          <span className={styles.qualifier}>Experimental</span>
          <span className={styles.count}>{projection.notes.length} proposed notes</span>
        </div>
        <button
          type="button"
          className={styles.toggle}
          aria-expanded={!collapsed}
          aria-controls={bodyId}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? "Show" : "Hide"}
        </button>
      </div>

      {!collapsed && (
        <div className={styles.body} id={bodyId}>
          <div className={styles.object}>
            <svg
              viewBox="0 0 480 112"
              role="img"
              aria-label={`Proposed melody reduction across the full Piano Roll timeline with ${projection.notes.length} exact source notes`}
            >
              <line
                x1={10}
                x2={470}
                y1={101}
                y2={101}
                stroke="var(--border)"
                strokeWidth={0.8}
                strokeOpacity={0.65}
              />
              <text x={10} y={109} className={styles.timeLabel}>0:00</text>
              <text x={470} y={109} textAnchor="end" className={styles.timeLabel}>
                {formatClock(timelineEnd)}
              </text>
              {projection.notes.map((note) => {
                const startX = x(note.startSeconds);
                const endX = x(note.endSeconds);
                const selected = selectedNoteId === note.id;
                const label = `${pitchName(note.pitch)} at ${formatClock(note.startSeconds)}`;
                return (
                  <rect
                    key={note.id}
                    className={styles.melodyNote}
                    data-melody-note-id={note.id}
                    data-selected={selected ? "true" : undefined}
                    x={startX}
                    y={y(note.pitch)}
                    width={Math.max(4, endX - startX)}
                    height={8}
                    rx={2}
                    role="button"
                    tabIndex={0}
                    aria-label={`Show ${label} in Piano Roll`}
                    aria-pressed={selected}
                    onClick={() => onSelectNote(note)}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      event.preventDefault();
                      onSelectNote(note);
                    }}
                  >
                    <title>{label}</title>
                  </rect>
                );
              })}
            </svg>
          </div>

          <div className={styles.actions}>
            <button type="button" className={styles.primaryAction} onClick={onFocus}>Focus</button>
            <button type="button" onClick={onHear} disabled={!canHear}>
              {playbackActionLabel(playbackRole)}
            </button>
          </div>

          <details className={styles.details}>
            <summary>Details</summary>
            <dl>
              <dt>Source Version</dt><dd>{projection.sourceVersionId}</dd>
              <dt>Engine</dt><dd>{engine}</dd>
              <dt>Method</dt><dd>{method}</dd>
              {model && <><dt>Model</dt><dd>{model}</dd></>}
              <dt>Mapping</dt><dd>{projection.notes.length}/{projection.notes.length} exact Piano Roll notes</dd>
              <dt>Limit</dt><dd>Experimental interpretation, not a verified melody label or top-voice rule. LStoM is established on arranged pop MIDI; general piano and dense polyphony remain ambiguous.</dd>
            </dl>
          </details>
        </div>
      )}
    </section>
  );
}

export default function MelodyReduction({ insight }: { insight: Insight }) {
  const { workspace, setSelection, setActiveRepresentation } = useWorkspace();
  const { transport, seek, play } = useTransport();
  const pianoRoll = workspace.representations.find((item) => item.kind === "piano_roll");
  if (!pianoRoll) return null;

  const projection = projectMelodyReduction(insight, pianoRoll);
  if (projection.status !== "supported") return null;

  const pieceEndSeconds = Math.max(
    projection.endSeconds,
    ...(pianoRoll.notes ?? []).map((note) => note.end),
  );
  const selectedNoteId = workspace.selection?.noteIds?.length === 1
    ? workspace.selection.noteIds[0]
    : null;

  const focusReduction = () => {
    setSelection({
      timeRange: {
        start: projection.startSeconds,
        end: projection.endSeconds,
        domain: "performance",
      },
      noteIds: projection.notes.map((note) => note.id),
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    setActiveRepresentation("piano_roll");
  };

  const selectSingleNote = (note: MelodyReductionNote) => {
    setSelection({
      noteIds: [note.id],
      provenance: { origin: null, timeExact: true, measureApproximate: false },
    });
    setActiveRepresentation("piano_roll");
    if (transport.activeSource?.role !== "score") {
      seek(note.startSeconds);
    }
  };

  return (
    <MelodyReductionObject
      insight={insight}
      projection={projection}
      pieceEndSeconds={pieceEndSeconds}
      playbackRole={transport.activeSource?.role ?? null}
      canHear={Boolean(transport.activeSource)}
      selectedNoteId={selectedNoteId}
      onFocus={focusReduction}
      onSelectNote={selectSingleNote}
      onHear={() => {
        seek(projection.startSeconds);
        play();
      }}
    />
  );
}
