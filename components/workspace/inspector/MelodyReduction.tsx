"use client";

import { Disclosure, DisclosureButton, DisclosurePanel } from "@headlessui/react";
import Tooltip from "@/components/ui/Tooltip";
import type { Insight } from "@/lib/domain.types";
import {
  projectMelodyReduction,
  type MelodyReductionProjection,
} from "@/lib/melody-reduction";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
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
  playheadSeconds,
  selectedNoteId,
  onSelectNote,
}: {
  insight: Insight;
  projection: SupportedMelodyReduction;
  pieceEndSeconds: number;
  playheadSeconds?: number | null;
  selectedNoteId?: string | null;
  onSelectNote: (note: MelodyReductionNote) => void;
}) {
  const { engine, method, model } = provenanceLabels(insight);
  const pitches = projection.notes.map((note) => note.pitch);
  const minPitch = Math.min(...pitches);
  const maxPitch = Math.max(...pitches);
  const pitchSpan = Math.max(1, maxPitch - minPitch);
  const timelineEnd = Math.max(pieceEndSeconds, projection.endSeconds, 0.001);
  const x = (seconds: number) => 10 + (Math.max(0, seconds) / timelineEnd) * 460;
  const y = (pitch: number) => 58 - ((pitch - minPitch) / pitchSpan) * 42;
  const showPlayhead = playheadSeconds !== null
    && playheadSeconds !== undefined
    && playheadSeconds >= 0
    && playheadSeconds <= timelineEnd;

  return (
    <section className={styles.reduction} aria-label="Experimental melody reduction">
      <div className={styles.header}>
        <div className={styles.heading}>
          <strong>Melody</strong>
          <span className={styles.count}>{projection.notes.length} notes</span>
        </div>
        <Tooltip content="Model-specific melody proposal. Click any note to locate its exact source note in the Piano Roll.">
          <span className={styles.qualifier} tabIndex={0}>Experimental</span>
        </Tooltip>
      </div>

      <div className={styles.object}>
        <svg
          viewBox="0 0 480 88"
          role="group"
          aria-label={`Proposed melody reduction across the full Piano Roll timeline with ${projection.notes.length} exact source notes`}
        >
          <line
            x1={10}
            x2={470}
            y1={75}
            y2={75}
            stroke="var(--border)"
            strokeWidth={0.7}
            strokeOpacity={0.5}
          />
          <text x={10} y={84} className={styles.timeLabel}>0:00</text>
          <text x={470} y={84} textAnchor="end" className={styles.timeLabel}>
            {formatClock(timelineEnd)}
          </text>
          {showPlayhead && (
            <line
              className={styles.playhead}
              data-melody-playhead="true"
              x1={x(playheadSeconds)}
              x2={x(playheadSeconds)}
              y1={8}
              y2={75}
            />
          )}
          {projection.notes.map((note) => {
            const startX = x(note.startSeconds);
            const endX = x(note.endSeconds);
            const selected = selectedNoteId === note.id;
            const playing = showPlayhead
              && playheadSeconds >= note.startSeconds
              && playheadSeconds <= note.endSeconds;
            const label = `${pitchName(note.pitch)} at ${formatClock(note.startSeconds)}`;
            return (
              <rect
                key={note.id}
                className={styles.melodyNote}
                data-melody-note-id={note.id}
                data-selected={selected ? "true" : undefined}
                data-playing={playing ? "true" : undefined}
                x={startX}
                y={y(note.pitch)}
                width={Math.max(4, endX - startX)}
                height={7}
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

      <Disclosure>
        {({ open }) => (
          <>
            <DisclosureButton className={styles.aboutButton}>
              <span>About</span>
              <svg
                viewBox="0 0 16 16"
                aria-hidden="true"
                className={open ? styles.chevronOpen : styles.chevron}
              >
                <path d="m5 6 3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </DisclosureButton>
            <DisclosurePanel className={styles.detailsPanel}>
              <dl>
                <dt>Source</dt><dd>Version {projection.sourceVersionId}</dd>
                <dt>Engine</dt><dd>{engine}</dd>
                <dt>Method</dt><dd>{method}</dd>
                {model && <><dt>Model</dt><dd>{model}</dd></>}
                <dt>Mapping</dt><dd>{projection.notes.length}/{projection.notes.length} exact Piano Roll notes</dd>
                <dt>Limit</dt><dd>Experimental interpretation, not a verified melody label or top-voice rule. LStoM is established on arranged pop MIDI; general piano and dense polyphony remain ambiguous.</dd>
              </dl>
            </DisclosurePanel>
          </>
        )}
      </Disclosure>
    </section>
  );
}

export default function MelodyReduction({ insight }: { insight: Insight }) {
  const { workspace, setSelection, setActiveRepresentation } = useWorkspace();
  const { transport, seek } = useTransport();
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
      playheadSeconds={transport.activeSource?.role === "score" ? null : transport.position}
      selectedNoteId={selectedNoteId}
      onSelectNote={selectSingleNote}
    />
  );
}
